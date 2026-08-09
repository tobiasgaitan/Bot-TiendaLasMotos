"""
Regression pins for BOT-BUILD-PCC-LOOP-017.

Cierra el bucle del guard de PCC y conecta el path degradado al fallback honesto
de DRIFT-CANON-016 con recomendación determinista del Top Result.

Pins:
    PIN-1 — Turn 2 post-tool con resultados válidos + empty-candidate transitorio
            → retry inline recupera y el usuario recibe TOP RESULT + precio + imagen.
    PIN-2 — El LLM re-invoca search_catalog en turns 2 y 3 → max_turns agotado
            → fallback honesto (nunca el copy viejo "Se me quedó colgado el sistema").
    PIN-3 — La salida degradada contiene _catalog_top_name, precio ($) e imagen Markdown.
"""

import re
import unicodedata
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai_brain import CerebroIA


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

FALLBACK_MARKER = "Se me quedó colgado el sistema"
HONEST_FALLBACK_MARKER = "inconveniente procesando esa búsqueda"


# ---------------------------------------------------------------------------
# Harness de mocks Gemini (patrón test_fix_catalog_search_regression_005.py)
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


def _empty_response():
    return _MockResponse(candidates=[])


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
            "automatica": ["automatica", "scooter", "city"],
            "sport": ["sport", "calle"],
        }


def _build_cerebro():
    catalog = _FakeCatalog([TOP_ITEM])
    cerebro = CerebroIA(catalog_service=catalog)
    cerebro.client = MagicMock()
    return cerebro, catalog


# ---------------------------------------------------------------------------
# PIN-1 — Turn 2 post-tool con resultados válidos + empty-candidate transitorio
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_pcc_loop_pin_t2_post_tool_empty_candidate_recovers_with_top_result():
    """
    [BOT-BUILD-PCC-LOOP-017 / PIN-1] El retry inline tras un empty-candidate
    transitorio post-tool-response debe producir una respuesta final con el
    TOP RESULT, precio ($) e imagen Markdown. No debe emitir ningún fallback.
    """
    cerebro, catalog = _build_cerebro()
    gemini_calls = []

    async def mock_call_gemini(*args, **kwargs):
        gemini_calls.append(args)
        if len(gemini_calls) == 1:
            return _fc_search_catalog("doble proposito")
        if len(gemini_calls) == 2:
            return _empty_response()  # transitorio
        return _text_response(
            "¡Con gusto! La Victory MRX 125 tiene un precio de $8.500.000.\n"
            "![Victory MRX 125](https://firebasestorage.googleapis.com/v0/b/tiendalasmotos.appspot.com/o/products%2Fvictory-mrx-125.png?alt=media)\n"
            "¿Te gustaría calcular el crédito?"
        )

    prospect_data = {"exists": True, "nombre": "Mario", "habeas_data_accepted": True}

    with patch.object(catalog, "search_items", return_value=[TOP_ITEM]), \
         patch.object(cerebro, "_call_gemini_with_retry_async", side_effect=mock_call_gemini), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True), \
         patch("app.services.agentic_loop_service.AgenticOrchestrator.run_checker", return_value={"success": True}):

        res = await cerebro.pensar_respuesta(
            "Hola, quisiera una moto doble propósito a crédito",
            prospect_data=prospect_data,
        )

    assert res is not None
    assert FALLBACK_MARKER not in res, (
        "REGRESIÓN: Turn 2 con resultados válidos degradó al fallback viejo."
    )
    assert HONEST_FALLBACK_MARKER not in res, (
        "El retry inline recuperó la respuesta; no debe emitir copy de degradado."
    )
    assert "Victory MRX 125" in res
    assert "$8.500.000" in res
    assert "![Victory MRX 125](" in res


# ---------------------------------------------------------------------------
# PIN-2 — Re-invocación de search_catalog hasta max_turns → fallback honesto
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_pcc_loop_pin_max_turns_reinvocation_uses_honest_fallback():
    """
    [BOT-BUILD-PCC-LOOP-017 / PIN-2] Si el LLM re-invoca search_catalog
    repetidamente en lugar de construir la recomendación, al agotarse max_turns
    el path degradado debe usar el copy honesto de empty_candidate, NUNCA el
    copy legacy de system_error.
    """
    cerebro, catalog = _build_cerebro()
    gemini_calls = []

    async def mock_call_gemini(*args, **kwargs):
        gemini_calls.append(args)
        # El LLM se niega a generar texto y sigue invocando search_catalog.
        return _fc_search_catalog("doble proposito")

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

    assert res is not None
    assert FALLBACK_MARKER not in res, (
        "REGRESIÓN: el path degradado por re-invocación emitió el copy viejo."
    )
    assert HONEST_FALLBACK_MARKER in res


# ---------------------------------------------------------------------------
# PIN-3 — Salida degradada contiene Top Result (nombre + precio + imagen)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_pcc_loop_pin_degraded_fallback_includes_top_result():
    """
    [BOT-BUILD-PCC-LOOP-017 / PIN-3] El fallback degradado debe incluir la
    recomendación determinista del TOP RESULT: nombre, precio ($) e imagen Markdown.
    """
    cerebro, catalog = _build_cerebro()

    async def mock_call_gemini(*args, **kwargs):
        return _fc_search_catalog("doble proposito")

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

    assert "Victory MRX 125" in res
    assert "$8.500.000" in res
    assert "![Victory MRX 125](https://firebasestorage.googleapis.com/v0/b/tiendalasmotos.appspot.com/o/products%2Fvictory-mrx-125.png?alt=media)" in res
