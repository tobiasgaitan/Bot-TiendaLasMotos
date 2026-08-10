"""
Regression pins for BOT-BUILD-MOTO-CANON-018 Fix B.

Fix B: the PCC-LOOP-017 degraded fallback (and the parallel exception-handler
path) must include the 'Ficha Tecnica:' prefix required by the PCC guard,
along with Top Result, price ($) and Markdown image.
"""

import re
import unicodedata
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai_brain import CerebroIA
from app.services.agentic_loop_service import AgenticOrchestrator


PHONE_E164 = "+573192564289"

TOP_ITEM = {
    "id": "victory_mrx_125",
    "name": "Victory MRX 125",
    "price": "$8.500.000",
    "formatted_price": "$8.500.000",
    "category": "motos",
    "image_url": "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos.appspot.com/o/products%2Fvictory-mrx-125.png?alt=media",
    "link": "https://tiendalasmotos.com/victory-mrx-125",
    "summary": "La doble propósito más vendida.",
    "searchBy": ["doble proposito", "enduro", "todo terreno"],
}


class _FakeCatalog:
    def __init__(self, items):
        self._items = items

    @staticmethod
    def _normalize_item_id_key(raw: str) -> str:
        if not raw or not isinstance(raw, str):
            return ""
        s = unicodedata.normalize("NFKC", raw).lower().strip()
        s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
        s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
        return s

    def search_items(self, query: str, trace_id: str = None):
        q = query.lower()
        matches = []
        for item in self._items:
            name = str(item.get("name", "")).lower()
            search_by = [str(s).lower() for s in item.get("searchBy", [])]
            if q in name or any(q in s for s in search_by):
                matches.append(item)
        return matches

    def get_catalog_aliases(self):
        return {
            "doble proposito": ["doble proposito", "enduro", "todo terreno"],
        }


def _build_cerebro():
    catalog = _FakeCatalog([TOP_ITEM])
    cerebro = CerebroIA(catalog_service=catalog)
    cerebro.client = MagicMock()
    return cerebro, catalog


# ---------------------------------------------------------------------------
# PCC-A — _build_pcc_fallback includes prefix + Top Result + price + image
# ---------------------------------------------------------------------------
def test_moto_canon_018_pcc_a_helper_includes_prefix():
    cerebro, _ = _build_cerebro()
    res = cerebro._build_pcc_fallback(
        "¿Qué moto me recomiendas?",
        [],
        top_name="Victory MRX 125",
        top_image="https://example.com/mrx125.jpg",
        top_price="$8.500.000",
    )
    assert "Ficha Tecnica: Victory MRX 125" in res
    assert "⭐ Recomendación TOP: Victory MRX 125" in res
    assert "💰 Precio: $8.500.000" in res
    assert "![Victory MRX 125](https://example.com/mrx125.jpg)" in res


# ---------------------------------------------------------------------------
# PCC-B — run_checker accepts the fallback as PCC-compliant
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_moto_canon_018_pcc_b_run_checker_accepts_fallback():
    """With moto_interest set post-stash, the fallback must satisfy PCC."""
    cerebro, _ = _build_cerebro()
    fallback = cerebro._build_pcc_fallback(
        "¿Qué moto me recomiendas?",
        [],
        top_name="Victory MRX 125",
        top_image="https://example.com/mrx125.jpg",
        top_price="$8.500.000",
    )
    prospect_data = {
        "moto_interest": "Victory MRX 125",
        "_catalog_top_name": "Victory MRX 125",
    }
    orchestrator = AgenticOrchestrator()
    validation = orchestrator.run_checker(
        fallback,
        is_catalog_query=True,
        prospect_data=prospect_data,
        user_prompt="quisiera una moto doble propósito a crédito",
    )
    assert validation["success"] is True, validation.get("report", {})


# ---------------------------------------------------------------------------
# PCC-C — 'Sin descripción' is sanitized to avoid has_sin_descripcion_fallback trap
# ---------------------------------------------------------------------------
def test_moto_canon_018_pcc_c_sin_descripcion_sanitized():
    cerebro, _ = _build_cerebro()
    res = cerebro._build_pcc_fallback(
        "¿Qué moto me recomiendas?",
        [],
        top_name="Sin descripción",
        top_image="https://example.com/mrx125.jpg",
        top_price="$8.500.000",
    )
    assert "Ficha Tecnica: Sin descripción" not in res
    assert "Ficha Tecnica: (información no disponible)" in res


# ---------------------------------------------------------------------------
# Mock helpers for E2E pins
# ---------------------------------------------------------------------------
class _MockPart:
    def __init__(self, function_call=None, text=None):
        self.function_call = function_call
        self.text = text


class _MockContent:
    def __init__(self, parts):
        self.parts = parts


class _MockCandidate:
    def __init__(self, content):
        self.content = content


class _MockResponse:
    def __init__(self, candidates):
        self.candidates = candidates


def _fc_search_catalog(query="doble proposito"):
    fc = MagicMock()
    fc.name = "search_catalog"
    fc.args = {"query": query}
    return _MockResponse(candidates=[_MockCandidate(_MockContent([_MockPart(function_call=fc)]))])


def _text_response(text):
    return _MockResponse(candidates=[_MockCandidate(_MockContent([_MockPart(text=text)]))])


# ---------------------------------------------------------------------------
# PCC-E2E — Full post-reset flow ends with prefixed fallback
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_moto_canon_018_pcc_e2e_post_reset_fallback_has_prefix():
    """End-to-end: /reset-like empty prospect + category+credit query →
    search_catalog stashes top → Gemini returns empty text on attempt 1
    (simulating a hung/empty generation) → _generate_with_retry_async hits
    the empty-candidate path and returns a decorated fallback with
    'Ficha Tecnica:' prefix via _build_pcc_fallback."""
    cerebro, catalog = _build_cerebro()
    gemini_calls = []

    async def mock_call_gemini(*args, **kwargs):
        gemini_calls.append(args)
        if len(gemini_calls) == 1:
            return _fc_search_catalog("doble proposito")
        # All subsequent calls return an EMPTY text response, forcing PCC to
        # exhaust its attempts and degrade to the honest fallback.
        return _text_response("")

    prospect_data = {"exists": True, "nombre": "Mario", "habeas_data_accepted": True}

    with patch.object(catalog, "search_items", return_value=[TOP_ITEM]), \
         patch.object(cerebro, "_call_gemini_with_retry_async", side_effect=mock_call_gemini), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True):

        res = await cerebro.pensar_respuesta(
            "Hola, quisiera una moto doble propósito a crédito",
            prospect_data=prospect_data,
        )

    assert "Ficha Tecnica: Victory MRX 125" in res
    assert "⭐ Recomendación TOP: Victory MRX 125" in res
    assert "$8.500.000" in res
    assert "![Victory MRX 125](" in res
    assert prospect_data.get("_catalog_top_name") == "Victory MRX 125"


# ---------------------------------------------------------------------------
# PCC-EXC-E2E — Exception-handler fallback path also includes prefix
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_moto_canon_018_pcc_exc_e2e_exception_handler_has_prefix():
    """If text extraction from the Gemini response raises an exception after
    search_catalog succeeded, the exception-handler fallback must still emit
    the 'Ficha Tecnica:' prefix."""
    cerebro, catalog = _build_cerebro()

    class _BadResponse:
        """Response whose candidates[0].content.parts[0].text raises."""
        class _Candidate:
            class _Content:
                class _Part:
                    @property
                    def text(self):
                        raise RuntimeError("forced extraction failure")
                    function_call = None
                parts = [_Part()]
            content = _Content()
        candidates = [_Candidate()]

    call_count = 0

    async def mock_call_gemini(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _fc_search_catalog("doble proposito")
        return _BadResponse()

    prospect_data = {"exists": True, "nombre": "Mario", "habeas_data_accepted": True}

    with patch.object(catalog, "search_items", return_value=[TOP_ITEM]), \
         patch.object(cerebro, "_call_gemini_with_retry_async", side_effect=mock_call_gemini), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True):

        res = await cerebro._generate_with_retry_async(
            "Hola, quisiera una moto doble propósito a crédito",
            context="",
            prospect_data=prospect_data,
            history=[],
        )

    assert "Ficha Tecnica: Victory MRX 125" in res
    assert "⭐ Recomendación TOP: Victory MRX 125" in res
    assert "$8.500.000" in res
