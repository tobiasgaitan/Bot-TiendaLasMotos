"""
Pins de BOT-BUILD-DEADLINE-BUDGET-023 (v10.65.0).

La política frío/caliente se activa solo si GEMINI_COLD_CALL_TIMEOUT_S
existe en el entorno (chequeado dinámicamente por _deadline_policy_enabled()).
Sin la var, effective_gemini_timeout_s() retorna GEMINI_CALL_TIMEOUT_S
(pins FIX-2A intactos sin edición).

Pines:
  D1-IS-COLD           — uptime < 120s → is_cold()==True.
  D2-IS-WARM           — uptime ≥ 120s → is_cold()==False.
  D3-COLD-TIMEOUT      — habilitado + cold → 30s.
  D4-WARM-TIMEOUT      — habilitado + warm → 18s.
  D5-COLD-CALL         — habilitado + cold → _call_gemini_with_retry_async usa 30s.
  D6-COLD-HANG         — habilitado + cold + hang → TimeoutError tras 3 intentos.
  D7-POLICY-DISABLED   — sin env var → GEMINI_CALL_TIMEOUT_S.
  D8-FIX2A-PATCH       — sin env var + patch(GEMINI_CALL_TIMEOUT_S, 2.0) → 2.0.
  D9-FIX2A-COLD        — habilitado + cold + patch constant → 30s (independiente).
  D10-COLD-BUDGET      — habilitado + cold + budget 45s → fallback.
"""

import asyncio
import os
import time
from unittest.mock import AsyncMock, patch

import pytest

from app.services.ai_brain import CerebroIA, GEMINI_CALL_TIMEOUT_S
import app.core.deadline_policy as dl_policy
from app.core.deadline_policy import (
    COLD_WINDOW_S,
    GEMINI_COLD_CALL_TIMEOUT_S,
    effective_gemini_timeout_s,
    is_cold,
    set_instance_started_monotonic,
)

ENV_COLD_ENABLED = {"GEMINI_COLD_CALL_TIMEOUT_S": "30"}


@pytest.fixture(autouse=True)
def _clean_deadline_ambient(monkeypatch):
    """F4.5: borrar GEMINI_COLD_CALL_TIMEOUT_S del entorno entre tests
    para que los pins de política-desactivada (D7/D8) no fallen si un
    dev tiene la var en su .env local.  También restaura el global
    _instance_started_monotonic para eliminar dependencia de orden."""
    monkeypatch.delenv("GEMINI_COLD_CALL_TIMEOUT_S", raising=False)
    saved = dl_policy._instance_started_monotonic
    yield
    dl_policy._instance_started_monotonic = saved


# ===========================================================================
# D1/D2 — is_cold() según uptime (independiente de política)
# ===========================================================================
def test_d1_is_cold_true_within_window():
    """D1: set_started_monotonic(t=now) → is_cold() == True."""
    set_instance_started_monotonic(time.monotonic())
    assert is_cold() is True


def test_d2_is_cold_false_outside_window():
    """D2: set_started_monotonic(t=now - COLD_WINDOW_S - 1) → is_cold() == False."""
    set_instance_started_monotonic(time.monotonic() - COLD_WINDOW_S - 1.0)
    assert is_cold() is False


# ===========================================================================
# D3/D4 — effective_gemini_timeout_s() frío vs caliente (política habilitada)
# ===========================================================================
def test_d3_cold_returns_cold_timeout():
    """D3: habilitado + frío → effective_gemini_timeout_s() == 30s."""
    set_instance_started_monotonic(time.monotonic())
    with patch.dict(os.environ, ENV_COLD_ENABLED):
        result = effective_gemini_timeout_s()
    assert result == 30.0, f"Frío habilitado: esperado 30s, recibido {result}s"


def test_d4_warm_returns_brain_constant():
    """D4: habilitado + caliente → effective_gemini_timeout_s() == GEMINI_CALL_TIMEOUT_S."""
    set_instance_started_monotonic(time.monotonic() - COLD_WINDOW_S - 1.0)
    with patch.dict(os.environ, ENV_COLD_ENABLED):
        result = effective_gemini_timeout_s()
    assert result == GEMINI_CALL_TIMEOUT_S, (
        f"Caliente habilitado: esperado {GEMINI_CALL_TIMEOUT_S}s, recibido {result}s"
    )


# ===========================================================================
# D5/D6 — _call_gemini_with_retry_async con política habilitada
# ===========================================================================
@pytest.mark.asyncio
async def test_d5_cold_call_succeeds_with_long_timeout():
    """D5: habilitado + frío → _call_gemini_with_retry_async completa."""
    with patch.dict(os.environ, ENV_COLD_ENABLED):
        set_instance_started_monotonic(time.monotonic())
        cerebro = CerebroIA()

        async def fast_func(*args, **kwargs):
            return "ok"

        result = await cerebro._call_gemini_with_retry_async(fast_func)
        assert result == "ok"


@pytest.mark.asyncio
async def test_d6_cold_hang_timeouts_propagate():
    """D6: habilitado + frío + hang → TimeoutError tras 3 intentos con cold_timeout."""
    with patch.dict(os.environ, ENV_COLD_ENABLED):
        set_instance_started_monotonic(time.monotonic())

        cerebro = CerebroIA()
        calls = {"n": 0}

        async def never_completes(*args, **kwargs):
            calls["n"] += 1
            await asyncio.Event().wait()

        with patch("app.core.deadline_policy.GEMINI_COLD_CALL_TIMEOUT_S", 0.05), \
             patch.object(asyncio, "sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(asyncio.TimeoutError):
                await cerebro._call_gemini_with_retry_async(never_completes)

        assert calls["n"] == 3, f"Esperaba 3 intentos, hubo {calls['n']}"
        assert mock_sleep.await_count == 2, "Backoff ausente"


# ===========================================================================
# D7/D8 — Política desactivada (sin env var) → pins FIX-2A intactos
# ===========================================================================
def test_d7_policy_disabled_returns_brain_constant():
    """D7: sin env var → effective_gemini_timeout_s() == GEMINI_CALL_TIMEOUT_S."""
    result = effective_gemini_timeout_s()
    assert result == GEMINI_CALL_TIMEOUT_S


def test_d8_fix2a_patch_still_works():
    """D8: sin env var + patch(GEMINI_CALL_TIMEOUT_S, 2.0) → 2.0."""
    with patch("app.services.ai_brain.GEMINI_CALL_TIMEOUT_S", 2.0):
        assert effective_gemini_timeout_s() == 2.0


# ===========================================================================
# D9 — Política habilitada + patch de constante → cold es independiente
# ===========================================================================
def test_d9_cold_independent_of_patched_constant():
    """D9: habilitado + cold + patch(GEMINI_CALL_TIMEOUT_S, 2.0) → 30s."""
    set_instance_started_monotonic(time.monotonic())
    with patch.dict(os.environ, ENV_COLD_ENABLED):
        with patch("app.services.ai_brain.GEMINI_CALL_TIMEOUT_S", 2.0):
            result = effective_gemini_timeout_s()
    assert result == 30.0, f"Frío + patch: esperado 30s, recibido {result}s"


# ===========================================================================
# D10 — Budget guard lee timeout efectivo frío (pineo directo de :749)
# ===========================================================================
@pytest.mark.asyncio
async def test_d10_cold_budget_guard_fires(caplog):
    """D10: habilitado + cold + budget 0.01s → elapsed real (≥0.05s del 1er timeout)
    + cold_timeout (0.05s) > budget (0.01s) → RuntimeError GEMINI_TIMEOUT_BUDGET_S.
    Sin mock de time.monotonic: el elapsed real del primer hang garantiza la violación
    del budget ínfimo de forma determinista y en <0.5s."""
    with patch.dict(os.environ, ENV_COLD_ENABLED):
        set_instance_started_monotonic(time.monotonic())

        cerebro = CerebroIA()
        calls = {"n": 0}

        async def slow_func(*args, **kwargs):
            calls["n"] += 1
            await asyncio.Event().wait()

        # budget 0.01s < elapsed real (≥0.05s del 1er wait_for) → guard dispara
        with patch("app.core.deadline_policy.GEMINI_COLD_CALL_TIMEOUT_S", 0.05), \
             patch("app.services.ai_brain.GEMINI_TIMEOUT_BUDGET_S", 0.01):
            with pytest.raises(RuntimeError, match="GEMINI_TIMEOUT_BUDGET_S"):
                await cerebro._call_gemini_with_retry_async(slow_func)

    assert calls["n"] == 1, (
        f"La guarda debe abortar tras 1 intento, hubo {calls['n']}"
    )
    budget_logs = [r.message for r in caplog.records if "GEMINI BUDGET" in r.message]
    assert budget_logs, "Falta marcador 🚨 [GEMINI BUDGET] en logs"