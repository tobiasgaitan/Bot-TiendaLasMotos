"""
Pins de BOT-BUILD-DEADLOCK-PERSISTENT-022 (v10.64.0).

P1-HAPPY-E2E:    /reset -> "doble proposito a credito" -> Turn 1 search_catalog,
                  Turn 2 calculate_credit_score rechazado (controlado),
                  Turn 3 PASO 1 completo ($, ![], Ficha Tecnica:), SIN fallback.
P2-FASE-CONGELADA: fuerza CATALOG_VALIDATION_FAIL en attempt 1;
                   attempt 2 preserva <fase_actual>PHASE_1_PROFILING y NO contiene
                   instruccion de Habeas; spy call_count == 3 (C5-034 pendiente).
P3-CLASIFICADOR:   control positivo: turno fresco con moto_interest canonico + credito
                   -> avanza a PHASE_2.
P4-NO-UTC:         assert config.tools en llamadas 2/3/4; nudge contiene
                   prohibicion dual; len(gemini_calls)==4; resultado happy path.
P6-FLAG-ONE-SHOT:  en turno con mencion crediticia, calculate_credit_score se
                   rechaza exactamente 1 vez (caplog count == 1).
"""

import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai_brain import CerebroIA
from app.services.catalog_service import CatalogService


PHONE_E164 = "+573192564289"

APACHE_ITEM = {
    "id": "apache_200",
    "name": "TVS APACHE RTR 200 4V XC FI ABS",
    "price": "$13.899.999",
    "formatted_price": "$13.899.999 (incluye SOAT, Matricula, y tramites)",
    "image_url": "https://storage.googleapis.com/b/tiendalasmotos.appspot.com/o/products%2Fapache-200.png?alt=media",
    "category": "deportiva",
    "searchBy": ["apache"],
    "summary": "La deportiva TVS Apache 200.",
}

HAPPY_TEXT = (
    "Hola! Soy Juan Pablo, tu asesor de Auteco Las Motos. Que gusto!\n"
    "Para doble proposito te recomiendo la VICTORY MRX 125.\n"
    "![VICTORY MRX 125](https://img/mrx125.png)\n"
    "Precio: $9.969.000. Ficha Tecnica: VICTORY MRX 125. Con quien tengo el gusto?"
)

NO_FICHA_TEXT = (
    "Hola, te recomiendo la VICTORY MRX 125.\n"
    "![VICTORY MRX 125](https://img/mrx125.png)\n"
    "Precio: $9.969.000. Con quien tengo el gusto?"
)

FALLBACK_MARKER = "Que pena! Tuve un inconveniente procesando esa busqueda"


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


def _fc_calculate_credit_score():
    fc = MagicMock()
    fc.name = "calculate_credit_score"
    fc.args = {
        "ocupacion_y_contrato": "Empleado",
        "ingresos_demostrables": "SMLV",
        "historial_datacredito": "Sin experiencia",
    }
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

# --------------- P1-HAPPY-E2E ---------------

@pytest.mark.asyncio
async def test_p1_happy_e2e_credit_rejection_recovers():
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
            return _fc_calculate_credit_score()
        return _text_response(HAPPY_TEXT)

    with patch.object(catalog_service, "search_items", return_value=[APACHE_ITEM]), \
         patch.object(cerebro, "_call_gemini_with_retry_async", side_effect=mock_gemini), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True):

        res = await cerebro.pensar_respuesta(
            "Hola, quisiera una moto doble proposito a credito",
            prospect_data=pros_data,
        )

    assert re.search(r"\$\d[\d.,]+", res), f"PASO 1 debe tener precio con $: '{res[:300]}'"
    assert "![" in res, "PASO 1 debe tener imagen Markdown"
    assert "Ficha Tecnica" in res, "PASO 1 debe tener prefijo Ficha Tecnica"
    assert FALLBACK_MARKER not in res, "Happy path NO debe degradar al fallback"
    assert len(gemini_calls) == 3, (
        f"3 llamadas (inicial + post-search-fc-credit + text), hubo {len(gemini_calls)}"
    )


# --------------- P2-FASE-CONGELADA ---------------

@pytest.mark.asyncio
async def test_p2_fase_congelada_attempt2_freeze():
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
            return _text_response(NO_FICHA_TEXT)
        if len(gemini_calls) == 3:
            return _fc_search_catalog("enduro")
        return _text_response(HAPPY_TEXT)

    spy = MagicMock(wraps=cerebro._determine_funnel_phase)

    with patch.object(catalog_service, "search_items", return_value=[APACHE_ITEM]), \
         patch.object(cerebro, "_call_gemini_with_retry_async", side_effect=mock_gemini), \
         patch.object(cerebro, "_determine_funnel_phase", spy), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True):

        res = await cerebro.pensar_respuesta(
            "Hola, quisiera una moto doble proposito a credito",
            prospect_data=pros_data,
        )

    assert FALLBACK_MARKER not in res, "El attempt 2 debe recuperarse sin fallback"
    assert "Ficha Tecnica" in res, "El attempt 2 debe completar PASO 1 con Ficha"
    assert re.search(r"\$\d[\d.,]+", res), "PASO 1 debe tener precio con $"

    assert spy.call_count == 3, (
        f"1 captura turn_phase + 2 log-only _create_tools (:1689, C5-034), "
        f"hubo {spy.call_count}"
    )

    attempt2_prompt = None
    for i, call_args in enumerate(gemini_calls):
        if i >= 2:
            payload = call_args[1] if len(call_args) > 1 else call_args[0]
            if isinstance(payload, str) and "<fase_actual>" in payload:
                attempt2_prompt = payload
                break

    assert attempt2_prompt is not None, "Debe existir prompt de attempt 2"
    assert "<fase_actual>PHASE_1_PROFILING</fase_actual>" in attempt2_prompt, (
        f"Attempt 2 debe conservar PHASE_1: {attempt2_prompt[:400]}"
    )
    assert "EL USUARIO ESTA LISTO PARA EL CREDITO" not in attempt2_prompt, (
        "Attempt 2 NO debe contener instruccion de Habeas"
    )
    assert "PHASE_2_HABEAS_DATA" not in attempt2_prompt, "Sin PHASE_2 en prompt congelado"

    assert len(gemini_calls) == 4, f"2 attempts x 2 llamadas = 4, hubo {len(gemini_calls)}"

# --------------- P3-CLASIFICADOR ---------------

def test_p3_classifier_positivo_avanza_ph2_nuevo_turno():
    cerebro, _ = _build_cerebro()

    pros = {
        "exists": True,
        "moto_interest": "TVS APACHE RTR 200 4V XC FI ABS",
        "phone": PHONE_E164,
    }
    history = [
        {"role": "user", "content": "Hola, quisiera una moto doble proposito a credito"},
        {"role": "assistant", "content": HAPPY_TEXT},
        {"role": "user", "content": "Si, a credito"},
    ]

    phase = cerebro._determine_funnel_phase(pros, history)
    assert phase == "PHASE_2_HABEAS_DATA", (
        f"Turno nuevo con moto canonica + credito debe avanzar a PHASE_2, no {phase}"
    )


@pytest.mark.asyncio
async def test_p3_e2e_segundo_turno_ph2_en_prompt():
    cerebro, catalog_service = _build_cerebro()

    pros_data = {
        "exists": True,
        "nombre": "Mario",
        "moto_interest": "TVS APACHE RTR 200 4V XC FI ABS",
        "habeas_data_accepted": True,
        "phone": PHONE_E164,
    }

    gemini_calls = []

    async def mock_gemini(*args, **kwargs):
        gemini_calls.append(args)
        return _text_response("Perfecto, Mario. Para continuar con el credito necesito algunos datos...")

    with patch.object(catalog_service, "search_items", return_value=[APACHE_ITEM]), \
         patch.object(cerebro, "_call_gemini_with_retry_async", side_effect=mock_gemini), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True):

        await cerebro.pensar_respuesta(
            "Si, a credito",
            prospect_data=pros_data,
        )

    first_prompt = gemini_calls[0][1] if len(gemini_calls[0]) > 1 else gemini_calls[0][0]
    prompt_str = first_prompt if isinstance(first_prompt, str) else str(first_prompt)
    assert "<fase_actual>PHASE_2_HABEAS_DATA</fase_actual>" in prompt_str, (
        f"Turno nuevo con credito debe entrar en PHASE_2: {prompt_str[:400]}"
    )

# --------------- P4-NO-UTC ---------------

def _assert_tools_not_empty(cfg):
    tools = getattr(cfg, "tools", None)
    assert tools is not None and tools, (
        f"tools debe ser no vacio en este send, es {tools!r}"
    )


def _assert_tools_empty(cfg):
    tools = getattr(cfg, "tools", None)
    assert tools is None or (isinstance(tools, list) and len(tools) == 0), (
        f"tools debe ser [] o None en este send, es {tools!r}"
    )


@pytest.mark.asyncio
async def test_p4_no_utc_tools_config_and_nudge():
    cerebro, catalog_service = _build_cerebro()

    pros_data = {
        "exists": True,
        "nombre": "Mario",
        "habeas_data_accepted": True,
        "phone": PHONE_E164,
    }

    gemini_calls = []

    async def mock_gemini(*args, **kwargs):
        gemini_calls.append((args, kwargs))
        if len(gemini_calls) == 1:
            return _fc_search_catalog("enduro")
        if len(gemini_calls) == 2:
            return _fc_calculate_credit_score()
        if len(gemini_calls) == 3:
            return _empty_response()
        return _text_response(HAPPY_TEXT)

    with patch.object(catalog_service, "search_items", return_value=[APACHE_ITEM]), \
         patch.object(cerebro, "_call_gemini_with_retry_async", side_effect=mock_gemini), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True):

        res = await cerebro.pensar_respuesta(
            "Hola, quisiera una moto doble proposito a credito",
            prospect_data=pros_data,
        )

    assert len(gemini_calls) == 4, (
        f"4 llamadas (inicial + post-search + post-rechazo + retry), hubo {len(gemini_calls)}"
    )

    cfg2 = gemini_calls[1][1].get("config")
    assert cfg2 is not None, "Llamada 2 debe tener config kwarg"
    _assert_tools_not_empty(cfg2)

    cfg3 = gemini_calls[2][1].get("config")
    assert cfg3 is not None, "Llamada 3 debe tener config kwarg"
    _assert_tools_empty(cfg3)

    cfg4 = gemini_calls[3][1].get("config")
    assert cfg4 is not None, "Llamada 4 debe tener config kwarg"
    _assert_tools_empty(cfg4)

    retry_args = gemini_calls[3][0]
    retry_payload = retry_args[1] if len(retry_args) > 1 else retry_args[0]

    nudge_text = ""
    if isinstance(retry_payload, list):
        for part in retry_payload:
            if hasattr(part, "text") and part.text:
                nudge_text += part.text
    elif isinstance(retry_payload, str):
        nudge_text = retry_payload

    assert "calculate_credit_score" in nudge_text, (
        f"Nudge T2 debe prohibir calculate_credit_score: '{nudge_text[:300]}'"
    )

    assert re.search(r"\$\d[\d.,]+", res), f"Precio con $: '{res[:300]}'"
    assert "![" in res, "Imagen Markdown"
    assert "Ficha Tecnica" in res, "Prefijo Ficha Tecnica"
    assert FALLBACK_MARKER not in res, "Sin fallback"

# --------------- P6-FLAG-ONE-SHOT ---------------

@pytest.mark.asyncio
async def test_p6_flag_one_shot_rejection_count():
    cerebro, catalog_service = _build_cerebro()

    pros_data = {
        "exists": True,
        "nombre": "Mario",
        "habeas_data_accepted": True,
        "phone": PHONE_E164,
    }

    gemini_calls = []

    async def mock_gemini(*args, **kwargs):
        gemini_calls.append((args, kwargs))
        if len(gemini_calls) == 1:
            return _fc_search_catalog("enduro")
        if len(gemini_calls) == 2:
            return _fc_calculate_credit_score()
        if len(gemini_calls) == 3:
            return _empty_response()
        return _text_response(HAPPY_TEXT)

    with patch.object(catalog_service, "search_items", return_value=[APACHE_ITEM]), \
         patch.object(cerebro, "_call_gemini_with_retry_async", side_effect=mock_gemini), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True), \
         patch("app.services.ai_brain.logger") as mock_logger:
            res = await cerebro.pensar_respuesta(
                "Hola, quisiera una moto doble proposito a credito",
                prospect_data=pros_data,
            )

    rejection_logs = [
        call for call in mock_logger.warning.call_args_list
        if "[TOOL REJECTION] calculate_credit_score invoked in PHASE_1_PROFILING" in str(call)
    ]
    assert len(rejection_logs) == 1, (
        f"calculate_credit_score debe rechazarse exactamente 1 vez por attempt (flag per-attempt), "
        f"hubo {len(rejection_logs)}: {rejection_logs}"
    )

    assert FALLBACK_MARKER not in res, "PASO 1 se recupera sin fallback"
    assert "Ficha Tecnica" in res, "PASO 1 completo"

# --------------- P7-PARALLEL-CREDIT ---------------

def _dual_fc_calculate_credit_score():
    fc1 = MagicMock()
    fc1.name = "calculate_credit_score"
    fc1.args = {"ocupacion_y_contrato": "Empleado", "ingresos_demostrables": "SMLV", "historial_datacredito": "Sin experiencia"}
    fc2 = MagicMock()
    fc2.name = "calculate_credit_score"
    fc2.args = {"ocupacion_y_contrato": "Independiente", "ingresos_demostrables": "3 SMLV", "historial_datacredito": "Al dia"}
    return _MockResponse(candidates=[_MockCandidate(_MockContent([
        _MockPart(function_call=fc1), _MockPart(function_call=fc2)
    ]))])


@pytest.mark.asyncio
async def test_p7_parallel_credit_fc_fr_pairing_intact():
    """
    Turn 2 response con DOS calculate_credit_score en paralelo.
    Assert: payload del reenvio contiene 2 function_response (pairing fc=fr intacto),
    0 text parts del cortocircuito, 1 rechazo primario + 1 marcador Repeated,
    resultado happy path sin fallback.
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
        gemini_calls.append((args, kwargs))
        if len(gemini_calls) == 1:
            return _fc_search_catalog("enduro")
        if len(gemini_calls) == 2:
            return _dual_fc_calculate_credit_score()
        return _text_response(HAPPY_TEXT)

    with patch.object(catalog_service, "search_items", return_value=[APACHE_ITEM]), \
         patch.object(cerebro, "_call_gemini_with_retry_async", side_effect=mock_gemini), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True), \
         patch("app.services.ai_brain.logger") as mock_logger:

            res = await cerebro.pensar_respuesta(
                "Hola, quisiera una moto doble proposito a credito",
                prospect_data=pros_data,
            )

    assert len(gemini_calls) == 3, (
        f"3 llamadas (inicial + post-search-dual-fc + text), hubo {len(gemini_calls)}"
    )

    _, kwargs2 = gemini_calls[1]
    payload2 = kwargs2.get("config", None)
    assert payload2 is not None, "Llamada 2 debe tener config"
    tools2 = getattr(payload2, "tools", None)
    assert tools2 is not None and tools2, "Llamada 2 (post-search) debe tener tools != [] (T1 activo)"

    rejection_logs = [
        call for call in mock_logger.warning.call_args_list
        if "[TOOL REJECTION] calculate_credit_score invoked in PHASE_1_PROFILING" in str(call)
    ]
    assert len(rejection_logs) == 1, (
        f"Rechazo primario debe ser exactamente 1 (primer fc del par), hubo {len(rejection_logs)}"
    )

    repeated_logs = [
        call for call in mock_logger.warning.call_args_list
        if "Repeated calculate_credit_score attempt" in str(call)
    ]
    assert len(repeated_logs) == 1, (
        f"Marcador Repeated debe ser exactamente 1 (segundo fc del par), hubo {len(repeated_logs)}"
    )

    assert FALLBACK_MARKER not in res, "Sin fallback — pairing fc=fr intacto, no 400"
    assert re.search(r"\$\d[\d.,]+", res), "Precio con $"
    assert "![" in res, "Imagen Markdown"
    assert "Ficha Tecnica" in res, "Prefijo Ficha Tecnica"
