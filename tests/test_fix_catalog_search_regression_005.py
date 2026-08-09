"""
Tests de caracterización para [BOT-BUILD-FIX-CATALOG-SEARCH-REGRESSION-005].

Causa raíz (Cloud Logging prod, 2026-07-25 23:09:20Z):
    "🚨 [AI FALLBACK REASON]: Empty Candidate in Turn 2 for Mario"
    Gemini devolvió candidates=[] (safety filter transitorio) justo DESPUÉS de
    recibir los resultados de search_catalog('apache'), y la rama "Empty
    Candidate in Turn" del while-loop degradaba al fallback SIN reintentar,
    sacrificando resultados de herramienta ya obtenidos.

Fix atómico (ai_brain.py, rama in-loop): retry inline patrón FIX-2B con nudge
de sistema; fallback solo si el empty persiste.

Pin:
    T1 — empty candidates TRANSITORIO post-tool → retry inline recupera la
         respuesta y el usuario NO recibe el fallback.
    T2 — empty candidates PERSISTENTE → el fallback se preserva (degradación
         controlada intacta).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.ai_brain import CerebroIA
from app.services.catalog_service import CatalogService


FALLBACK_MARKER = "Se me quedó colgado el sistema"
HONEST_FALLBACK_MARKER = "inconveniente procesando esa búsqueda"

APACHE_ITEM = {
    "id": "apache_rtr_200_4v_fi_abs",
    "name": "TVS APACHE RTR 200 4V XC FI ABS",
    "price": "$13.899.999 (incluye SOAT, Matrícula, y tramites)",
    "raw_price": 13899999,
    "formatted_price": "$13.899.999 (incluye SOAT, Matrícula, y tramites)",
    "category": "motos",
    "image_url": "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos.appspot.com/o/products%2Fapache-200.png?alt=media",
    "link": "https://tiendalasmotos.com/apache-rtr-200",
    "summary": "La 200 más completa de la familia Apache.",
    "searchBy": ["apache", "200", "4v", "fi", "pulsar"],
}


# ---------------------------------------------------------------------------
# Harness de mocks Gemini (patrón test_agentic_loop_async.py)
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


def _fc_search_catalog(query="apache"):
    fc = MagicMock()
    fc.name = "search_catalog"
    fc.args = {"query": query}
    return _MockResponse(candidates=[_MockCandidate(_MockContent([_MockPart(function_call=fc)]))])


def _empty_response():
    # Respuesta vacía de Gemini (safety filter transitorio / glitch de API)
    return _MockResponse(candidates=[])


def _text_response(text):
    return _MockResponse(candidates=[_MockCandidate(_MockContent([_MockPart(text=text)]))])


RECOVERED_TEXT = (
    "¡Con gusto, Mario! La TVS APACHE RTR 200 4V XC FI ABS tiene un precio de "
    "$13.899.999 (incluye SOAT, Matrícula, y tramites).\n"
    "![TVS APACHE RTR 200 4V XC FI ABS](https://firebasestorage.googleapis.com/v0/b/tiendalasmotos.appspot.com/o/products%2Fapache-200.png?alt=media)\n"
    "¿Te gustaría visitar la sede para conocerla en persona?"
)


def _build_cerebro():
    catalog_service = CatalogService()
    cerebro = CerebroIA(catalog_service=catalog_service)
    # Cliente GenAI mockeado: el chat existe pero send_message jamás se invoca
    # porque _call_gemini_with_retry_async va parcheado (se pasa como arg).
    mock_chat = MagicMock()
    mock_chat.send_message = AsyncMock()
    mock_client = MagicMock()
    mock_client.aio.chats.create = MagicMock(return_value=mock_chat)
    cerebro.client = mock_client
    return cerebro, catalog_service


# ---------------------------------------------------------------------------
# T1: Empty candidate TRANSITORIO en turno post-tool → retry inline recupera
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_empty_candidate_in_turn_recovers_via_inline_retry():
    """
    [BOT-BUILD-FIX-CATALOG-SEARCH-REGRESSION-005] Réplica del incidente de prod:
    search_catalog('apache') retorna resultados; al enviarlos de vuelta, Gemini
    responde candidates=[] UNA vez (transitorio); el retry inline obtiene la
    respuesta válida. El usuario recibe la moto, NO el fallback.
    """
    cerebro, catalog_service = _build_cerebro()

    gemini_calls = []

    async def mock_call_gemini(*args, **kwargs):
        gemini_calls.append(args)
        if len(gemini_calls) == 1:
            return _fc_search_catalog("apache")      # Turno 1: tool call
        if len(gemini_calls) == 2:
            return _empty_response()                  # Turno 2: EMPTY transitorio
        return _text_response(RECOVERED_TEXT)         # Retry inline: recuperado

    prospect_data = {"exists": True, "nombre": "Mario", "habeas_data_accepted": False}

    with patch.object(catalog_service, "search_items", return_value=[APACHE_ITEM]), \
         patch.object(cerebro, "_call_gemini_with_retry_async", side_effect=mock_call_gemini), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True):

        res = await cerebro.pensar_respuesta("apache", prospect_data=prospect_data)

    # Aserción 1: el fallback NO se emitió
    assert res is not None
    assert FALLBACK_MARKER not in res, (
        "REGRESIÓN: empty candidate transitorio post-tool degradó al fallback "
        "a pesar de tener resultados de catálogo en mano."
    )

    # Aserción 2: la respuesta recuperada (con la moto) llegó al usuario
    assert "APACHE RTR 200" in res

    # Aserción 3: el retry inline se ejecutó exactamente una vez con el nudge
    assert len(gemini_calls) == 3, (
        f"Se esperaban 3 llamadas a Gemini (inicial + tool-result + retry), hubo {len(gemini_calls)}"
    )
    nudge_msg = gemini_calls[2][1] if len(gemini_calls[2]) > 1 else ""
    assert "respuesta anterior llegó vacía" in nudge_msg


# ---------------------------------------------------------------------------
# T2: Empty candidate PERSISTENTE con resultados de catálogo → fallback honesto
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_empty_candidate_persistent_with_catalog_results_uses_honest_fallback():
    """
    [BOT-BUILD-PCC-LOOP-017] Si Gemini devuelve candidates=[] también en el retry
    inline PERO ya tenemos resultados de catálogo, el fallback debe ser el copy
    honesto de DRIFT-CANON-016 y debe incluir el Top Result (nombre + precio + imagen).
    """
    cerebro, catalog_service = _build_cerebro()

    gemini_calls = []

    async def mock_call_gemini(*args, **kwargs):
        gemini_calls.append(args)
        if len(gemini_calls) == 1:
            return _fc_search_catalog("apache")
        return _empty_response()  # vacío persistente (tool-result Y retry)

    prospect_data = {"exists": True, "nombre": "Mario", "habeas_data_accepted": False}

    with patch.object(catalog_service, "search_items", return_value=[APACHE_ITEM]), \
         patch.object(cerebro, "_call_gemini_with_retry_async", side_effect=mock_call_gemini), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True):

        res = await cerebro.pensar_respuesta("apache", prospect_data=prospect_data)

    assert res is not None
    assert FALLBACK_MARKER not in res, (
        "REGRESIÓN: con resultados de catálogo, el fallback persistente emitió "
        "el copy deshonesto de system_error."
    )
    assert HONEST_FALLBACK_MARKER in res
    assert "APACHE RTR 200" in res
    assert "$13.899.999" in res
    assert "![TVS APACHE RTR 200 4V XC FI ABS](" in res
    # inicial + tool-result (vacío) + retry inline (vacío) → fallback
    assert len(gemini_calls) == 3


# ---------------------------------------------------------------------------
# T3: Empty candidate PERSISTENTE sin resultados → legacy system_error preservado
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_empty_candidate_persistent_no_catalog_results_uses_legacy_fallback():
    """
    [BOT-BUILD-PCC-LOOP-017 / C-21] Sin resultados de catálogo, el path degradado
    conserva el fallback legacy system_error; no hay Top Result que mostrar.
    """
    cerebro, catalog_service = _build_cerebro()

    gemini_calls = []

    async def mock_call_gemini(*args, **kwargs):
        gemini_calls.append(args)
        if len(gemini_calls) == 1:
            return _fc_search_catalog("apache")
        return _empty_response()  # vacío persistente (tool-result Y retry)

    prospect_data = {"exists": True, "nombre": "Mario", "habeas_data_accepted": False}

    with patch.object(catalog_service, "search_items", return_value=[]), \
         patch.object(cerebro, "_call_gemini_with_retry_async", side_effect=mock_call_gemini), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True):

        res = await cerebro.pensar_respuesta("apache", prospect_data=prospect_data)

    assert res is not None
    assert FALLBACK_MARKER in res, (
        "Sin resultados de catálogo, el fallback degradado debe preservar el "
        "copy legacy system_error."
    )
    assert HONEST_FALLBACK_MARKER not in res
    # inicial + tool-result (vacío) + retry inline (vacío) → fallback
    assert len(gemini_calls) == 3
