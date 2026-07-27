"""
[BOT-BUILD-COHERENCE-WAVE07-04-E2E-FIRE-TEST-001]
Prueba de Fuego E2E integral — certifica las migraciones de Waves 07-01/02/03.

Arnés: router REAL (`_handle_message_background_impl`) + CerebroIA REAL con
Gemini scriptado (function-call turn → text turn) + Juez REAL (auditoría
semántica C4 desactivada, patrón de test_audio_regression.py) + servicios de
frontera mockeados (memory, storage, audio, whatsapp, catálogo del router).

Escenarios del ticket:
1. blind_credit — audio pidiendo cuotas sin datos personales → fallback de
   Crédito Ciego inyecta entidad='Brilla de Gases', cuota formateada, Habeas
   inmediato, cero fallback humano.
2. faq_query — '¿Necesito codeudor?' → query_faq (NO search_catalog), matriz
   de crédito, sin imágenes/precios, embudo retomado.
3. location_query — '¿Dónde están ubicadas sus tiendas?' → query_locations,
   5 sedes, sin imágenes, embudo retomado.
4. full_funnel — /reset → audio MRX → cuota → Sí → nombre/ciudad → ocupación.
"""
import re
from collections import deque
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import BackgroundTasks

import app.services.ai_brain as brain_module
from app.routers.whatsapp import _handle_message_background_impl
from app.services.ai_brain import CerebroIA
from app.services.judge_service import JudgeService


# ============================================================================
# BUILDERS — Gemini scriptado
# ============================================================================

def _fc_response(tool_name: str, tool_args: dict):
    mock_response = MagicMock()
    part = MagicMock()
    part.text = None
    fc = MagicMock()
    fc.name = tool_name
    fc.args = tool_args
    part.function_call = fc
    mock_response.candidates = [MagicMock()]
    mock_response.candidates[0].content.parts = [part]
    mock_response.usage_metadata = MagicMock(
        total_token_count=100, prompt_token_count=80, candidates_token_count=20
    )
    return mock_response


def _text_response(text: str):
    mock_response = MagicMock()
    part = MagicMock()
    part.text = text
    part.function_call = None
    mock_response.candidates = [MagicMock()]
    mock_response.candidates[0].content.parts = [part]
    mock_response.usage_metadata = MagicMock(
        total_token_count=100, prompt_token_count=80, candidates_token_count=20
    )
    return mock_response


def make_scripted_cerebro(script: list, catalog_items=None, motor=None, sent=None):
    """CerebroIA REAL con chat de Gemini scriptado (una respuesta por send_message)."""
    cerebro = CerebroIA()
    cerebro.client = MagicMock()

    catalog = MagicMock()
    catalog.get_catalog_aliases.return_value = {}
    catalog.search_items.return_value = catalog_items or []
    catalog.get_all_items.return_value = catalog_items or []
    cerebro._catalog_service = catalog

    cerebro.motor_financiero = motor or MagicMock()

    responses = deque(script)

    async def _send(*args, **kwargs):
        if sent is not None and args:
            sent.append(args[0])
        return responses.popleft()

    chat = MagicMock()
    chat.send_message = AsyncMock(side_effect=_send)
    cerebro.client.aio.chats.create.return_value = chat
    return cerebro


# ============================================================================
# BUILDERS — frontera del router
# ============================================================================

def _memory_mock(prospect: dict, history: list):
    ms = MagicMock()
    ms.create_prospect_if_missing = AsyncMock()
    ms.update_last_interaction = AsyncMock()
    ms.save_message = AsyncMock()
    ms.transition_to_in_progress = AsyncMock()
    ms.update_prospect_summary = AsyncMock()
    ms.set_human_help_status = AsyncMock()
    ms.get_prospect_data = AsyncMock(return_value=prospect)
    ms.get_or_create_prospect = AsyncMock(return_value=prospect)
    ms.generate_and_update_summary = AsyncMock()
    ms.get_chat_history = AsyncMock(return_value=history)
    ms.delete_prospect_completely = AsyncMock(return_value=True)
    return ms


def _text_msg(phone: str, wamid: str, body: str):
    return {"from": phone, "id": wamid, "type": "text",
            "text": body, "phone_number_id": "555555"}


def _audio_msg(phone: str, wamid: str):
    return {"from": phone, "id": wamid, "type": "audio",
            "media_id": f"media_{wamid}", "mime_type": "audio/ogg; codecs=opus",
            "phone_number_id": "555555"}


async def run_router_turn(msg_data, cerebro_factory, prospect, history, *, audio_text=None, motor=None):
    """Ejecuta un turno completo del router con mocks de frontera.
    Retorna namespace con los mocks para aserciones.
    NOTA: el router inyecta motor_financiero de módulo dentro del cerebro
    (whatsapp.py:879) — por eso el motor se parchea a nivel router."""
    mock_ms = _memory_mock(prospect, history)

    mock_storage = MagicMock()
    mock_storage.download_media = AsyncMock(return_value=b"mock_audio_bytes_fire")

    mock_audio = MagicMock()
    mock_audio.transcribe_audio = AsyncMock(return_value=audio_text or "")

    mock_whatsapp = MagicMock()
    mock_whatsapp.mark_as_read = AsyncMock()
    mock_whatsapp.send_text_message = AsyncMock(return_value=True)

    router_catalog = MagicMock()
    router_catalog.search = MagicMock(return_value=[])
    router_catalog.get_all_items = MagicMock(return_value=[])
    router_catalog._items = []
    router_catalog.normalize_transcription = MagicMock(side_effect=lambda x: x)

    # Juez REAL con auditoría semántica (C4) desactivada — patrón C9-GRACE.
    real_judge = JudgeService(cerebro_ia=MagicMock())
    real_judge._client = None

    mock_egress = AsyncMock(return_value=True)

    with patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.storage_service", mock_storage), \
         patch("app.routers.whatsapp.AudioService", return_value=mock_audio), \
         patch("app.routers.whatsapp.CerebroIA", cerebro_factory), \
         patch("app.routers.whatsapp.VisionService", return_value=MagicMock()), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_whatsapp), \
         patch("app.routers.whatsapp.whatsapp_service", mock_whatsapp, create=True), \
         patch("app.routers.whatsapp.catalog_service", router_catalog), \
         patch("app.routers.whatsapp.judge_service", real_judge), \
         patch("app.routers.whatsapp.config_loader", MagicMock()), \
         patch("app.routers.whatsapp.motor_financiero", motor), \
         patch("app.routers.whatsapp._process_and_send_egress_message", mock_egress), \
         patch("app.routers.whatsapp.message_buffer") as mock_buffer, \
         patch("app.routers.whatsapp._ensure_services", AsyncMock()):

        mock_buffer.add_message = AsyncMock(return_value=True)
        mock_buffer.debounce_seconds = 0
        mock_buffer.is_task_active = MagicMock(return_value=True)
        mock_buffer.get_aggregated_message = AsyncMock(return_value=None)
        mock_buffer.clear_buffer = AsyncMock()

        await _handle_message_background_impl(msg_data, BackgroundTasks())

    return SimpleNamespace(
        memory=mock_ms, audio=mock_audio, whatsapp=mock_whatsapp, egress=mock_egress,
    )


def _egress_text(turn) -> str:
    assert turn.egress.await_count >= 1, "El egreso consolidado jamás fue invocado."
    return str(turn.egress.call_args.args[1])


def _assert_no_human_fallback(turn):
    for call in turn.memory.set_human_help_status.call_args_list:
        if len(call[0]) >= 2:
            assert call[0][1] is not True, \
                "FALLO CRÍTICO: set_human_help_status(True) — el flujo cayó a deserción humana."


# ============================================================================
# DATOS — catálogo controlado
# ============================================================================

SPORT_100 = [{
    "name": "TVS Sport 100", "price": "$ 9.129.000", "raw_price": 9129000.0,
    "category": "Urban", "cc": 0.0,
    "image_url": "https://img.test/sport100.jpg", "summary": "Trabajo 100cc",
}]

MRX_125 = [{
    "name": "Victory MRX 125", "price": "$ 9.129.000", "raw_price": 9129000.0,
    "category": "Sport", "cc": 125,
    "image_url": "https://img.test/mrx125.jpg", "summary": "Deportiva 125cc",
}]

PRICE_REGEX = re.compile(r"\$\s?\d{1,3}(,\d{3})+")
HUMAN_FALLBACK = "Disculpa, no estoy seguro"


# ============================================================================
# SCENARIO 1 — Crédito Ciego vía audio (Waves 07-01 + 07-02)
# ============================================================================

@pytest.mark.asyncio
async def test_scenario_1_blind_credit_audio_injects_brilla_defaults():
    phone = "+573197070401"
    prospect = {
        "exists": True, "status": "IN_PROGRESS", "chatbot_status": "ACTIVE",
        "celular": phone, "human_help_requested": False, "ai_summary": "",
        "moto_interest": "TVS Sport 100",  # moto ya identificada; sin datos personales
    }
    history = [{"role": "user", "content": "quiero saber de cuotas"}]

    motor = MagicMock()
    motor.calculate_payment.return_value = {"cuota_mensual": 450000}

    cerebro = make_scripted_cerebro(
        [_fc_response("calculate_credit_score", {})],  # LLM omite TODOS los parámetros
        catalog_items=SPORT_100,
        motor=motor,
    )

    from app.services.config_service import config_service
    with patch.object(config_service, "get_registration_cost", return_value=0.0), \
         patch.object(brain_module, "_apply_blind_credit_defaults",
                      wraps=brain_module._apply_blind_credit_defaults) as blind_spy:
        turn = await run_router_turn(
            _audio_msg(phone, "wamid.fire_s1_audio"),
            cerebro_factory=MagicMock(return_value=cerebro),
            prospect=prospect,
            history=history,
            audio_text="Hola, quiero saber el precio de la Boxer y cómo financiarla",
            motor=motor,
        )

    # 1. calculate_credit_score ejecutado con entidad='Brilla de Gases'
    motor.calculate_payment.assert_called_once()
    pay_kwargs = motor.calculate_payment.call_args.kwargs
    assert pay_kwargs["entidad"] == "Brilla de Gases"
    assert pay_kwargs["inicial"] == 912900.0, "La inicial ciega debe ser el 10% del precio."

    # 2. El fallback de Crédito Ciego (Wave 07-02) interceptó el payload vacío del LLM
    blind_spy.assert_called_once()
    assert blind_spy.call_args.args[0] == {}, "Se esperaba payload LLM vacío para la inyección."

    # 3. Cuota aproximada con formato monetario correcto + Habeas inmediato
    text = _egress_text(turn)
    assert "aproximadamente de $450,000" in text
    assert PRICE_REGEX.search(text), "La cuota no cumple el formato $XXX,XXX."
    assert "politica-de-privacidad" in text, "El script de Habeas Data no se emitió tras la cuota."

    # 4. Cero fallback humano y pipeline de audio efectivamente usado
    assert HUMAN_FALLBACK not in text
    _assert_no_human_fallback(turn)
    turn.audio.transcribe_audio.assert_awaited_once()


# ============================================================================
# SCENARIO 2 — FAQ de crédito vía query_faq (Wave 07-01)
# ============================================================================

@pytest.mark.asyncio
async def test_scenario_2_faq_query_uses_query_faq_not_catalog():
    phone = "+573197070402"
    prospect = {
        "exists": True, "status": "IN_PROGRESS", "chatbot_status": "ACTIVE",
        "celular": phone, "human_help_requested": False,
        "nombre": "Carlos", "ciudad": "Bogotá", "forma_pago": "crédito",
        "moto_interest": "TVS Sport 100", "habeas_data_accepted": False,
    }

    sent = []
    faq_final_text = (
        "No siempre. Estos son los requisitos oficiales:\n"
        "- Empleados: Requieren Cédula, email, celular.\n"
        "- Reportados: Requieren Cédula + 10% de inicial OBLIGATORIA.\n"
        "- Extranjeros: Requieren PPT/PEP + Pasaporte + Dirección física.\n"
        "- Brilla: Requieren Cédula + 2 últimos recibos de gas pagados.\n"
        "Para darte el valor exacto, ¿me autorizas el tratamiento de tus datos?"
    )
    cerebro = make_scripted_cerebro(
        [
            _fc_response("query_faq", {"query": "codeudor crédito"}),
            _text_response(faq_final_text),
        ],
        catalog_items=SPORT_100,
        sent=sent,
    )

    with patch.object(brain_module, "get_faq_answer",
                      wraps=brain_module.get_faq_answer) as faq_spy:
        turn = await run_router_turn(
            _text_msg(phone, "wamid.fire_s2_faq", "¿Necesito codeudor para el crédito?"),
            cerebro_factory=MagicMock(return_value=cerebro),
            prospect=prospect,
            history=[],
        )

    # 1. query_faq invocado, search_catalog NO
    faq_spy.assert_called_once()
    cerebro._catalog_service.search_items.assert_not_called()

    # 2. Respuesta con la matriz de crédito migrada
    text = _egress_text(turn)
    assert "Reportados: Requieren Cédula + 10% de inicial OBLIGATORIA." in text

    # 3. Sin imágenes ni precios en la respuesta FAQ
    assert "![" not in text
    assert not PRICE_REGEX.search(text), "La respuesta FAQ no debe incluir precios."

    # 4. Embudo retomado: [BOT-PLAN-HARDENING-EGRESS-FUNNEL-001 / Fase 3 — Capa A]
    #    el function response cierra con el ANCLA DE EMBUDO que porta la pregunta
    #    pendiente VERBATIM (en PHASE_2: el script legal de consentimiento del PASO 4,
    #    que ES la directiva de Habeas en forma textual), sustituyendo al
    #    funnel_instruction genérico. El PHASE-GATE sancionado (ai_brain.py:922)
    #    sigue cerrando hacia la firma de Habeas Data.
    assert len(sent) == 2
    payload_str = str(sent[1])
    assert "[ANCLA DE EMBUDO" in payload_str, "El function response no incluyó el ancla de embudo (Capa A)."
    assert "¿me autorizas el tratamiento de tus datos?" in payload_str, \
        "El ancla no porta la pregunta pendiente verbatim (script PASO 4)."
    assert "política de privacidad" in text, \
        "El PHASE-GATE no retomó el embudo hacia la firma de Habeas Data."
    _assert_no_human_fallback(turn)


# ============================================================================
# SCENARIO 3 — Ubicaciones vía query_locations (Wave 07-01)
# ============================================================================

@pytest.mark.asyncio
async def test_scenario_3_location_query_returns_five_branches():
    phone = "+573197070403"
    prospect = {
        "exists": True, "status": "IN_PROGRESS", "chatbot_status": "ACTIVE",
        "celular": phone, "human_help_requested": False,
        "nombre": "Carlos", "moto_interest": "TVS Sport 100",
    }

    locations_final_text = (
        "¡Claro! Estas son nuestras sedes:\n"
        "- Santa Marta (11 Noviembre): Calle 30 # 79-85. https://maps.app.goo.gl/xjRquwXZZiRaDyeU7\n"
        "- Santa Marta (Piragua): Sector 1 Mz I Casa 4 L 4. https://maps.app.goo.gl/mnV22T9J5cUErZSx5\n"
        "- Santa Marta (Gaira): Carrera 4 # 20-45. https://maps.app.goo.gl/FG6jFQKm1J1httLZ6\n"
        "- Riohacha: Calle 15 # 11A-12. https://maps.app.goo.gl/8fp1D2c2due6UHMo9\n"
        "- Zona Bananera (Orihueca): Calle 5 # 2-135. https://maps.app.goo.gl/1savLzhGmEfB3qDT6\n"
        "¿Desde qué ciudad nos escribes?"
    )
    sent = []
    cerebro = make_scripted_cerebro(
        [
            _fc_response("query_locations", {"query": "tiendas ubicación"}),
            _text_response(locations_final_text),
        ],
        catalog_items=SPORT_100,
        sent=sent,
    )

    with patch.object(brain_module, "get_location_info",
                      wraps=brain_module.get_location_info) as loc_spy:
        turn = await run_router_turn(
            _text_msg(phone, "wamid.fire_s3_loc", "¿Dónde están ubicadas sus tiendas?"),
            cerebro_factory=MagicMock(return_value=cerebro),
            prospect=prospect,
            history=[],
        )

    # 1. query_locations invocado, search_catalog NO
    loc_spy.assert_called_once()
    cerebro._catalog_service.search_items.assert_not_called()

    # 2. Las 5 sedes con sus links
    text = _egress_text(turn)
    for name in ["Santa Marta (11 Noviembre)", "Santa Marta (Piragua)", "Santa Marta (Gaira)",
                 "Riohacha", "Zona Bananera (Orihueca)"]:
        assert name in text, f"Sede '{name}' ausente en la respuesta."
    assert text.count("https://maps.app.goo.gl/") == 5

    # 3. Sin imágenes de motos
    assert "![" not in text

    # 4. Embudo retomado: la pregunta de ciudad viajó con el tool result
    assert len(sent) == 2
    assert "¿Desde qué ciudad nos escribes?" in str(sent[1])
    assert text.rstrip().endswith("?")
    _assert_no_human_fallback(turn)


# ============================================================================
# SCENARIO 4 — Embudo completo: reset → audio → cuota → Habeas → perfilamiento
# ============================================================================

@pytest.mark.asyncio
async def test_scenario_4_full_funnel_reset_to_profiling():
    phone = "+573197070404"
    base = {
        "exists": True, "status": "IN_PROGRESS", "chatbot_status": "ACTIVE",
        "celular": phone, "human_help_requested": False, "ai_summary": "",
    }

    cerebro_queue = deque()
    cerebro_factory = MagicMock(side_effect=lambda *a, **k: cerebro_queue.popleft())

    # --- TURNO 1: /reset (intercepción de comando, sin cerebro) ---
    # El router instancia CerebroIA ANTES de interceptar el comando (whatsapp.py:878):
    # se encola un dummy que jamás recibirá inferencia.
    cerebro_queue.append(make_scripted_cerebro([_text_response("unused")]))
    turn1 = await run_router_turn(
        _text_msg(phone, "wamid.fire_s4_reset", "/reset"),
        cerebro_factory=cerebro_factory,
        prospect=dict(base),
        history=[],
    )
    turn1.memory.delete_prospect_completely.assert_awaited_once_with(phone)
    reset_ack_texts = [str(c.args[1]) for c in turn1.whatsapp.send_text_message.call_args_list]
    assert any("reiniciada por completo" in t for t in reset_ack_texts), \
        "El ack determinista de /reset no fue enviado."

    # --- TURNO 2: audio 'Me interesa la VICTORY MRX 125' → PASO 1 (Visual-Lock) ---
    motor = MagicMock()
    motor.calculate_payment.return_value = {"cuota_mensual": 450000}

    cerebro_catalog = make_scripted_cerebro(
        [
            _fc_response("search_catalog", {"query": "Victory MRX 125"}),
            _text_response(
                "¡Hola! Soy Juan Pablo de Tienda Las Motos. La Victory MRX 125 es una "
                "bestia deportiva. Precio: $9.129.000. "
                "![Victory MRX 125](https://img.test/mrx125.jpg) "
                "Ficha Tecnica: Deportiva 125cc. ¿Prefieres compra de contado o a crédito?"
            ),
        ],
        catalog_items=MRX_125,
        motor=motor,
    )
    cerebro_queue.append(cerebro_catalog)

    from app.services.config_service import config_service
    with patch.object(config_service, "get_registration_cost", return_value=0.0):
        turn2 = await run_router_turn(
            _audio_msg(phone, "wamid.fire_s4_audio"),
            cerebro_factory=cerebro_factory,
            prospect=dict(base),
            history=[],
            audio_text="Me interesa la VICTORY MRX 125",
            motor=motor,
        )
    text2 = _egress_text(turn2)
    assert "Juan Pablo" in text2, "PASO 1: saludo de primer contacto ausente."
    assert "![Victory MRX 125](https://img.test/mrx125.jpg)" in text2, "PASO 1: Visual-Lock (imagen) roto."
    assert "$9.129.000" in text2, "PASO 1: Visual-Lock (precio) roto."

    # --- TURNO 3: '¿Cuánto sería la cuota?' → PASO 2/3/4 (Brilla ciega + Habeas) ---
    cerebro_credit = make_scripted_cerebro(
        [_fc_response("calculate_credit_score", {})],
        catalog_items=MRX_125,
        motor=motor,
    )
    cerebro_queue.append(cerebro_credit)

    with patch.object(config_service, "get_registration_cost", return_value=0.0):
        turn3 = await run_router_turn(
            _text_msg(phone, "wamid.fire_s4_cuota", "¿Cuánto sería la cuota?"),
            cerebro_factory=cerebro_factory,
            prospect={**base, "moto_interest": "Victory MRX 125"},
            history=[{"role": "user", "content": "quiero saber de cuotas"}],
            motor=motor,
        )
    text3 = _egress_text(turn3)
    pay_kwargs = motor.calculate_payment.call_args.kwargs
    assert pay_kwargs["entidad"] == "Brilla de Gases", "PASO 2: la simulación ciega no usó Brilla."
    assert PRICE_REGEX.search(text3), "PASO 3: cuota aproximada sin formato monetario."
    assert "politica-de-privacidad" in text3, "PASO 4: script de Habeas Data ausente."
    assert "emoji de pulgar arriba (👍)" in text3, "PASO 4: frase inmutable del emoji 👍 ausente."

    # --- TURNO 4: 'Sí' (Habeas) → PASO 5a (nombre + ciudad) ---
    cerebro_identity = make_scripted_cerebro(
        [_text_response(
            "¡Perfecto! Para continuar con tu estudio de crédito, ¿me regalas tu "
            "nombre completo y de qué ciudad nos escribes?"
        )],
        catalog_items=MRX_125,
        motor=motor,
    )
    cerebro_queue.append(cerebro_identity)

    turn4 = await run_router_turn(
        _text_msg(phone, "wamid.fire_s4_si", "Sí"),
        cerebro_factory=cerebro_factory,
        prospect={**base, "moto_interest": "Victory MRX 125", "forma_pago": "crédito",
                  "habeas_data_accepted": True, "habeas_data_accepted_sent": True},
        history=[{"role": "model", "content": "Política: https://tiendalasmotos.com/politica-de-privacidad"},
                 {"role": "user", "content": "Sí"}],
        motor=motor,
    )
    text4 = _egress_text(turn4)
    assert "nombre completo" in text4 and "ciudad" in text4, \
        "PASO 5: no se solicitaron nombre y ciudad tras el Sí de Habeas Data."

    # --- TURNO 5: 'Carlos Pérez, Bogotá' → MATRIZ (primera pregunta: ocupación) ---
    cerebro_profiling = make_scripted_cerebro(
        [_text_response("Gracias, Carlos Pérez. Para tu estudio: ¿a qué te dedicas "
                        "actualmente? ¿Eres empleado o independiente?")],
        catalog_items=MRX_125,
        motor=motor,
    )
    cerebro_queue.append(cerebro_profiling)

    turn5 = await run_router_turn(
        _text_msg(phone, "wamid.fire_s4_identity", "Carlos Pérez, Bogotá"),
        cerebro_factory=cerebro_factory,
        prospect={**base, "moto_interest": "Victory MRX 125", "forma_pago": "crédito",
                  "habeas_data_accepted": True, "habeas_data_accepted_sent": True,
                  "nombre": "Carlos Pérez", "ciudad": "Bogotá"},
        history=[{"role": "user", "content": "Sí"}],
        motor=motor,
    )
    text5 = _egress_text(turn5)
    assert "dedicas" in text5, "MATRIZ: la primera pregunta de perfilamiento (ocupación) no se emitió."

    # --- TURNO 6: 'Empleado' → MATRIZ continúa (contrato) ---
    cerebro_contract = make_scripted_cerebro(
        [_text_response("¡Excelente, Carlos! ¿Qué tipo de contrato tienes: fijo, "
                        "prestación de servicios o por obra?")],
        catalog_items=MRX_125,
        motor=motor,
    )
    cerebro_queue.append(cerebro_contract)

    turn6 = await run_router_turn(
        _text_msg(phone, "wamid.fire_s4_ocupation", "Empleado"),
        cerebro_factory=cerebro_factory,
        prospect={**base, "moto_interest": "Victory MRX 125", "forma_pago": "crédito",
                  "habeas_data_accepted": True, "habeas_data_accepted_sent": True,
                  "nombre": "Carlos Pérez", "ciudad": "Bogotá", "ocupacion": "Empleado"},
        history=[{"role": "user", "content": "Carlos Pérez, Bogotá"}],
        motor=motor,
    )
    text6 = _egress_text(turn6)
    assert "contrato" in text6, "MATRIZ: la segunda pregunta (contrato) no se emitió."

    # --- CERTIFICACIONES TRANSVERSALES DEL EMBUDO ---
    assert not cerebro_queue, "El router no consumió los 5 cerebros scriptados (turnos 2-6)."
    for i, turn in enumerate([turn2, turn3, turn4, turn5, turn6], start=2):
        _assert_no_human_fallback(turn)
        assert HUMAN_FALLBACK not in _egress_text(turn), f"Turno {i} cayó en fallback humano."
    # Pipeline de extracción (Wave 07-03) activo durante el embudo
    total_summary_calls = sum(
        t.memory.generate_and_update_summary.await_count
        for t in [turn2, turn3, turn4, turn5, turn6]
    )
    assert total_summary_calls >= 1, "generate_and_update_summary jamás se invocó en el embudo."


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
