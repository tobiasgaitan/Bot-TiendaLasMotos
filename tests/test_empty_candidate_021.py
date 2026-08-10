"""
Pins de BOT-BUILD-EMPTY-CANDIDATE-021 (v10.63.0).

P-HAPPY:   /reset → "doble propósito a crédito" → Turn 2 produce PASO 1
           completo (saludo, precio $, imagen ![...], Ficha Tecnica:),
           SIN fallback, SIN disculpa, y el function_response porta la
           directriz anti-deadlock.

P-RECOVERY: Turn 2 vacío UNA vez → retry reparado (payload contiene
            function_response + nudge) → PASO 1 completo sin fallback.

P-EGRESS-💰: fallback forzado → pipeline de egreso real (enforce_urls +
             extracción de imagen + enforce_length) → el caption final
             contiene "💰 Precio: $..." poblado.
"""

import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai_brain import CerebroIA
from app.services.catalog_service import CatalogService


# ──────────────── fixtures ────────────────

PHONE_E164 = "+573192564289"

APACHE_ITEM = {
    "id": "apache_200",
    "name": "TVS APACHE RTR 200 4V XC FI ABS",
    "price": "$13.899.999",
    "formatted_price": "$13.899.999 (incluye SOAT, Matrícula, y tramites)",
    "image_url": "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos.appspot.com/o/products%2Fapache-200.png?alt=media",
    "category": "deportiva",
    "searchBy": ["apache"],
    "summary": "La deportiva TVS Apache 200.",
}

HAPPY_TEXT = (
    "¡Hola! Soy Juan Pablo, tu asesor de Auteco Las Motos. ¡Qué gusto!\n"
    "Para doble propósito te recomiendo la VICTORY MRX 125.\n"
    "![VICTORY MRX 125](https://img/mrx125.png)\n"
    "Precio: $9.969.000. Ficha Tecnica: VICTORY MRX 125. ¿Con quién tengo el gusto?"
)


class _MockPart:
    def __init__(self, function_call=None, text=None, function_response=None):
        self.function_call = function_call
        self.text = text
        self.function_response = function_response


class _MockContent:
    def __init__(self, parts):
        self.parts = parts


class _MockCandidate:
    def __init__(self, content):
        self.content = content


class _MockResponse:
    def __init__(self, candidates):
        self.candidates = candidates


def _fc_search_catalog(query="enduro"):
    fc = MagicMock()
    fc.name = "search_catalog"
    fc.args = {"query": query}
    return _MockResponse(candidates=[_MockCandidate(_MockContent([_MockPart(function_call=fc)]))])


def _text_response(text):
    return _MockResponse(candidates=[_MockCandidate(_MockContent([_MockPart(text=text)]))])


def _empty_response():
    return _MockResponse(candidates=[])


def _build_cerebro():
    catalog_service = CatalogService()
    cerebro = CerebroIA(catalog_service=catalog_service)
    mock_chat = MagicMock()
    mock_chat.send_message = AsyncMock()
    mock_client = MagicMock()
    mock_client.aio.chats.create = MagicMock(return_value=mock_chat)
    cerebro.client = mock_client
    return cerebro, catalog_service


# ──────────────── P-HAPPY ────────────────

@pytest.mark.asyncio
async def test_p_happy_e2e_post_reset_credit_completes_paso1():
    """
    /reset → "Hola, quisiera una moto doble propósito a crédito":
    Turn 1 → search_catalog; Turn 2 → PASO 1 completo (greeting + $ + ![] +
    Ficha Tecnica), SIN disculpa, y el function_response porta la directriz
    anti-deadlock.
    """
    cerebro, catalog_service = _build_cerebro()

    pros_data = {
        "exists": True,
        "nombre": "Mario",
        "habeas_data_accepted": True,
        "phone": PHONE_E164,
    }

    gemini_calls = []

    async def mock_gemini(*args, **kwargs):
        gemini_calls.append(args)
        if len(gemini_calls) == 1:
            return _fc_search_catalog("enduro")
        return _text_response(HAPPY_TEXT)

    with patch.object(catalog_service, "search_items", return_value=[APACHE_ITEM]), \
         patch.object(cerebro, "_call_gemini_with_retry_async", side_effect=mock_gemini), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True):

        res = await cerebro.pensar_respuesta(
            "Hola, quisiera una moto doble propósito a crédito",
            prospect_data=pros_data,
        )

    # PASO 1 completo: saludo + moto + precio con $ + imagen + Ficha + pregunta
    assert re.search(r"\$\d[\d.,]+", res), (
        f"PASO 1 debe tener precio con $: '{res[:300]}'"
    )
    assert "![" in res, "PASO 1 debe tener imagen Markdown"
    assert "Ficha Tecnica" in res, "PASO 1 debe tener prefijo Ficha Tecnica"
    FALLBACK_MARKER = "¡Qué pena! Tuve un inconveniente procesando esa búsqueda"
    assert FALLBACK_MARKER not in res, "Happy path NO debe degradar al fallback"

    # Sin empty candidate
    assert len(gemini_calls) == 2, (
        f"Sin empty → 2 llamadas (inicial + tool-result), hubo {len(gemini_calls)}"
    )
    # [BOT-BUILD-EMPTY-CANDIDATE-021-RF / Hallazgo 1] Pin anti-deadlock:
    # el function_response enviado en Turn 2 DEBE contener la directriz
    # cuando el texto menciona crédito.
    _t2_payload = gemini_calls[1][1] if len(gemini_calls[1]) > 1 else None
    assert isinstance(_t2_payload, list), f"Turn-2 payload debe ser lista, es {type(_t2_payload)}"
    _fr_texts = []
    for _p in _t2_payload:
        if hasattr(_p, "function_response") and _p.function_response:
            _r = _p.function_response.response
            if isinstance(_r, dict) and _r.get("result"):
                _fr_texts.append(str(_r["result"]))
    _fr_joined = " ".join(_fr_texts)
    assert "DIRECTRIZ DE TURNO" in _fr_joined, (
        f"Fix-2: function_response debe portar la directriz anti-deadlock. "
        f"Payload repr: {_fr_joined[:400]}"
    )


# ──────────────── P-RECOVERY ────────────────

@pytest.mark.asyncio
async def test_p_recovery_empty_once_retry_recovers():
    """
    Turn 2 vacío UNA vez → retry reparado (payload = function_response + nudge)
    → PASO 1 completo sin fallback. Aserta que el payload del retry contiene
    tanto el function_response como el texto del nudge.
    """
    cerebro, catalog_service = _build_cerebro()

    pros_data = {
        "exists": True,
        "nombre": "Mario",
        "habeas_data_accepted": True,
        "phone": PHONE_E164,
    }

    gemini_calls = []

    async def mock_gemini(*args, **kwargs):
        gemini_calls.append(args)
        if len(gemini_calls) == 1:
            return _fc_search_catalog("enduro")
        if len(gemini_calls) == 2:
            return _empty_response()
        return _text_response(HAPPY_TEXT)

    with patch.object(catalog_service, "search_items", return_value=[APACHE_ITEM]), \
         patch.object(cerebro, "_call_gemini_with_retry_async", side_effect=mock_gemini), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True):

        res = await cerebro.pensar_respuesta(
            "Hola, quisiera una moto doble propósito a crédito",
            prospect_data=pros_data,
        )

    assert re.search(r"\$\d[\d.,]+", res), (
        f"PASO 1 recuperado debe tener precio con $: '{res[:300]}'"
    )
    FALLBACK_MARKER = "¡Qué pena! Tuve un inconveniente procesando esa búsqueda"
    assert FALLBACK_MARKER not in res, "La recuperación debe evitar el fallback"
    assert len(gemini_calls) == 3, (
        f"3 llamadas (inicial + tool-result + retry reparado), hubo {len(gemini_calls)}"
    )

    retry_payload = gemini_calls[2][1] if len(gemini_calls[2]) > 1 else None
    assert isinstance(retry_payload, list), (
        f"Payload del retry debe ser lista de Parts, es {type(retry_payload)}"
    )
    texts_in_payload = [
        p.text for p in retry_payload if hasattr(p, 'text') and p.text
    ]
    nudge_text = "".join(texts_in_payload)
    assert "respuesta anterior llegó vacía" in nudge_text, (
        f"Nudge no encontrado en payload: '{nudge_text[:200]}'"
    )
    has_function_response = any(
        hasattr(p, "function_response") and p.function_response
        for p in retry_payload
    )
    assert has_function_response, (
        "Payload del retry reparado DEBE contener el function_response del catálogo"
    )


# ──────────────── P-EGRESS-💰 ────────────────

def test_p_egress_fallback_preserves_precio():
    """
    El fallback construido por _build_pcc_fallback, tras pasar por el
    pipeline de egreso real (enforce_urls → extracción de imagen →
    enforce_length al caption), conserva "💰 Precio: $..." poblado.

    NOTA (B4): este test es una réplica inline deliberada del pipeline
    unificado de egreso (whatsapp.py _process_and_send_egress_message
    :2446-2474 + _send_whatsapp_message :2763-2764). Si el orden o los
    regex del pipeline real cambian, esta réplica debe actualizarse en
    sincronía; no es un test de integración que consuma la función real.
    """
    from app.services import egress_guard_service as egress_guard

    brain = CerebroIA(catalog_service=None)
    FAKE_IMG = "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos.appspot.com/o/products%2Fmrx-125.png?alt=media"
    FAKE_PRICE = "$9.969.000 (incluye SOAT, Matrícula, y tramites)"

    fb = brain._build_pcc_fallback(
        "Hola, quisiera una moto doble propósito a crédito",
        [],
        top_name="VICTORY MRX 125",
        top_image=FAKE_IMG,
        top_price=FAKE_PRICE,
    )

    # Réplica exacta del pipeline unificado de egreso (whatsapp.py)
    txt, _rep = egress_guard.enforce_urls(fb)
    markdown_pattern = r'!?\[[\s\S]*?\]\s*\((https?://[^\s\)]+)\)'
    images = re.findall(markdown_pattern, txt)
    caption = re.sub(markdown_pattern, '', txt).strip()
    caption = egress_guard.enforce_length(caption)

    assert f"💰 Precio: {FAKE_PRICE}" in caption, (
        f"Tras egreso, 💰 Precio debe sobrevivir. Caption='{caption}'"
    )
    assert "Ficha Tecnica: VICTORY MRX 125" in caption, (
        "Ficha Tecnica debe sobrevivir"
    )
    assert FAKE_IMG not in caption, (
        "La imagen Markdown debe haber sido extraída del caption"
    )
    assert images, "Debe detectarse al menos una imagen para foto"
    assert images[0] == FAKE_IMG, (
        "La imagen extraída debe ser la del fallback"
    )


# ──────────────── P-NO-CREDIT ────────────────

@pytest.mark.asyncio
async def test_p_no_credit_no_directive():
    """
    Sin keyword crediticia en el turno → el function_response de
    search_catalog NO debe contener la directriz anti-deadlock
    (la directriz es condicional al dead-lock PASO 2, que solo
    ocurre con mención crediticia).
    """
    cerebro, catalog_service = _build_cerebro()

    pros_data = {
        "exists": True,
        "nombre": "Mario",
        "habeas_data_accepted": True,
        "phone": PHONE_E164,
    }

    gemini_calls = []

    async def mock_gemini(*args, **kwargs):
        gemini_calls.append(args)
        if len(gemini_calls) == 1:
            return _fc_search_catalog("enduro")
        return _text_response(HAPPY_TEXT)

    with patch.object(catalog_service, "search_items", return_value=[APACHE_ITEM]), \
         patch.object(cerebro, "_call_gemini_with_retry_async", side_effect=mock_gemini), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True):

        res = await cerebro.pensar_respuesta(
            "Hola, quisiera una moto doble propósito",
            prospect_data=pros_data,
        )

    assert "¡Qué pena!" not in res, "Happy path sin crédito NO debe degradar"
    assert len(gemini_calls) == 2

    _t2_payload = gemini_calls[1][1] if len(gemini_calls[1]) > 1 else None
    assert isinstance(_t2_payload, list)
    _fr_texts = []
    for _p in _t2_payload:
        if hasattr(_p, "function_response") and _p.function_response:
            _r = _p.function_response.response
            if isinstance(_r, dict) and _r.get("result"):
                _fr_texts.append(str(_r["result"]))
    _fr_joined = " ".join(_fr_texts)
    assert "DIRECTRIZ DE TURNO" not in _fr_joined, (
        f"Sin keyword crediticia, el function_response NO debe portar la directriz. "
        f"Payload repr: {_fr_joined[:400]}"
    )


# ──────────────── P-FINANCIACION ────────────────

@pytest.mark.asyncio
async def test_p_financiacion_triggers_directive():
    """
    [BOT-BUILD-EMPTY-CANDIDATE-021-RF2 / R6] Hardening de keywords: la
    tupla C-22.2 usa 'financia' para cubrir financiar/financiación/
    financiamiento como substring. Con 'financiación' en el texto, el
    function_response DEBE portar la directriz anti-deadlock.
    """
    cerebro, catalog_service = _build_cerebro()

    pros_data = {
        "exists": True,
        "nombre": "Mario",
        "habeas_data_accepted": True,
        "phone": PHONE_E164,
    }

    gemini_calls = []

    async def mock_gemini(*args, **kwargs):
        gemini_calls.append(args)
        if len(gemini_calls) == 1:
            return _fc_search_catalog("enduro")
        return _text_response(HAPPY_TEXT)

    with patch.object(catalog_service, "search_items", return_value=[APACHE_ITEM]), \
         patch.object(cerebro, "_call_gemini_with_retry_async", side_effect=mock_gemini), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True):

        res = await cerebro.pensar_respuesta(
            "Hola, quisiera una moto doble propósito con financiación",
            prospect_data=pros_data,
        )

    assert "¡Qué pena!" not in res, "Happy path con financiación NO debe degradar"
    assert len(gemini_calls) == 2

    _t2_payload = gemini_calls[1][1] if len(gemini_calls[1]) > 1 else None
    assert isinstance(_t2_payload, list)
    _fr_texts = []
    for _p in _t2_payload:
        if hasattr(_p, "function_response") and _p.function_response:
            _r = _p.function_response.response
            if isinstance(_r, dict) and _r.get("result"):
                _fr_texts.append(str(_r["result"]))
    _fr_joined = " ".join(_fr_texts)
    assert "DIRECTRIZ DE TURNO" in _fr_joined, (
        f"'financiación' debe activar la directriz anti-deadlock. "
        f"Payload repr: {_fr_joined[:400]}"
    )


# ──────────────── P-TURN1-NUDGE-ONLY ────────────────

@pytest.mark.asyncio
async def test_p_turn1_nudge_only_payload_no_function_response():
    """
    [BOT-BUILD-EMPTY-CANDIDATE-021-RF2 / R7] Pin de la rama response_parts=[]:
    Turn 1 produce texto sin tool-call mencionando moto → forced-turn → respuesta
    con candidates pero content.parts=[] → entra al while loop → inner retry con
    response_parts vacío → payload es solo el nudge (1 part, sin function_response).
    El flujo debe recuperar sin fallback.
    """
    cerebro, catalog_service = _build_cerebro()

    pros_data = {
        "exists": True,
        "nombre": "Mario",
        "habeas_data_accepted": True,
        "phone": PHONE_E164,
    }

    gemini_calls = []

    async def mock_gemini(*args, **kwargs):
        gemini_calls.append(args)
        if len(gemini_calls) == 1:
            # Turn 1: texto sin function_call mencionando moto (forced-turn se activa)
            return _text_response("Hola, déjame ayudarte con eso.")
        if len(gemini_calls) == 2:
            # Forced-turn: response con candidates pero content.parts vacío
            return _MockResponse(candidates=[_MockCandidate(_MockContent([]))])
        # Inner retry (nudge-only): respuesta válida
        return _text_response(HAPPY_TEXT)

    with patch.object(catalog_service, "search_items", return_value=[APACHE_ITEM]), \
         patch.object(cerebro, "_call_gemini_with_retry_async", side_effect=mock_gemini), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True):

        res = await cerebro.pensar_respuesta(
            "Hola, quisiera una moto doble propósito",
            prospect_data=pros_data,
        )

    assert "¡Qué pena!" not in res, "Recuperación nudge-only NO debe degradar"
    assert len(gemini_calls) == 3, (
        f"3 llamadas: initial + forced + retry, hubo {len(gemini_calls)}"
    )

    retry_payload = gemini_calls[2][1] if len(gemini_calls[2]) > 1 else None
    assert isinstance(retry_payload, list), (
        f"Payload del retry debe ser lista, es {type(retry_payload)}"
    )
    # response_parts vacío → solo el part de nudge de texto
    assert len(retry_payload) == 1, (
        f"Payload nudge-only debe tener 1 part, tiene {len(retry_payload)}"
    )
    has_function_response = any(
        hasattr(p, "function_response") and p.function_response
        for p in retry_payload
    )
    assert not has_function_response, (
        "Payload nudge-only NO debe contener function_response"
    )
    assert hasattr(retry_payload[0], "text") and retry_payload[0].text, (
        "El único part debe ser de texto (nudge)"
    )
    assert "respuesta anterior llegó vacía" in retry_payload[0].text, (
        "El texto del nudge debe estar presente"
    )
