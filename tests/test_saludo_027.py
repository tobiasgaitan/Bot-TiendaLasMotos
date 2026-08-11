"""
[BOT-BUILD-SALUDO-027] Regression pins for C-23 post-rejection greeting and
canonical closing restoration.

P1-FR-GREETING-CLAUSE: greeting clause wired to skip_greeting in ai_brain.py source
P2-FR-CLOSING-CANONICAL: "¿Con quién tengo el gusto?" present in both frs
P3-E2E-PRIMER-CONTACTO: skip_greeting=False → model text with greeting+closing returned
P4-WARM-OMITE-SALUDO: skip_greeting=True → fr omits greeting clause
P5-FR-CAPTURADO-CON-SALUDO: captured fr payload contains greeting clause
P6-RESET-FORCES-GREETING: _evaluate_skip_greeting returns False after reset marker

Bite tests (manual):
  - comment condicional D4 → P4 FAIL
  - retirar cierre de fr → P2 FAIL
  - revertir frontera (d) → P6 FAIL
"""

import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.services import ai_brain
from app.services.ai_brain import CerebroIA


# ── helpers ──────────────────────────────────────────────────────────────────

PHONE_E164 = "+573192564289"


# ── P1 ───────────────────────────────────────────────────────────────────────

def test_saludo_027_p1_fr_greeting_clause():
    """Greeting clause wired to skip_greeting: the source file contains the
    conditional variable _greeting_clause keyed on skip_greeting, and the
    verbatim phrase 'saluda cálidamente presentándote como Juan Pablo'."""
    src_path = os.path.join(os.path.dirname(__file__), "..", "app", "services", "ai_brain.py")
    with open(src_path) as fh:
        content = fh.read()

    assert "_greeting_clause = (" in content, "Greeting wiring variable missing"
    assert "if not skip_greeting else" in content, (
        "skip_greeting conditional missing from greeting clause wiring"
    )
    assert "saluda cálidamente presentándote como Juan Pablo" in content, (
        "D2 verbatim greeting phrase missing from fr block"
    )


# ── P2 ───────────────────────────────────────────────────────────────────────

def test_saludo_027_p2_fr_closing_canonical():
    """Canonical closing wired as _closing_clause variable, injected into
    both rejection fr sites (1ª and repetida) via concatenation."""
    src_path = os.path.join(os.path.dirname(__file__), "..", "app", "services", "ai_brain.py")
    with open(src_path) as fh:
        content = fh.read()

    assert content.count("+ _closing_clause") >= 2, (
        "_closing_clause must be used in both fr sites (c1 and c2)"
    )
    assert "_closing_clause = (" in content, (
        "_closing_clause variable definition missing"
    )
    assert "¿Con quién tengo el gusto?" in content, (
        "Closing canonical literal missing from source"
    )


# ── P3 ───────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_saludo_027_p3_e2e_primer_contacto(monkeypatch):
    """3-leg C-23 flow with skip_greeting=False.  Model scripted with
    greeting + closing → validation passes → text returned intact."""
    cerebro = CerebroIA(catalog_service=None)
    cerebro.client = MagicMock()
    mock_catalog = MagicMock()
    mock_catalog.search_items.return_value = [
        {"name": "Victory MRX 125", "price": "$5.000.000", "raw_price": 5000000,
         "cc": 125, "category": "motos", "image_url": "https://img.url/mrx125.png",
         "imagen_url": ""}
    ]
    mock_catalog.get_catalog_aliases.return_value = {}
    cerebro._catalog_service = mock_catalog

    COMPLIANT = (
        "¡Hola Mario! Soy Juan Pablo, asesor de Tienda Las Motos. "
        "Ficha Tecnica: Victory MRX 125. 💰 Precio: $5.000.000. "
        "![Victory MRX 125](https://img.url/mrx125.png). "
        "¿Con quién tengo el gusto?"
    )

    async def _mock_generate(*a, **kw):
        return COMPLIANT

    with patch.object(cerebro, "_generate_with_retry_async", side_effect=_mock_generate), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False):
        res = await cerebro.pensar_respuesta(
            "quiero una moto enduro a crédito",
            prospect_data={"exists": True, "nombre": "Mario", "habeas_data_accepted": True, "phone": PHONE_E164},
            skip_greeting=False,
        )

    assert "Ficha Tecnica:" in res
    assert "¿Con quién tengo el gusto?" in res
    assert "saluda cálidamente" not in res   # model text carries the greeting, not the instruction


# ── P4 ───────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_saludo_027_p4_warm_omite_saludo(monkeypatch):
    """skip_greeting=True → the assembled fr payload must NOT contain the
    greeting clause.  Captures the reject_msg sent to chat.send_message."""
    cerebro = CerebroIA(catalog_service=None)
    cerebro.client = MagicMock()
    mock_catalog = MagicMock()
    mock_catalog.search_items.return_value = [
        {"name": "Victory MRX 125", "price": "$5.000.000", "raw_price": 5000000,
         "cc": 125, "category": "motos", "image_url": "https://img.url/mrx125.png",
         "imagen_url": ""}
    ]
    mock_catalog.get_catalog_aliases.return_value = {}
    cerebro._catalog_service = mock_catalog

    captured_frs = []

    _FC = type("_FC", (), {"name": "search_catalog", "args": {"query": "enduro"}})
    _PartFC = type("_Part", (), {"text": "", "function_call": _FC()})
    _ContentFC = type("_Content", (), {"parts": [_PartFC()]})
    _CandidateFC = type("_Candidate", (), {"content": _ContentFC()})
    _RespFC = type("_Resp", (), {"candidates": [_CandidateFC()], "usage_metadata": None})

    _FC2 = type("_FC", (), {"name": "calculate_credit_score", "args": {"precio": 5000000, "plazo_meses": 24}})
    _PartFC2 = type("_Part", (), {"text": "", "function_call": _FC2()})
    _ContentFC2 = type("_Content", (), {"parts": [_PartFC2()]})
    _CandidateFC2 = type("_Candidate", (), {"content": _ContentFC2()})
    _RespFC2 = type("_Resp", (), {"candidates": [_CandidateFC2()], "usage_metadata": None})

    _PartTxt = type("_Part", (), {"text": "texto final", "function_call": None})
    _ContentTxt = type("_Content", (), {"parts": [_PartTxt()]})
    _CandidateTxt = type("_Candidate", (), {"content": _ContentTxt()})
    _RespTxt = type("_Resp", (), {"candidates": [_CandidateTxt()], "usage_metadata": None})

    _script = [_RespFC(), _RespFC2(), _RespTxt()] * 3  # 3 outer attempts × 3 legs

    async def _fake_gemini(func, *args, **kwargs):
        if args:
            payload = args  # skip the func (chat.send_message)
            captured_frs.append(payload)
        return _script.pop(0)

    cerebro._call_gemini_with_retry_async = _fake_gemini

    await cerebro.pensar_respuesta(
        "quiero una moto enduro a crédito",
        prospect_data={"exists": True, "nombre": "Mario", "habeas_data_accepted": True, "phone": PHONE_E164},
        skip_greeting=True,
    )

    # Collect all text content from captured fr payloads
    all_text = ""
    for payload in captured_frs:
        if isinstance(payload, (list, tuple)):
            for item in payload:
                if isinstance(item, str):
                    all_text += item
                elif isinstance(item, (list, tuple)):
                    for sub in item:
                        fr = getattr(sub, "function_response", None)
                        if fr:
                            resp = getattr(fr, "response", {})
                            if isinstance(resp, dict):
                                all_text += str(resp.get("error", ""))
                                all_text += str(resp.get("result", ""))
                        all_text += str(getattr(sub, "text", ""))
                else:
                    fr = getattr(item, "function_response", None)
                    if fr:
                        resp = getattr(fr, "response", {})
                        if isinstance(resp, dict):
                            all_text += str(resp.get("error", ""))
                            all_text += str(resp.get("result", ""))
                    all_text += str(getattr(item, "text", ""))

    assert "saluda cálidamente presentándote como Juan Pablo" not in all_text, (
        "Greeting clause leaked into fr when skip_greeting=True"
    )
    assert "¿Con quién tengo el gusto?" not in all_text, (
        "Closing clause leaked into fr when nombre is known"
    )

    # --- half (b): first contact WITHOUT nombre → both clauses present ---
    captured_frs.clear()
    _script_b = [_RespFC(), _RespFC2(), _RespTxt()] * 3

    async def _fake_gemini_b(func, *args, **kwargs):
        if args:
            captured_frs.append(args)
        return _script_b.pop(0)

    cerebro._call_gemini_with_retry_async = _fake_gemini_b

    await cerebro.pensar_respuesta(
        "quiero una moto enduro a crédito",
        prospect_data={"exists": True, "habeas_data_accepted": True, "phone": PHONE_E164},
        skip_greeting=False,
    )

    all_text_b = ""
    for payload in captured_frs:
        if isinstance(payload, (list, tuple)):
            for item in payload:
                if isinstance(item, str):
                    all_text_b += item
                elif isinstance(item, (list, tuple)):
                    for sub in item:
                        fr = getattr(sub, "function_response", None)
                        if fr:
                            resp = getattr(fr, "response", {})
                            if isinstance(resp, dict):
                                all_text_b += str(resp.get("error", ""))
                                all_text_b += str(resp.get("result", ""))
                        all_text_b += str(getattr(sub, "text", ""))
                else:
                    fr = getattr(item, "function_response", None)
                    if fr:
                        resp = getattr(fr, "response", {})
                        if isinstance(resp, dict):
                            all_text_b += str(resp.get("error", ""))
                            all_text_b += str(resp.get("result", ""))
                    all_text_b += str(getattr(item, "text", ""))

    assert "saluda cálidamente presentándote como Juan Pablo" in all_text_b, (
        "Greeting clause missing from fr when skip_greeting=False and nombre absent"
    )
    assert "¿Con quién tengo el gusto?" in all_text_b, (
        "Closing clause missing from fr when nombre absent"
    )


# ── P5 ───────────────────────────────────────────────────────────────────────

def test_saludo_027_p5_fr_wiring_conditional():
    """Source-level: the greeting clause is appended to reject_msg via
    `+ _greeting_clause` in BOTH rejection fr sites (1ª and repetida)."""
    src_path = os.path.join(os.path.dirname(__file__), "..", "app", "services", "ai_brain.py")
    with open(src_path) as fh:
        content = fh.read()

    count = content.count("+ _greeting_clause")
    assert count >= 2, (
        f"Expected _greeting_clause concatenation in both fr sites, found {count}"
    )


# ── P6 ───────────────────────────────────────────────────────────────────────

def test_saludo_027_p6_reset_forces_greeting():
    """_evaluate_skip_greeting direct:
    (a) warm pre-reset msgs + user '/reset' command + current → False (greeting)
    (b) warm + /reset + 1 post-reset msg <12h → True (skip)
    (c) no reset, recent msg → True (current behavior preserved)"""
    from app.routers.whatsapp import _evaluate_skip_greeting

    pd = {"exists": True}

    # (a) Warm pre-reset history → /reset user command → greeting forced
    hist_a = [
        {"role": "user", "content": "quiero una moto", "timestamp": datetime.now(timezone.utc)},
        {"role": "model", "content": "Claro, te ayudo."},
        {"role": "user", "content": "/reset", "timestamp": datetime.now(timezone.utc)},
        {"role": "user", "content": "quiero una moto a crédito", "timestamp": datetime.now(timezone.utc)},
    ]
    result_a = _evaluate_skip_greeting(hist_a, pd, current_message_saved=True)
    assert result_a is False, (
        f"(a) First turn after reset with warm pre-reset history should greet, got {result_a}"
    )

    # (b) /reset boundary + one legit post-reset msg within 12h → skip
    hist_b = [
        {"role": "user", "content": "quiero una moto", "timestamp": datetime.now(timezone.utc)},
        {"role": "user", "content": "/reset", "timestamp": datetime.now(timezone.utc)},
        {"role": "user", "content": "quiero una moto a crédito", "timestamp": datetime.now(timezone.utc)},
        {"role": "model", "content": "texto respuesta"},
        {"role": "user", "content": "qué cuota queda", "timestamp": datetime.now(timezone.utc)},
    ]
    result_b = _evaluate_skip_greeting(hist_b, pd, current_message_saved=True)
    assert result_b is True, (
        f"(b) Second turn after reset within 12h should skip greeting, got {result_b}"
    )

    # (c) No reset command, recent msg → skip (current behavior)
    hist_c = [
        {"role": "user", "content": "quiero una moto", "timestamp": datetime.now(timezone.utc)},
        {"role": "model", "content": "Claro, te ayudo."},
        {"role": "user", "content": "quiero una moto a crédito", "timestamp": datetime.now(timezone.utc)},
    ]
    result_c = _evaluate_skip_greeting(hist_c, pd, current_message_saved=True)
    assert result_c is True, (
        f"(c) Recent conversation without reset should skip greeting, got {result_c}"
    )
