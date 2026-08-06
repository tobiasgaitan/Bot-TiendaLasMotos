"""
Pins de Orden Estado→Egreso — Etapa 3 Wave 05-01 [BOT-BUILD-ETAPA3-WAVE01-CHARACTERIZATION-001]

Verifica la Sincronía de Oficio en el monolito `_handle_message_background_impl`:
toda escritura de estado transicional del embudo (Firestore vía MemoryService) se
confirma ANTES del primer envío de mensaje a la API de Meta (red externa).

Excepción sancionada pineada explícitamente: `mark_as_read` (protocolo READ-FIRST,
L761-765) es un acuse de lectura — NO un mensaje del embudo — y se ejecuta antes
de cualquier persistencia por diseño documentado. Queda FUERA del conjunto de
"envíos" de este pin por decisión del ticket (egreso = mensajes al usuario).

Pins por rama:
  ORDER-TEXT      create→update_last→transition→summary→save(user)→save(model pre-egreso)
                  preceden al 1er envío Meta. Comportamiento vigente adicional: el eco
                  save(model) intra-egreso (L1906) ocurre DESPUÉS del envío (duplicidad
                  documentada; normalizable solo en 05-05 con aprobación del Auditor).
  ORDER-IMAGE     update_prospect_summary(moto_interest+PENDING) precede a
                  pensar_respuesta y al egreso de imagen [BOT-PONYTAIL-200].
  ORDER-AUDIO     save(user=transcripción) → generate_and_update_summary → 1er envío.
  ORDER-REACTION  update_prospect_summary(habeas+PENDING) precede a pensar_respuesta.
  ORDER-RESET     delete_prospect_completely precede a la confirmación enviada.
  ORDER-FALLBACK  [MANDATO v9.8.3] set_human_help_status(True) → ponytail DEPRIORITIZED
                  → save(model fallback) preceden al envío del mensaje de fallback.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import BackgroundTasks

from app.routers.whatsapp import _handle_message_background_impl
from tests.factories import make_catalog_item, format_cop
import random

PHONE_E164 = "+573192564288"
PHONE_RAW = "573192564288"
PHONE_NUMBER_ID = "999999"

# Etiquetas de eventos de la línea de tiempo
SEND_LABELS = ("meta:send_text", "meta:send_image")


# ── Utilidades de línea de tiempo ─────────────────────────────────────────────

def _wire_ms_timeline(ms: MagicMock, timeline: list) -> None:
    """Convierte cada método de persistencia del mock en un evento fechado."""
    def _recorder(label):
        async def _rec(*args, **kwargs):
            timeline.append(label)
            return True
        return _rec

    for name in (
        "create_prospect_if_missing",
        "update_last_interaction",
        "transition_to_in_progress",
        "generate_and_update_summary",
        "set_human_help_status",
        "update_prospect_summary",
        "delete_prospect_completely",
    ):
        getattr(ms, name).side_effect = _recorder(name)

    async def _save_rec(phone, role, content, **kwargs):
        timeline.append(f"save_message:{role}")
        return True

    ms.save_message.side_effect = _save_rec


def _send_recorder(label: str, timeline: list) -> AsyncMock:
    async def _rec(*args, **kwargs):
        timeline.append(label)
        return True
    return AsyncMock(side_effect=_rec)


def _first_send_index(timeline: list) -> int:
    indices = [i for i, e in enumerate(timeline) if e in SEND_LABELS]
    assert indices, f"Nunca hubo envío de mensaje a Meta en la línea de tiempo: {timeline}"
    return min(indices)


def _assert_precedes(timeline: list, label: str, context: str) -> None:
    first_send = _first_send_index(timeline)
    idxs = [i for i, e in enumerate(timeline) if e == label]
    assert idxs, f"[{context}] Evento de persistencia ausente: {label!r} en {timeline}"
    assert idxs[0] < first_send, (
        f"[{context}] VIOLACIÓN de Sincronía de Oficio: {label!r} (índice {idxs[0]}) "
        f"NO precede al primer envío Meta (índice {first_send}). Timeline: {timeline}"
    )


def _build_ms_mock(timeline: list, prospect: dict | None = None) -> MagicMock:
    """MemoryService mockeado con superficie completa + línea de tiempo fechada.

    WHY get_or_create_prospect explícito: ver docstring de _build_ms_mock en
    tests/test_webhook_integrity_e2e.py (polución de identidad de clases Mock por
    expulsión de sys.modules en test heredado; el guard BOT-174 sanciona esta rama).
    """
    prospect = prospect or {
        "exists": True,
        "status": "IN_PROGRESS",
        "chatbot_status": "ACTIVE",
        "name": "Juan Test",
        "celular": PHONE_E164,
        "ai_summary": "Resumen previo",
        "human_help_requested": False,
    }
    ms = MagicMock()
    ms.create_prospect_if_missing = AsyncMock()
    ms.update_last_interaction = AsyncMock()
    ms.transition_to_in_progress = AsyncMock()
    ms.generate_and_update_summary = AsyncMock()
    ms.save_message = AsyncMock()
    ms.set_human_help_status = AsyncMock()
    ms.update_prospect_summary = AsyncMock()
    ms.delete_prospect_completely = AsyncMock(return_value=True)
    ms.get_or_create_prospect = AsyncMock(return_value=prospect)
    ms.get_prospect_data = AsyncMock(return_value=prospect)
    ms.get_chat_history = AsyncMock(return_value=[])
    _wire_ms_timeline(ms, timeline)
    return ms


def _build_buffer_mock() -> MagicMock:
    buffer = MagicMock()
    buffer.add_message = AsyncMock(return_value=True)
    buffer.is_task_active = MagicMock(return_value=True)
    buffer.get_aggregated_message = AsyncMock(return_value=None)
    buffer.clear_buffer = AsyncMock()
    buffer.debounce_seconds = 0.01
    return buffer


def _build_whatsapp_service_mock(timeline: list) -> MagicMock:
    wa = MagicMock()

    async def _mark(*args, **kwargs):
        # READ-FIRST: acuse de lectura sancionado — fuera del conjunto SEND_LABELS.
        timeline.append("meta:mark_as_read")
        return True

    wa.mark_as_read = AsyncMock(side_effect=_mark)
    wa.send_text_message = _send_recorder("meta:send_text", timeline)
    wa.send_image_message = _send_recorder("meta:send_image", timeline)
    return wa


# ── ORDER-TEXT ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_order_text_branch_state_precedes_meta_egress():
    """
    Rama texto: toda la escritura transicional del embudo precede al primer envío
    a Meta. El acuse mark_as_read (READ-FIRST) se registra como excepción sancionada.
    Pin adicional del comportamiento vigente: el eco save_message('model') intra-egreso
    (L1906) ocurre DESPUÉS del envío (segunda persistencia del mismo turno).
    """
    item = make_catalog_item(0, random.Random(2026))
    llm_response = (
        f"Mira esta {item['name']}. Precio: {format_cop(item['price'])}. "
        f"Ficha Tecnica: {item['summary']} "
        f"![{item['name']}]({item['image_url']})"
    )

    timeline = []
    mock_ms = _build_ms_mock(timeline)
    mock_wa = _build_whatsapp_service_mock(timeline)

    mock_cerebro = MagicMock()
    mock_cerebro.pensar_respuesta = AsyncMock(return_value=llm_response)
    mock_judge = MagicMock()
    mock_judge.analyze_response = AsyncMock(return_value=(True, ""))
    mock_catalog = MagicMock()
    mock_catalog.search = MagicMock(return_value=[])

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.routers.whatsapp.judge_service", mock_judge), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_wa), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.message_buffer", _build_buffer_mock()), \
         patch("app.routers.whatsapp._send_whatsapp_image", _send_recorder("meta:send_image", timeline)), \
         patch("app.routers.whatsapp._send_whatsapp_message", _send_recorder("meta:send_text", timeline)), \
         patch("app.routers.whatsapp.db", MagicMock()):

        msg_payload = {
            "from": PHONE_RAW,
            "id": "wamid.order_text",
            "type": "text",
            "phone_number_id": PHONE_NUMBER_ID,
            "text": "Quiero una moto económica",
        }
        await _handle_message_background_impl(msg_payload, BackgroundTasks())

    ctx = "ORDER-TEXT"
    for label in (
        "create_prospect_if_missing",
        "update_last_interaction",
        "transition_to_in_progress",
        "generate_and_update_summary",
        "save_message:user",
    ):
        _assert_precedes(timeline, label, ctx)
    # T3: save_message:model ya no precede al envío; vive en el egreso unificado.

    # Pin del comportamiento vigente: exactamente UN eco save('model') posterior al envío.
    first_send = _first_send_index(timeline)
    post_send_model_saves = [
        i for i, e in enumerate(timeline)
        if e == "save_message:model" and i > first_send
    ]
    assert len(post_send_model_saves) == 1, (
        f"[{ctx}] Comportamiento vigente alterado: se esperaba 1 eco save('model') "
        f"intra-egreso posterior al envío. Timeline: {timeline}"
    )


# ── ORDER-IMAGE ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_order_image_branch_moto_interest_precedes_egress():
    """
    Rama imagen: la persistencia bloqueante del match (moto_interest + PENDING)
    precede a la inferencia (pensar_respuesta) y al egreso de imagen hacia Meta.
    """
    item = make_catalog_item(1, random.Random(2026))
    canonical_price = format_cop(item["price"])
    matched_item = {
        "id": item["id"],
        "name": item["name"],
        "image_url": item["image_url"],
        "price": item["price"],
        "formatted_price": canonical_price,
        "summary": item["summary"],
        "active": True,
    }

    timeline = []
    mock_ms = _build_ms_mock(timeline)
    mock_wa = _build_whatsapp_service_mock(timeline)

    async def _pensar(*args, **kwargs):
        timeline.append("cerebro:pensar_respuesta")
        return f"Claro, la {item['name']} es una dura."

    mock_cerebro = MagicMock()
    mock_cerebro.pensar_respuesta = AsyncMock(side_effect=_pensar)
    mock_judge = MagicMock()
    mock_judge.analyze_response = AsyncMock(return_value=(True, ""))

    mock_vision = MagicMock()
    mock_vision.analyze_image = AsyncMock(return_value=f"MOTO_DETECTADA: {item['name']}")

    mock_catalog = MagicMock()
    mock_catalog.get_vision_catalog_projection = MagicMock(return_value=[])
    mock_catalog.match_catalog_item_by_image = MagicMock(return_value=matched_item)
    mock_catalog._rehydrate_formatted_price = MagicMock(return_value=canonical_price)

    mock_storage = MagicMock()
    mock_storage.download_media = AsyncMock(return_value=b"fake_image_bytes")

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.routers.whatsapp.judge_service", mock_judge), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_wa), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.message_buffer", _build_buffer_mock()), \
         patch("app.routers.whatsapp.VisionService", return_value=mock_vision), \
         patch("app.routers.whatsapp.storage_service", mock_storage), \
         patch("app.routers.whatsapp._send_whatsapp_image", _send_recorder("meta:send_image", timeline)), \
         patch("app.routers.whatsapp._send_whatsapp_message", _send_recorder("meta:send_text", timeline)), \
         patch("app.routers.whatsapp.db", MagicMock()):

        msg_payload = {
            "from": PHONE_RAW,
            "id": "wamid.order_image",
            "type": "image",
            "phone_number_id": PHONE_NUMBER_ID,
            "image": {"id": "media_order_img", "mime_type": "image/jpeg", "caption": ""},
        }
        await _handle_message_background_impl(msg_payload, BackgroundTasks())

    ctx = "ORDER-IMAGE"
    _assert_precedes(timeline, "create_prospect_if_missing", ctx)
    _assert_precedes(timeline, "update_prospect_summary", ctx)
    _assert_precedes(timeline, "generate_and_update_summary", ctx)

    # El commit del match también precede a la propia inferencia.
    i_update = timeline.index("update_prospect_summary")
    i_pensar = timeline.index("cerebro:pensar_respuesta")
    assert i_update < i_pensar, (
        f"[{ctx}] update_prospect_summary (índice {i_update}) debe preceder a "
        f"pensar_respuesta (índice {i_pensar}). Timeline: {timeline}"
    )


# ── ORDER-AUDIO ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_order_audio_branch_transcription_state_precedes_egress():
    """
    Rama audio: save(user=transcripción) → generate_and_update_summary → re-fetch
    → Juez → 1er envío Meta. La transcripción persistida es la fuente de verdad
    del siguiente turno (blinding fix, BOT-BUGFIX-AUDIO-REGRESSION-121).
    """
    item = make_catalog_item(2, random.Random(2026))
    transcription = "Quiero comprar una Victory"

    timeline = []
    history = [
        {"role": "user", "content": "hola"},
        {"role": "model", "content": "¿Qué tipo de moto buscas?"},
    ]
    mock_ms = _build_ms_mock(timeline)
    mock_ms.get_chat_history = AsyncMock(return_value=history)
    mock_wa = _build_whatsapp_service_mock(timeline)

    mock_cerebro = MagicMock()
    mock_cerebro.pensar_respuesta = AsyncMock(
        return_value=f"Perfecto. Precio: {format_cop(item['price'])}. Ficha Tecnica: {item['summary']}"
    )
    mock_judge = MagicMock()
    mock_judge.analyze_response = AsyncMock(return_value=(True, ""))

    mock_audio = MagicMock()
    mock_audio.transcribe_audio = AsyncMock(return_value=transcription)

    mock_storage = MagicMock()
    mock_storage.download_media = AsyncMock(return_value=b"fake_audio_bytes")

    mock_catalog = MagicMock()
    mock_catalog.search = MagicMock(return_value=[])
    mock_catalog.normalize_transcription = MagicMock(side_effect=lambda x: x)

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.routers.whatsapp.judge_service", mock_judge), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_wa), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.message_buffer", _build_buffer_mock()), \
         patch("app.routers.whatsapp.AudioService", return_value=mock_audio), \
         patch("app.routers.whatsapp.storage_service", mock_storage), \
         patch("app.routers.whatsapp._send_whatsapp_image", _send_recorder("meta:send_image", timeline)), \
         patch("app.routers.whatsapp._send_whatsapp_message", _send_recorder("meta:send_text", timeline)), \
         patch("app.routers.whatsapp.db", MagicMock()):

        msg_payload = {
            "from": PHONE_RAW,
            "id": "wamid.order_audio",
            "type": "audio",
            "phone_number_id": PHONE_NUMBER_ID,
            "media_id": "media_order_audio",
            "mime_type": "audio/ogg; codecs=opus",
        }
        await _handle_message_background_impl(msg_payload, BackgroundTasks())

    ctx = "ORDER-AUDIO"
    _assert_precedes(timeline, "save_message:user", ctx)
    _assert_precedes(timeline, "generate_and_update_summary", ctx)

    # Orden interno: la transcripción se persiste antes de la sincronía de memoria.
    i_save_user = timeline.index("save_message:user")
    i_summary = timeline.index("generate_and_update_summary")
    assert i_save_user < i_summary, (
        f"[{ctx}] save(user=transcripción) (índice {i_save_user}) debe preceder a "
        f"generate_and_update_summary (índice {i_summary}). Timeline: {timeline}"
    )


# ── DV-1: UNICIDAD DE APERTURA DE SESIÓN EN RAMA AUDIO ───────────────────────

@pytest.mark.asyncio
async def test_dv1_audio_single_session_opening_precedes_egress():
    """
    [M3-DEUDA-VIVA-001 / DV-1] Un turno de audio ejecuta UNA SOLA VEZ la apertura
    transicional de sesión: create_prospect_if_missing y update_last_interaction
    corren exclusivamente en el preámbulo común (_open_session_and_refresh).
    La doble ejecución heredada en _pipeline_audio (nacida en 24043c2, 2026-03-04,
    como init defensiva "Good practice" ya cubierta por el preámbulo) quedó
    erradicada. Pin adicional: ambas escrituras preceden al 1er envío Meta
    (Sincronía de Oficio, paridad con _assert_precedes).
    """
    item = make_catalog_item(2, random.Random(2026))
    transcription = "Quiero comprar una Victory"

    timeline = []
    history = [
        {"role": "user", "content": "hola"},
        {"role": "model", "content": "¿Qué tipo de moto buscas?"},
    ]
    mock_ms = _build_ms_mock(timeline)
    mock_ms.get_chat_history = AsyncMock(return_value=history)
    mock_wa = _build_whatsapp_service_mock(timeline)

    mock_cerebro = MagicMock()
    mock_cerebro.pensar_respuesta = AsyncMock(
        return_value=f"Perfecto. Precio: {format_cop(item['price'])}. Ficha Tecnica: {item['summary']}"
    )
    mock_judge = MagicMock()
    mock_judge.analyze_response = AsyncMock(return_value=(True, ""))

    mock_audio = MagicMock()
    mock_audio.transcribe_audio = AsyncMock(return_value=transcription)

    mock_storage = MagicMock()
    mock_storage.download_media = AsyncMock(return_value=b"fake_audio_bytes")

    mock_catalog = MagicMock()
    mock_catalog.search = MagicMock(return_value=[])
    mock_catalog.normalize_transcription = MagicMock(side_effect=lambda x: x)

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.routers.whatsapp.judge_service", mock_judge), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_wa), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.message_buffer", _build_buffer_mock()), \
         patch("app.routers.whatsapp.AudioService", return_value=mock_audio), \
         patch("app.routers.whatsapp.storage_service", mock_storage), \
         patch("app.routers.whatsapp._send_whatsapp_image", _send_recorder("meta:send_image", timeline)), \
         patch("app.routers.whatsapp._send_whatsapp_message", _send_recorder("meta:send_text", timeline)), \
         patch("app.routers.whatsapp.db", MagicMock()):

        msg_payload = {
            "from": PHONE_RAW,
            "id": "wamid.dv1_audio_single",
            "type": "audio",
            "phone_number_id": PHONE_NUMBER_ID,
            "media_id": "media_dv1_audio",
            "mime_type": "audio/ogg; codecs=opus",
        }
        await _handle_message_background_impl(msg_payload, BackgroundTasks())

    # DV-1-PIN-1 (unicidad): la erradicación deja exactamente 1 ejecución por turno.
    mock_ms.create_prospect_if_missing.assert_awaited_once()
    mock_ms.update_last_interaction.assert_awaited_once()

    # DV-1-PIN-2 (Sincronía de Oficio): persistencia ≺ 1er envío Meta.
    ctx = "DV-1-AUDIO"
    _assert_precedes(timeline, "create_prospect_if_missing", ctx)
    _assert_precedes(timeline, "update_last_interaction", ctx)


# ── ORDER-REACTION ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_order_reaction_habeas_write_precedes_inference():
    """
    Rama reacción 👍: la escritura de habeas_data_accepted (+ponytail PENDING) se
    confirma ANTES de cualquier inferencia y antes del egreso. Si esta escritura
    se delegara a background (fire-and-forget), el siguiente turno podría relanzar
    el script legal ya aprobado — el pin blinda la Sincronía de Oficio.
    """
    prospect = {
        "exists": True,
        "status": "PENDING",
        "chatbot_status": "ACTIVE",
        "celular": PHONE_E164,
        "ai_summary": "Resumen previo",
        "habeas_data_accepted": False,
        "human_help_requested": False,
    }
    timeline = []
    mock_ms = _build_ms_mock(timeline, prospect)
    mock_wa = _build_whatsapp_service_mock(timeline)

    async def _pensar(*args, **kwargs):
        timeline.append("cerebro:pensar_respuesta")
        return "Entendido, gracias por autorizar."

    mock_cerebro = MagicMock()
    mock_cerebro.pensar_respuesta = AsyncMock(side_effect=_pensar)
    mock_judge = MagicMock()
    mock_judge.analyze_response = AsyncMock(return_value=(True, ""))
    mock_catalog = MagicMock()
    mock_catalog.search = MagicMock(return_value=[])

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.routers.whatsapp.judge_service", mock_judge), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_wa), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.message_buffer", _build_buffer_mock()), \
         patch("app.routers.whatsapp._send_whatsapp_image", _send_recorder("meta:send_image", timeline)), \
         patch("app.routers.whatsapp._send_whatsapp_message", _send_recorder("meta:send_text", timeline)), \
         patch("app.routers.whatsapp.db", MagicMock()):

        msg_payload = {
            "from": PHONE_RAW,
            "id": "wamid.order_reaction",
            "type": "reaction",
            "phone_number_id": PHONE_NUMBER_ID,
            "reaction": {"message_id": "wamid.parent_1", "emoji": "👍"},
        }
        await _handle_message_background_impl(msg_payload, BackgroundTasks())

    ctx = "ORDER-REACTION"
    _assert_precedes(timeline, "update_prospect_summary", ctx)

    i_habeas = timeline.index("update_prospect_summary")
    i_pensar = timeline.index("cerebro:pensar_respuesta")
    assert i_habeas < i_pensar, (
        f"[{ctx}] La escritura habeas (índice {i_habeas}) debe preceder a "
        f"pensar_respuesta (índice {i_pensar}). Timeline: {timeline}"
    )


# ── ORDER-RESET ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_order_reset_wipe_precedes_confirmation_send():
    """
    Comando "/reset": el wipe nuclear (delete_prospect_completely) se confirma
    ANTES de enviar la confirmación al usuario. Si el envío precediera al wipe,
    un fallo de Firestore dejaría al usuario creyendo su sesión reiniciada sin
    serlo (dessincronía de estado transicional).
    """
    timeline = []
    mock_ms = _build_ms_mock(timeline)
    mock_wa = _build_whatsapp_service_mock(timeline)

    mock_cerebro = MagicMock()
    mock_cerebro.pensar_respuesta = AsyncMock(return_value="NO DEBE INVOCARSE")
    mock_judge = MagicMock()
    mock_judge.analyze_response = AsyncMock(return_value=(True, ""))
    mock_catalog = MagicMock()
    mock_catalog.search = MagicMock(return_value=[])

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.routers.whatsapp.judge_service", mock_judge), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_wa), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.message_buffer", _build_buffer_mock()), \
         patch("app.routers.whatsapp.db", MagicMock()):

        msg_payload = {
            "from": PHONE_RAW,
            "id": "wamid.order_reset",
            "type": "text",
            "phone_number_id": PHONE_NUMBER_ID,
            "text": "/reset",
        }
        await _handle_message_background_impl(msg_payload, BackgroundTasks())

    ctx = "ORDER-RESET"
    _assert_precedes(timeline, "delete_prospect_completely", ctx)

    i_wipe = timeline.index("delete_prospect_completely")
    i_send = _first_send_index(timeline)
    assert i_wipe < i_send, (
        f"[{ctx}] Wipe nuclear (índice {i_wipe}) debe preceder a la confirmación "
        f"(índice {i_send}). Timeline: {timeline}"
    )


# ── ORDER-FALLBACK (MANDATO v9.8.3) ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_order_judge_fallback_marks_human_help_before_fallback_send():
    """
    [MANDATO v9.8.3] Ante agotamiento de reintentos del Juez (3 rechazos), el
    monolito marca el estado PRIMERO (set_human_help_status=True → ponytail
    DEPRIORITIZED → save model fallback) y DESPUÉS envía el mensaje de fallback.
    Garantiza CRM actualizado incluso si Meta falla temporalmente.
    """
    timeline = []
    mock_ms = _build_ms_mock(timeline)
    mock_wa = _build_whatsapp_service_mock(timeline)

    mock_cerebro = MagicMock()
    mock_cerebro.pensar_respuesta = AsyncMock(return_value="Respuesta sin precio ni imagen")
    mock_judge = MagicMock()
    mock_judge.analyze_response = AsyncMock(
        return_value=(False, "C1_VISUAL_LOCK: respuesta sin precio canónico")
    )
    mock_catalog = MagicMock()
    mock_catalog.search = MagicMock(return_value=[])

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.routers.whatsapp.judge_service", mock_judge), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_wa), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.message_buffer", _build_buffer_mock()), \
         patch("app.routers.whatsapp._send_whatsapp_image", _send_recorder("meta:send_image", timeline)), \
         patch("app.routers.whatsapp._send_whatsapp_message", _send_recorder("meta:send_text", timeline)), \
         patch("app.routers.whatsapp.db", MagicMock()):

        msg_payload = {
            "from": PHONE_RAW,
            "id": "wamid.order_fallback",
            "type": "text",
            "phone_number_id": PHONE_NUMBER_ID,
            "text": "¿Cuánto cuesta esa moto?",
        }
        await _handle_message_background_impl(msg_payload, BackgroundTasks())

    ctx = "ORDER-FALLBACK"
    # El Juez agotó los 3 intentos (max_retries=2 → attempts 1..3).
    assert mock_judge.analyze_response.await_count == 3

    for label in ("set_human_help_status", "update_prospect_summary", "save_message:model"):
        _assert_precedes(timeline, label, ctx)

    # Correlación pineada: set_human_help precede a ponytail DEPRIORITIZED (CH-4).
    i_help = timeline.index("set_human_help_status")
    i_ponytail = timeline.index("update_prospect_summary")
    assert i_help < i_ponytail, (
        f"[{ctx}] set_human_help_status (índice {i_help}) debe preceder a "
        f"update_prospect_summary DEPRIORITIZED (índice {i_ponytail}). Timeline: {timeline}"
    )
