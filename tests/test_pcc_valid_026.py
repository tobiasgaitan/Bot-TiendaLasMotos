"""
[BOT-BUILD-PCC-VALID-026] Regression pins for C-23 post-rejection text
failures under PCC validation (CATALOG_VALIDATION_FAIL).

P1-REPRO-VALIDADOR:  run_checker rejects text without 'Ficha Tecnica:' prefix
P2-NUDGE-CONTRATO:   the 4 guide texts now contain 'Ficha Tecnica:' demand
P3-E2E-CUMPLE:       C-23 3-leg flow with compliant text → validation passes
P4-SALVAGE-DETERM:   C-23 rejection + validation fail → canonical PASO 1 caption
P5-SALVAGE-NO-CRED:  no-credit flow → existing _build_pcc_fallback preserved
P6-NULL-PROSPECT-DATA: prospect_data=None must not crash on unguarded .pop() (locks R1)

Bite tests (manual — not pytest pins):
  - comment out salvage branch → P4 FAIL → restore → green
  - remove 'Ficha Tecnica:' from a1-a4 → P2/P3 FAIL → restore → green
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from app.services import ai_brain
from app.services.ai_brain import CerebroIA
from app.services.agentic_loop_service import AgenticOrchestrator


PHONE_E164 = "+573192564289"
PROSPECT_EXAMPLE = {"exists": True, "nombre": "Mario", "habeas_data_accepted": True, "phone": PHONE_E164}


# ── helpers ──────────────────────────────────────────────────────────────────

def _build_mock_cerebro():
    cerebro = CerebroIA(catalog_service=None)
    cerebro.client = MagicMock()
    return cerebro


_FC = type("_FC", (), {"name": "search_catalog", "args": {"query": "moto"}})
_FC_CREDIT = type("_FC", (), {"name": "calculate_credit_score", "args": {"precio": 5000000, "plazo_meses": 24}})


def _resp_with_fc(fc_obj):
    _Part = type("_Part", (), {"text": "", "function_call": fc_obj})
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


COMPLIANT_TEXT = "¡Hola Mario! Ficha Tecnica: Victory MRX 125 💰 Precio: $5.000.000 ![Victory MRX 125](https://img.url/mrx125.png)"
NON_COMPLIANT_TEXT = "¡Hola Mario! ⭐ TOP RESULT: Victory MRX 125. Precio: $5.000.000 ![Victory MRX 125](https://img.url/mrx125.png)"


# ── P1 ───────────────────────────────────────────────────────────────────────

def test_pcc_valid_026_p1_repro_validator():
    """run_checker with text missing 'Ficha Tecnica:' → CATALOG_VALIDATION_FAIL;
    with prefix → success. purchase_intent triggers has_ficha requirement."""
    orch = AgenticOrchestrator.__new__(AgenticOrchestrator)
    pd = {"moto_interest": "Victory MRX 125", "phone": PHONE_E164}
    prompt = "quiero una moto enduro a crédito"

    r_fail = orch.run_checker(NON_COMPLIANT_TEXT, is_catalog_query=True, prospect_data=pd, user_prompt=prompt, trace_id="026-p1")
    assert r_fail["success"] is False
    assert r_fail["report"]["scenario_key"] == "CATALOG_VALIDATION_FAIL"

    r_ok = orch.run_checker(COMPLIANT_TEXT, is_catalog_query=True, prospect_data=pd, user_prompt=prompt, trace_id="026-p1")
    assert r_ok["success"] is True


# ── P2 ───────────────────────────────────────────────────────────────────────

def test_pcc_valid_026_p2_nudge_contract():
    """The 4 guide texts injected by palanca (a) all demand the 'Ficha Tecnica:'
    literal prefix.  Sources extracted from ai_brain.py."""
    import os
    src = os.path.join(os.path.dirname(__file__), "..", "app", "services", "ai_brain.py")
    with open(src) as fh:
        content = fh.read()

    # a1: rejection fr (first)
    assert "la línea literal 'Ficha Tecnica: <modelo>' tal como la devolvió" in content, "a1 missing"

    # a2: rejection fr (repeated)
    assert "y la línea literal 'Ficha Tecnica: <modelo>'. Sin más" in content, "a2 missing"

    # a3: empty-candidate nudge
    assert "y el prefijo literal 'Ficha Tecnica:'.]" in content, "a3 missing"

    # a4: forced_instruction retry
    assert "y el prefijo literal 'Ficha Tecnica: <modelo>' tal como la devolvió el catálogo." in content, "a4 missing"


# ── P3 ───────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pcc_valid_026_p3_e2e_cumple(monkeypatch):
    """3-leg C-23 flow with _generate_with_retry_async returning COMPLIANT text
    → pensar_respuesta validation passes → text returned."""
    cerebro = _build_mock_cerebro()

    async def _mock_generate(*a, **kw):
        return COMPLIANT_TEXT

    with patch.object(cerebro, "_generate_with_retry_async", side_effect=_mock_generate), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False):
        res = await cerebro.pensar_respuesta(
            "quiero una moto enduro a crédito",
            prospect_data=dict(PROSPECT_EXAMPLE),
        )

    assert "Ficha Tecnica:" in res
    assert "$" in res
    assert "Victory MRX 125" in res
    assert "¿Con quién tengo el gusto?" not in str(res)  # model text, not salvage


# ── P4 ───────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pcc_valid_026_p4_salvage_determinista(monkeypatch):
    """pensar_respuesta with reject flag stashed + non-compliant text + Top Result
    → max attempts → canonical PASO 1 caption (Ficha Tecnica:, $, image, NO '¡Qué pena!')."""
    cerebro = _build_mock_cerebro()
    mock_catalog = MagicMock()
    mock_catalog.search_items.return_value = [
        {"name": "Victory MRX 125", "price": "$5.000.000", "raw_price": 5000000, "cc": 125, "category": "motos", "image_url": "https://img.url/mrx125.png", "imagen_url": ""}
    ]
    mock_catalog.get_catalog_aliases.return_value = {}
    cerebro._catalog_service = mock_catalog

    async def _mock_generate(*a, **kw):
        return NON_COMPLIANT_TEXT

    pd = dict(PROSPECT_EXAMPLE)
    pd["_catalog_top_name"] = "Victory MRX 125"
    pd["_catalog_top_image"] = "https://img.url/mrx125.png"
    pd["_credit_tool_rejected_this_turn"] = True

    monkeypatch.setattr(ai_brain, "PCC_DEADLINE_BUDGET_S", 999.0)
    monkeypatch.setattr(ai_brain, "PCC_INNER_LOOP_BUDGET_RATIO", 0.75)

    with patch.object(cerebro, "_generate_with_retry_async", side_effect=_mock_generate), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False):
        res = await cerebro.pensar_respuesta(
            "quiero una moto enduro a crédito",
            prospect_data=pd,
        )

    assert "Ficha Tecnica:" in res
    assert "$" in res
    assert "Victory MRX 125" in res
    assert "¿Con quién tengo el gusto?" in res
    assert "¡Qué pena!" not in res
    assert "Soy Juan Pablo" in res


# ── P5 ───────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pcc_valid_026_p5_salvage_no_credit(monkeypatch):
    """No rejection flag → max attempts → existing _build_pcc_fallback path
    (contains 'Ficha Tecnica:' + price, starts with '¡Qué pena!')."""
    cerebro = _build_mock_cerebro()
    mock_catalog = MagicMock()
    mock_catalog.search_items.return_value = [
        {"name": "Victory MRX 125", "price": "$5.000.000", "raw_price": 5000000, "cc": 125, "category": "motos", "image_url": "https://img.url/mrx125.png", "imagen_url": ""}
    ]
    mock_catalog.get_catalog_aliases.return_value = {}
    cerebro._catalog_service = mock_catalog

    async def _mock_generate(*a, **kw):
        return NON_COMPLIANT_TEXT

    pd = dict(PROSPECT_EXAMPLE)
    pd["_catalog_top_name"] = "Victory MRX 125"
    pd["_catalog_top_image"] = "https://img.url/mrx125.png"

    monkeypatch.setattr(ai_brain, "PCC_DEADLINE_BUDGET_S", 999.0)
    monkeypatch.setattr(ai_brain, "PCC_INNER_LOOP_BUDGET_RATIO", 0.75)

    with patch.object(cerebro, "_generate_with_retry_async", side_effect=_mock_generate), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False):
        res = await cerebro.pensar_respuesta(
            "quiero una moto enduro a crédito",
            prospect_data=pd,
        )

    assert "Ficha Tecnica:" in res
    assert "¡Qué pena!" in res
    assert "Soy Juan Pablo" not in res


# ── P6 ───────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pcc_valid_026_p6_null_prospect_data(monkeypatch):
    """pensar_respuesta with prospect_data=None must not crash on the max-attempts
    fallback path.  Locks R1 (unguarded pop fix)."""
    cerebro = _build_mock_cerebro()

    async def _mock_generate(*a, **kw):
        return NON_COMPLIANT_TEXT

    monkeypatch.setattr(ai_brain, "PCC_DEADLINE_BUDGET_S", 999.0)
    monkeypatch.setattr(ai_brain, "PCC_INNER_LOOP_BUDGET_RATIO", 0.75)

    with patch.object(cerebro, "_generate_with_retry_async", side_effect=_mock_generate), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False):
        # Must not raise AttributeError
        res = await cerebro.pensar_respuesta(
            "quiero una moto enduro a crédito",
            prospect_data=None,
        )

    assert "¡Qué pena!" in res
