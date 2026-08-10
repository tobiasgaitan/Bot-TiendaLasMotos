"""
Regression pins for BOT-BUILD-MOTO-CANON-018 Fix C (capa 1).

Validates _call_gemini_with_retry_async exponential backoff, timeout retry
behavior, and the PCC deadline-budget guard.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import ai_brain
from app.services.ai_brain import CerebroIA


PHONE_E164 = "+573192564289"


class _MonotonicSequence:
    def __init__(self, values):
        self._values = list(values)
    def __call__(self):
        return self._values.pop(0) if self._values else 1_000_000.0


def _build_cerebro():
    cerebro = CerebroIA(catalog_service=None)
    cerebro.client = MagicMock()
    return cerebro


# ---------------------------------------------------------------------------
# GEM-D — asyncio.TimeoutError triggers 3 attempts within budget
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_moto_canon_018_gem_d_timeout_retries_within_budget(monkeypatch, caplog):
    cerebro = _build_cerebro()
    caplog.set_level("ERROR", logger="app.services.ai_brain")

    sleep_calls = []

    async def _fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr("app.services.ai_brain.asyncio.sleep", _fake_sleep)

    attempt = 0

    async def _always_timeout():
        nonlocal attempt
        attempt += 1
        raise asyncio.TimeoutError("forced timeout")

    with pytest.raises(asyncio.TimeoutError):
        await cerebro._call_gemini_with_retry_async(_always_timeout)

    assert attempt == 3, "TimeoutError must be retried twice (3 attempts total)"
    assert len(sleep_calls) == 2
    # base_delay=2.0: sleeps are 2.0+jitter and 4.0+jitter
    assert sleep_calls[0] >= 2.0
    assert sleep_calls[1] >= 4.0
    cumulative = sum(sleep_calls)
    assert cumulative <= float(ai_brain.GEMINI_TIMEOUT_BUDGET_S), (
        f"Cumulative wait {cumulative}s exceeds budget {ai_brain.GEMINI_TIMEOUT_BUDGET_S}s"
    )
    assert "🚨 [GEMINI ASYNC ERROR] Final failure" in caplog.text


# ---------------------------------------------------------------------------
# GEM-E — APIError 429 triggers exponential backoff
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_moto_canon_018_gem_e_quota_error_retries(monkeypatch, caplog):
    cerebro = _build_cerebro()
    caplog.set_level("ERROR", logger="app.services.ai_brain")

    sleep_calls = []

    async def _fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr("app.services.ai_brain.asyncio.sleep", _fake_sleep)

    from google.genai.errors import APIError

    attempt = 0

    async def _always_quota():
        nonlocal attempt
        attempt += 1
        raise APIError(code=429, response_json={})

    with pytest.raises(APIError):
        await cerebro._call_gemini_with_retry_async(_always_quota)

    assert attempt == 3
    assert len(sleep_calls) == 2
    assert sleep_calls[0] >= 2.0
    assert sleep_calls[1] >= 4.0
    assert "🚨 [GEMINI ASYNC ERROR] Final failure" in caplog.text


# ---------------------------------------------------------------------------
# GEM-F — Non-retriable error raises immediately
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_moto_canon_018_gem_f_non_retriable_raises_immediately(monkeypatch, caplog):
    cerebro = _build_cerebro()
    caplog.set_level("ERROR", logger="app.services.ai_brain")

    sleep_calls = []

    async def _fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr("app.services.ai_brain.asyncio.sleep", _fake_sleep)

    async def _value_error():
        raise ValueError("non-retriable")

    with pytest.raises(ValueError, match="non-retriable"):
        await cerebro._call_gemini_with_retry_async(_value_error)

    assert len(sleep_calls) == 0, "Non-retriable errors must not trigger backoff sleeps"
    assert "🚨 [GEMINI ASYNC ERROR] Final failure" in caplog.text


# ---------------------------------------------------------------------------
# GEM-G — Success on attempt 2 does not log final failure
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_moto_canon_018_gem_g_success_no_final_error_log(monkeypatch, caplog):
    cerebro = _build_cerebro()
    caplog.set_level("ERROR", logger="app.services.ai_brain")

    monkeypatch.setattr("app.services.ai_brain.asyncio.sleep", AsyncMock())

    attempt = 0

    async def _transient_then_ok():
        nonlocal attempt
        attempt += 1
        if attempt == 1:
            raise asyncio.TimeoutError("transient")
        return "ok"

    res = await cerebro._call_gemini_with_retry_async(_transient_then_ok)
    assert res == "ok"
    assert attempt == 2
    assert "🚨 [GEMINI ASYNC ERROR]" not in caplog.text


# ---------------------------------------------------------------------------
# C-20d DEADLINE (rewritten) — generator returns non-compliant text so
# validation runs and the deadline guard is exercised, forcing fallback.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_moto_canon_018_deadline_forces_degraded_fallback(monkeypatch, caplog):
    """When PCC_DEADLINE_BUDGET_S is set to a negative value, the deadline
    guard (elapsed > budget) fires deterministically on the first validation
    failure, forcing degrade to _build_pcc_fallback with the 'Ficha Tecnica:'
    prefix. This avoids flakiness from global time.monotonic patches being
    consumed by langfuse's @observe() wrapper."""
    cerebro = _build_cerebro()
    caplog.set_level("WARNING", logger="app.services.ai_brain")

    monkeypatch.setattr("app.services.ai_brain.PCC_DEADLINE_BUDGET_S", -1.0)

    attempts = []

    async def _mock_generate(*args, **kwargs):
        attempts.append(args)
        return "sin precio ni imagen"  # non-compliant, forces validation failure

    with patch.object(cerebro, "_generate_with_retry_async", side_effect=_mock_generate), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False):

        res = await cerebro.pensar_respuesta(
            "Hola, quisiera una moto",
            prospect_data={
                "exists": True,
                "nombre": "Mario",
                "_catalog_top_name": "Victory MRX 150",
                "_catalog_top_image": "https://img.url/mrx150.png",
            },
        )

    assert len(attempts) == 1, (
        "Deadline exhausted on first validation failure; no retry allowed"
    )
    assert "⏱️ [PCC-DEADLINE]" in caplog.text
    assert "Ficha Tecnica: Victory MRX 150" in res
    assert res is not None


# ---------------------------------------------------------------------------
# C-20c budget pin — parched budget aborts retries with RuntimeError
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_moto_canon_020_budget_aborts_retries(monkeypatch, caplog):
    """When GEMINI_TIMEOUT_BUDGET_S is tiny and monotonic reports a huge
    elapsed time, the budget check must raise RuntimeError (non-retriable)
    on the first attempt without any sleep."""
    cerebro = _build_cerebro()
    caplog.set_level("ERROR", logger="app.services.ai_brain")

    sleep_calls = []

    async def _fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr("app.services.ai_brain.asyncio.sleep", _fake_sleep)
    monkeypatch.setattr("app.services.ai_brain.GEMINI_TIMEOUT_BUDGET_S", 0.05)
    monkeypatch.setattr(
        "app.services.ai_brain.time.monotonic",
        _MonotonicSequence([0.0, 100.0]),
    )

    attempt = 0

    async def _always_timeout():
        nonlocal attempt
        attempt += 1
        raise asyncio.TimeoutError("forced timeout")

    with pytest.raises(RuntimeError, match="GEMINI_TIMEOUT_BUDGET_S"):
        await cerebro._call_gemini_with_retry_async(_always_timeout)

    assert attempt == 1, "Budget exhaustion must prevent retries"
    assert len(sleep_calls) == 0, "Budget abort must not sleep"
    assert "🚨 [GEMINI BUDGET]" in caplog.text


# ---------------------------------------------------------------------------
# C19-A — pensar_respuesta propagates the same captured start_pcc to both sites
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_moto_canon_018_c19a_pensar_propagates_captured_start_pcc(monkeypatch):
    """Both _generate_with_retry_async call sites in pensar_respuesta must
    receive pcc_deadline_start equal to the single start_pcc captured at the
    top of the function."""
    cerebro = _build_cerebro()
    monkeypatch.setattr("app.services.ai_brain.time.monotonic", lambda: 12345.0)

    captured = []

    async def _mock_generate(*args, **kwargs):
        captured.append(kwargs.get("pcc_deadline_start"))
        return ""

    for langfuse in (True, False):
        captured.clear()
        with patch.object(cerebro, "_generate_with_retry_async", side_effect=_mock_generate), \
             patch("app.services.ai_brain.LANGFUSE_AVAILABLE", langfuse), \
             patch("app.services.ai_brain.langfuse_context"), \
             patch("app.services.agentic_loop_service.AgenticOrchestrator.run_checker", return_value={"success": True, "report": {}}):
            await cerebro.pensar_respuesta(
                "Hola",
                prospect_data={"exists": True, "nombre": "Mario", "phone": PHONE_E164},
            )
        assert captured == [12345.0], (
            f"Branch LANGFUSE_AVAILABLE={langfuse} did not propagate the captured start_pcc"
        )


# ---------------------------------------------------------------------------
# C19-B — propagated deadline is honored by the inner PCC loop
# ---------------------------------------------------------------------------
def _empty_gemini_response():
    """Factory for a Gemini response whose candidate text is empty."""
    class _Part:
        text = ""
        function_call = None
    class _Content:
        parts = [_Part()]
    class _Candidate:
        content = _Content()
    class _Resp:
        candidates = [_Candidate()]
        usage_metadata = None
    return _Resp()


@pytest.mark.asyncio
async def test_moto_canon_018_c19b_deadline_propagation_cuts_inner_loop(monkeypatch, caplog):
    """The pcc_deadline_start propagated from pensar_respuesta is honored by
    _generate_with_retry_async: a value far in the past forces the inner loop
    to cut and degrade without raising an exception."""
    cerebro = _build_cerebro()
    caplog.set_level("WARNING", logger="app.services.ai_brain")

    # Simulate that the budget is already exhausted when the inner loop checks it.
    monkeypatch.setattr(
        "app.services.ai_brain.time.monotonic",
        lambda: float(ai_brain.PCC_DEADLINE_BUDGET_S) + 1.0,
    )

    with patch.object(cerebro, "_call_gemini_with_retry_async", return_value=_empty_gemini_response()):
        res = await cerebro._generate_with_retry_async(
            "Hola, quisiera una moto",
            context="",
            prospect_data={"exists": True, "nombre": "Mario", "habeas_data_accepted": True},
            history=[],
            pcc_deadline_start=0.0,
        )

    assert res is not None
    assert "⏱️ [PCC-DEADLINE] Inner loop cut" in caplog.text


# ---------------------------------------------------------------------------
# C19-C — callers without pcc_deadline_start keep the default behavior
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_moto_canon_018_c19c_default_deadline_for_legacy_callers(monkeypatch):
    """External/direct callers of _generate_with_retry_async that do not pass
    pcc_deadline_start must still work because the helper defaults to
    time.monotonic() internally."""
    cerebro = _build_cerebro()

    fixed_now = 99999.0
    monkeypatch.setattr("app.services.ai_brain.time.monotonic", lambda: fixed_now)

    # Patch the inner Gemini call with an empty-text response so the helper
    # exits cleanly without network traffic.
    with patch.object(cerebro, "_call_gemini_with_retry_async", return_value=_empty_gemini_response()):
        res = await cerebro._generate_with_retry_async(
            "Hola",
            context="",
            prospect_data={"exists": True, "nombre": "Mario"},
            history=[],
        )

    # The empty candidate triggers the legacy fallback response; the important
    # contract is that omitting pcc_deadline_start does not crash.
    assert isinstance(res, str) and len(res) > 0
