"""
[BOT-BUILD-TOOLLOOP-025] Regression pins for C-23 post-TOOL REJECTION text turn deadline.

P1a-3LEG: 3-leg C-23 flow at 62.3s elapsed → text PASO 1 returned (new cap 90s
          no longer cuts where old 60s did). Pre-fix: old 0.5 cap would cut → fallback.

P1b-4LEG-FORCED: 4-leg with FORCED TOOL VALIDATION TURN (:2214-2263) at 70s.

P2-PER-INNER-LOOP: flag resets per _generate_with_retry_async invocation.

P3-RATIO-075: ratio 0.75 boundaries (89.5s no cut, 90.5s cut) — search loop
               genuine, flag=False.

P5-LOG-ZSF: exemption log (100s, flag=True) vs cut log (99s, flag=False).

P6-NO-CREDIT: no-credit flow with flag=False → cut fires → text NOT returned.

P7-ABSOLUTE-CEILING: elapsed 121s > 120s (PCC_DEADLINE_BUDGET_S) → flag=True
                     but ceiling denies exemption → cut fires.

Clock: mutable float patched via monkeypatch, advanced ONLY inside
       _call_gemini_with_retry_async mock (network layer).
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from app.services import ai_brain
from app.services.ai_brain import CerebroIA


# ── helpers ──────────────────────────────────────────────────────────────────

def _build_brain_with_catalog():
    cerebro = CerebroIA(catalog_service=None)
    cerebro.client = MagicMock()
    mock_catalog = MagicMock()
    mock_catalog.search_items.return_value = [
        {
            "name": "Victory MRX 150",
            "price": "$5.000.000",
            "raw_price": 5000000,
            "cc": 150,
            "category": "motos",
            "image_url": "https://img.url/mrx150.png",
            "imagen_url": "",
        }
    ]
    mock_catalog.get_catalog_aliases.return_value = {}
    cerebro._catalog_service = mock_catalog
    return cerebro


def _resp_with_fc(fc_name, fc_args=None):
    _FC = type("_FC", (), {"name": fc_name, "args": fc_args or {}})
    _Part = type("_Part", (), {"text": "", "function_call": _FC()})
    _Content = type("_Content", (), {"parts": [_Part()]})
    _Candidate = type("_Candidate", (), {"content": _Content()})
    _Resp = type("_Resp", (), {"candidates": [_Candidate()], "usage_metadata": None})
    return _Resp()


def _resp_with_text(text):
    _Part = type("_Part", (), {"text": text, "function_call": None})
    _Content = type("_Content", (), {"parts": [_Part()]})
    _Candidate = type("_Candidate", (), {"content": _Content()})
    _Resp = type("_Resp", (), {"candidates": [_Candidate()], "usage_metadata": None})
    return _Resp()


MODEL_TEXT = "¡Hola Mario! Te presento nuestro TOP RESULT: Victory MRX 150 a $5.000.000. [IMAGE: https://img.url/mrx150.png](Ficha Tecnica: Victory MRX 150)"


# ── P1a ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_toolloop_budget_025_p1a_3leg_exemption(monkeypatch, caplog):
    """3-leg C-23 flow: 62.3s at iter 3 → cap 90s (ratio 0.75) → no cut →
    text returned. Old cap 60s (0.5) would have cut → fallback."""
    import logging
    cerebro = _build_brain_with_catalog()
    caplog.set_level(logging.WARNING, logger="app.services.ai_brain")
    monkeypatch.setattr(ai_brain, "PCC_DEADLINE_BUDGET_S", 120.0)
    monkeypatch.setattr(ai_brain, "PCC_INNER_LOOP_BUDGET_RATIO", 0.75)

    _clock = 0.0
    monkeypatch.setattr("app.services.ai_brain.time.monotonic", lambda: _clock)

    _script = [
        (40.0, _resp_with_fc("search_catalog", {"query": "moto"})),
        (10.0, _resp_with_fc("calculate_credit_score", {"precio": 5000000, "plazo_meses": 24})),
        (12.3, _resp_with_text(MODEL_TEXT)),
    ]

    async def _fake_gemini(func, *args, **kwargs):
        nonlocal _clock
        advance, response = _script.pop(0)
        _clock += advance
        return response

    monkeypatch.setattr(cerebro, "_call_gemini_with_retry_async", _fake_gemini)

    res = await cerebro._generate_with_retry_async(
        "Hola, quiero una moto a crédito",  # _CREDIT_TURN_KEYWORDS match
        context="",
        prospect_data={"exists": True, "nombre": "Mario", "habeas_data_accepted": True},
        history=[],
        pcc_deadline_start=0.0,
    )

    assert MODEL_TEXT[:20] in res
    assert "Inner loop cut" not in caplog.text


# ── P1b ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_toolloop_budget_025_p1b_4leg_forced_turn(monkeypatch, caplog):
    """4-leg FORCED TURN: LEG 1 no fc (40s cold) → FORCED send (10s)
    → search_catalog (10s) → reject (10s) → 70s at iter 3 → text returned."""
    import logging
    cerebro = _build_brain_with_catalog()
    caplog.set_level(logging.WARNING, logger="app.services.ai_brain")
    monkeypatch.setattr(ai_brain, "PCC_DEADLINE_BUDGET_S", 120.0)
    monkeypatch.setattr(ai_brain, "PCC_INNER_LOOP_BUDGET_RATIO", 0.75)

    _clock = 0.0
    monkeypatch.setattr("app.services.ai_brain.time.monotonic", lambda: _clock)

    if hasattr(cerebro, "_load_searchby_aliases"):
        monkeypatch.setattr(cerebro, "_load_searchby_aliases", lambda: [])

    _script = [
        (40.0, _resp_with_text("Hola")),                                    # LEG 1: no fc → FORCED
        (10.0, _resp_with_fc("search_catalog", {"query": "moto"})),         # LEG 1′ forced
        (10.0, _resp_with_fc("calculate_credit_score", {"precio": 5000000, "plazo_meses": 24})),  # LEG 2
        (10.0, _resp_with_text(MODEL_TEXT)),                                 # LEG 3
    ]

    async def _fake_gemini(func, *args, **kwargs):
        nonlocal _clock
        advance, response = _script.pop(0)
        _clock += advance
        return response

    monkeypatch.setattr(cerebro, "_call_gemini_with_retry_async", _fake_gemini)

    res = await cerebro._generate_with_retry_async(
        "Hola, quiero una moto a crédito",
        context="",
        prospect_data={"exists": True, "nombre": "Mario", "habeas_data_accepted": True},
        history=[],
        pcc_deadline_start=0.0,
    )

    assert MODEL_TEXT[:20] in res
    assert "Inner loop cut" not in caplog.text


# ── P2 ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_toolloop_budget_025_p2_per_inner_loop(monkeypatch):
    """Flag resets per _generate_with_retry_async invocation. Two consecutive
    calls, each with its own C-23 rejection flow → text returned in both."""
    cerebro = _build_brain_with_catalog()
    monkeypatch.setattr(ai_brain, "PCC_DEADLINE_BUDGET_S", 120.0)
    monkeypatch.setattr(ai_brain, "PCC_INNER_LOOP_BUDGET_RATIO", 0.75)

    for iteration in range(2):
        _clock = 0.0
        monkeypatch.setattr("app.services.ai_brain.time.monotonic", lambda: _clock)

        _script = [
            (40.0, _resp_with_fc("search_catalog", {"query": "moto"})),
            (10.0, _resp_with_fc("calculate_credit_score", {"precio": 5000000, "plazo_meses": 24})),
            (12.3, _resp_with_text(MODEL_TEXT)),
        ]

        async def _fake_gemini(func, *args, **kwargs):
            nonlocal _clock
            advance, response = _script.pop(0)
            _clock += advance
            return response

        monkeypatch.setattr(cerebro, "_call_gemini_with_retry_async", _fake_gemini)

        res = await cerebro._generate_with_retry_async(
            "Hola, quiero una moto a crédito", context="",
            prospect_data={"exists": True, "nombre": "Mario", "habeas_data_accepted": True},
            history=[], pcc_deadline_start=0.0,
        )
        assert MODEL_TEXT[:20] in res, (
            f"Iteration {iteration}: text NOT returned (flag did not work)"
        )


# ── P3 ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_toolloop_budget_025_p3_ratio_075_boundaries(monkeypatch):
    """Ratio 0.75 → cap = 90s (120 * 0.75). 89.5s: no cut → model text.
    90.5s: cut → fallback (NOT the model text)."""
    cerebro = _build_brain_with_catalog()
    monkeypatch.setattr(ai_brain, "PCC_DEADLINE_BUDGET_S", 120.0)
    monkeypatch.setattr(ai_brain, "PCC_INNER_LOOP_BUDGET_RATIO", 0.75)

    for clock_top, should_cut in [(89.5, False), (90.5, True)]:
        _clock = clock_top
        monkeypatch.setattr("app.services.ai_brain.time.monotonic", lambda: _clock)

        _script = [
            (0.0, _resp_with_fc("search_catalog", {"query": "tvs"})),
            (0.0, _resp_with_text(MODEL_TEXT)),
        ]

        async def _fake_gemini(func, *args, **kwargs):
            nonlocal _clock
            advance, response = _script.pop(0)
            _clock += advance
            return response

        monkeypatch.setattr(cerebro, "_call_gemini_with_retry_async", _fake_gemini)

        res = await cerebro._generate_with_retry_async(
            "Quiero información del catálogo",
            context="",
            prospect_data={"exists": True, "nombre": "Mario", "habeas_data_accepted": True},
            history=[],
            pcc_deadline_start=0.0,
        )

        if should_cut:
            assert MODEL_TEXT[:20] not in str(res), (
                "Expected cut at 90.5s (cap=90s) but model text was processed"
            )
        else:
            assert MODEL_TEXT[:20] in res, (
                "Expected no cut at 89.5s (cap=90s) but fallback was returned"
            )


# ── P5 ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_toolloop_budget_025_p5_log_zsf(monkeypatch, caplog):
    """Exemption path (100s, flag=True): exemption log present + no cut log.
    Cut path (99s, flag=False): cut log present."""
    import logging
    cerebro = _build_brain_with_catalog()
    caplog.set_level(logging.WARNING, logger="app.services.ai_brain")
    monkeypatch.setattr(ai_brain, "PCC_DEADLINE_BUDGET_S", 120.0)
    monkeypatch.setattr(ai_brain, "PCC_INNER_LOOP_BUDGET_RATIO", 0.75)

    # --- half A: exemption path (elapsed > cap at iter 3, flag=True) ---
    _clock = 0.0
    monkeypatch.setattr("app.services.ai_brain.time.monotonic", lambda: _clock)

    _script = [
        (50.0, _resp_with_fc("search_catalog", {"query": "moto"})),
        (10.0, _resp_with_fc("calculate_credit_score", {"precio": 5000000, "plazo_meses": 24})),
        (40.0, _resp_with_text(MODEL_TEXT)),
    ]

    async def _fake_gemini(func, *args, **kwargs):
        nonlocal _clock
        advance, response = _script.pop(0)
        _clock += advance
        return response

    monkeypatch.setattr(cerebro, "_call_gemini_with_retry_async", _fake_gemini)

    res = await cerebro._generate_with_retry_async(
        "Hola, quiero una moto a crédito", context="",
        prospect_data={"exists": True, "nombre": "Mario", "habeas_data_accepted": True},
        history=[], pcc_deadline_start=0.0,
    )
    assert MODEL_TEXT[:20] in res
    assert "⏱️ [PCC-DEADLINE] Exemption" in caplog.text
    assert "Inner loop cut" not in caplog.text

    # --- half B: cut path (elapsed > cap, flag=False) ---
    caplog.clear()
    _clock = 99.0
    monkeypatch.setattr("app.services.ai_brain.time.monotonic", lambda: _clock)

    _script2 = [
        (0.0, _resp_with_fc("search_catalog", {"query": "tvs"})),
        (0.0, _resp_with_text(MODEL_TEXT)),
    ]

    async def _fake_gemini2(func, *args, **kwargs):
        nonlocal _clock
        advance, response = _script2.pop(0)
        _clock += advance
        return response

    monkeypatch.setattr(cerebro, "_call_gemini_with_retry_async", _fake_gemini2)

    await cerebro._generate_with_retry_async(
        "Quiero información del catálogo", context="",
        prospect_data={"exists": True, "nombre": "Mario", "habeas_data_accepted": True},
        history=[], pcc_deadline_start=0.0,
    )
    assert "⏱️ [PCC-DEADLINE] Inner loop cut" in caplog.text


# ── P6 ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_toolloop_budget_025_p6_no_credit_cut(monkeypatch, caplog):
    """No-credit flow, flag=False, elapsed 99s > cap 90s → cut fires,
    model text NOT returned, 'Inner loop cut' in log, 'Exemption' absent."""
    import logging
    cerebro = _build_brain_with_catalog()
    caplog.set_level(logging.WARNING, logger="app.services.ai_brain")
    monkeypatch.setattr(ai_brain, "PCC_DEADLINE_BUDGET_S", 120.0)
    monkeypatch.setattr(ai_brain, "PCC_INNER_LOOP_BUDGET_RATIO", 0.75)

    _clock = 99.0
    monkeypatch.setattr("app.services.ai_brain.time.monotonic", lambda: _clock)

    _script = [
        (0.0, _resp_with_fc("search_catalog", {"query": "tvs"})),
        (0.0, _resp_with_text(MODEL_TEXT)),
    ]

    async def _fake_gemini(func, *args, **kwargs):
        nonlocal _clock
        advance, response = _script.pop(0)
        _clock += advance
        return response

    monkeypatch.setattr(cerebro, "_call_gemini_with_retry_async", _fake_gemini)

    res = await cerebro._generate_with_retry_async(
        "Quiero información del catálogo",
        context="",
        prospect_data={"exists": True, "nombre": "Mario", "habeas_data_accepted": True},
        history=[],
        pcc_deadline_start=0.0,
    )

    assert MODEL_TEXT[:20] not in str(res)
    assert "⏱️ [PCC-DEADLINE] Inner loop cut" in caplog.text
    assert "Exemption" not in caplog.text


# ── P7 ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_toolloop_budget_025_p7_absolute_ceiling(monkeypatch, caplog):
    """Elapsed 121s > 120s absolute ceiling (PCC_DEADLINE_BUDGET_S) →
    flag=True but exemption denied → cut fires, text NOT returned."""
    import logging
    cerebro = _build_brain_with_catalog()
    caplog.set_level(logging.WARNING, logger="app.services.ai_brain")
    monkeypatch.setattr(ai_brain, "PCC_DEADLINE_BUDGET_S", 120.0)
    monkeypatch.setattr(ai_brain, "PCC_INNER_LOOP_BUDGET_RATIO", 0.75)

    _clock = 0.0
    monkeypatch.setattr("app.services.ai_brain.time.monotonic", lambda: _clock)

    _script = [
        (60.0, _resp_with_fc("search_catalog", {"query": "moto"})),
        (20.0, _resp_with_fc("calculate_credit_score", {"precio": 5000000, "plazo_meses": 24})),
        (41.0, _resp_with_text(MODEL_TEXT)),
    ]

    async def _fake_gemini(func, *args, **kwargs):
        nonlocal _clock
        advance, response = _script.pop(0)
        _clock += advance
        return response

    monkeypatch.setattr(cerebro, "_call_gemini_with_retry_async", _fake_gemini)

    res = await cerebro._generate_with_retry_async(
        "Hola, quiero una moto a crédito", context="",
        prospect_data={"exists": True, "nombre": "Mario", "habeas_data_accepted": True},
        history=[], pcc_deadline_start=0.0,
    )

    assert MODEL_TEXT[:20] not in str(res)
    assert "⏱️ [PCC-DEADLINE] Inner loop cut" in caplog.text
