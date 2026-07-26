"""
Red de Caracterización E2E — Etapa 3 Wave 05-01 [BOT-BUILD-ETAPA3-WAVE01-CHARACTERIZATION-001]

Captura el comportamiento ACTUAL del monolito `_handle_message_background_impl`
(correcto o no) por cada rama de entrada del webhook, como línea base de verdad
previa a la fragmentación RF-5 (waves 05-03 a 05-05). Algoritmo de Feathers
(docs/OPENCODE.md Fase 7): pinea el comportamiento vigente, no el deseado.

Pins E2E (rama → invariantes capturados):
  E2E-TEXT      Flujo embudo completo: READ-FIRST → save user → LINEAR BLOCKING →
                Juez → save model → egreso unificado con PCC Pro (precio/imagen/ficha).
  E2E-IMAGE     Visión→match catálogo: update_prospect_summary(moto_interest+PENDING)
                bloqueante, pensar_respuesta con prompt canónico, Visual Lock
                post-generación inyecta imagen/precio, Juez NO interviene (comportamiento
                vigente), egreso imagen con URL canónica.
  E2E-AUDIO     Descarga→transcripción→alineación fonética→save user(transcription)→
                summary con last_bot_question→Juez→egreso.
  E2E-REACTION  👍 → debounce → update_prospect_summary(habeas+PENDING) ANTES de
                pensar_respuesta, cuerpo mutado a "Sí" [BOT-PONYTAIL-200].
  E2E-RESET     "/reset" → wipe nuclear → confirmación; jamás invoca pensar_respuesta;
                liberación de _active_resets (blindaje de cleanup).
  E2E-STATUSES  Delegación BackgroundTasks en la frontera + persistencia bloqueante
                del acuse vía update_whatsapp_status [ARCH-BULK-META-010].

Regla del ticket: cero valores numéricos fijos — todo monto se referencia desde
tests/factories.py y se valida con los validadores regex PCC Pro (tests/validators.py).
"""
import json

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import BackgroundTasks

from app.routers.whatsapp import (
    webhook_handler,
    _handle_message_background_impl,
    _handle_statuses_background,
)
from tests.factories import make_catalog_item, format_cop
from tests import validators
import random

PHONE_E164 = "+573192564288"
PHONE_RAW = "573192564288"
PHONE_NUMBER_ID = "999999"


# ── Builders canónicos (patrón probado en test_characterization_etapa1.py) ─────

def _factory_item(idx: int = 0) -> dict:
    """Ítem sintético determinista (seed fija) — los tests REFERENCIAN sus valores."""
    return make_catalog_item(idx, random.Random(2026))


def _build_ms_mock(prospect: dict | None = None) -> MagicMock:
    """MemoryService mockeado con la superficie completa que el monolito invoca.

    WHY get_or_create_prospect explícito: el guard BOT-174 (whatsapp.py L1386-1405)
    ramifica sobre `isinstance(ms.get_or_create_prospect.return_value, Mock)`. Un
    test heredado (test_pcc_ficha_tecnica.py::test_brilla_gases_real_firestore_cuotas)
    expulsa `unittest.mock` de sys.modules, recargando clases NUEVAS de Mock y
    rompiendo la identidad de isinstance sobre mocks creados previamente. Configurar
    el valor explícito (dict, no Mock) es la rama que el guard sanciona para tests
    y es inmune a esa polución de identidad de clases.
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
    return ms


def _build_buffer_mock() -> MagicMock:
    buffer = MagicMock()
    buffer.add_message = AsyncMock(return_value=True)
    buffer.is_task_active = MagicMock(return_value=True)
    buffer.get_aggregated_message = AsyncMock(return_value=None)
    buffer.clear_buffer = AsyncMock()
    buffer.debounce_seconds = 0.01
    return buffer


def _build_cerebro_mock(response_text: str) -> MagicMock:
    cerebro = MagicMock()
    cerebro.pensar_respuesta = AsyncMock(return_value=response_text)
    return cerebro


def _build_judge_mock(verdict=(True, "")) -> MagicMock:
    judge = MagicMock()
    judge.analyze_response = AsyncMock(return_value=verdict)
    return judge


def _build_whatsapp_service_mock() -> MagicMock:
    wa = MagicMock()
    wa.mark_as_read = AsyncMock()
    wa.send_text_message = AsyncMock()
    wa.send_image_message = AsyncMock()
    return wa


# ── E2E-TEXT ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_e2e_text_branch_full_funnel():
    """
    Rama texto: el monolito ejecuta el embudo completo con egreso unificado.
    Pin PCC Pro: la respuesta egresada conserva precio canónico, imagen markdown
    y ficha técnica (validadores regex, valores referenciados al ítem de fábrica).
    Pin de comportamiento vigente (Feathers): save_message("model") ocurre DOS veces
    — una pre-egreso (L1558, texto crudo con markdown) y una intra-egreso (L1906,
    texto limpio). CH-5 no lo observa porque mockea el egreso completo. La wave
    05-05 podrá normalizar esta duplicidad SOLO con aprobación del Auditor.
    """
    item = _factory_item()
    canonical_price = format_cop(item["price"])
    llm_response = (
        f"Mira esta {item['name']}. Precio: {canonical_price}. "
        f"Ficha Tecnica: {item['summary']} "
        f"![{item['name']}]({item['image_url']})"
    )

    mock_ms = _build_ms_mock()
    mock_cerebro = _build_cerebro_mock(llm_response)
    mock_judge = _build_judge_mock()
    mock_wa = _build_whatsapp_service_mock()
    mock_buffer = _build_buffer_mock()
    mock_catalog = MagicMock()
    mock_catalog.search = MagicMock(return_value=[])

    send_image = AsyncMock(return_value=True)
    send_text = AsyncMock(return_value=True)

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.routers.whatsapp.judge_service", mock_judge), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_wa), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.message_buffer", mock_buffer), \
         patch("app.routers.whatsapp._send_whatsapp_image", send_image), \
         patch("app.routers.whatsapp._send_whatsapp_message", send_text), \
         patch("app.routers.whatsapp.db", MagicMock()):

        msg_payload = {
            "from": PHONE_RAW,
            "id": "wamid.e2e_text",
            "type": "text",
            "phone_number_id": PHONE_NUMBER_ID,
            "text": "Quiero una moto económica",
        }
        await _handle_message_background_impl(msg_payload, BackgroundTasks())

    # READ-FIRST: acuse de lectura antes de cualquier lógica.
    mock_wa.mark_as_read.assert_awaited_once_with("wamid.e2e_text", phone_number_id=PHONE_NUMBER_ID)

    # Persistencia del turno de usuario con el cuerpo crudo.
    mock_ms.save_message.assert_any_call(PHONE_E164, "user", "Quiero una moto económica")

    # LINEAR BLOCKING: sincronía de memoria antes de la inferencia.
    mock_ms.generate_and_update_summary.assert_awaited_once()
    # Juez de fundamentación: exactamente 1 auditoría (aprobada al primer intento).
    mock_judge.analyze_response.assert_awaited_once()

    # Egreso: imagen con URL canónica y caption que conserva precio + ficha (PCC Pro).
    send_image.assert_awaited_once()
    _, image_url, *rest = send_image.call_args.args
    caption = send_image.call_args.kwargs.get("caption", "")
    assert image_url == item["image_url"]
    validators.assert_price_consistency(caption, item["price"])
    validators.assert_ficha_explicit(llm_response)
    validators.assert_image_reference(llm_response)

    # Comportamiento vigente pineado: doble save_message("model") (pre-egreso + eco intra-egreso).
    model_saves = [c for c in mock_ms.save_message.call_args_list if c.args[1] == "model"]
    assert len(model_saves) == 2, (
        f"Comportamiento vigente alterado: se esperaban 2 save_message('model') "
        f"(pre-egreso + eco intra-egreso), hallado: {model_saves}"
    )


# ── E2E-IMAGE ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_e2e_image_branch_moto_match_visual_lock():
    """
    Rama imagen (moto detectada): match canónico → persistencia bloqueante de
    moto_interest + ponytail_status=PENDING [BOT-PONYTAIL-200] → cerebro con prompt
    canónico → Visual Lock post-generación (inyección de imagen y precio si el LLM
    los omite) → egreso imagen con URL canónica y precio en caption.
    Pin de comportamiento vigente: el Juez NO audita esta rama.
    """
    item = _factory_item(idx=1)
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

    mock_ms = _build_ms_mock()
    # El LLM omite deliberadamente precio e imagen → el Visual Lock debe inyectarlos.
    mock_cerebro = _build_cerebro_mock(f"Claro, la {item['name']} es una dura.")
    mock_judge = _build_judge_mock()
    mock_wa = _build_whatsapp_service_mock()
    mock_buffer = _build_buffer_mock()

    mock_vision = MagicMock()
    mock_vision.analyze_image = AsyncMock(return_value=f"MOTO_DETECTADA: {item['name']}")

    mock_catalog = MagicMock()
    mock_catalog.get_vision_catalog_projection = MagicMock(return_value=[])
    mock_catalog.match_catalog_item_by_image = MagicMock(return_value=matched_item)
    mock_catalog._rehydrate_formatted_price = MagicMock(return_value=canonical_price)

    mock_storage = MagicMock()
    mock_storage.download_media = AsyncMock(return_value=b"fake_image_bytes")

    send_image = AsyncMock(return_value=True)
    send_text = AsyncMock(return_value=True)

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.routers.whatsapp.judge_service", mock_judge), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_wa), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.message_buffer", mock_buffer), \
         patch("app.routers.whatsapp.VisionService", return_value=mock_vision), \
         patch("app.routers.whatsapp.storage_service", mock_storage), \
         patch("app.routers.whatsapp._send_whatsapp_image", send_image), \
         patch("app.routers.whatsapp._send_whatsapp_message", send_text), \
         patch("app.routers.whatsapp.db", MagicMock()):

        msg_payload = {
            "from": PHONE_RAW,
            "id": "wamid.e2e_image",
            "type": "image",
            "phone_number_id": PHONE_NUMBER_ID,
            "image": {"id": "media_e2e_img", "mime_type": "image/jpeg", "caption": ""},
        }
        await _handle_message_background_impl(msg_payload, BackgroundTasks())

    # Pipeline de visión ejecutado con bytes descargados.
    mock_storage.download_media.assert_awaited_once_with("media_e2e_img")
    mock_vision.analyze_image.assert_awaited_once()

    # Persistencia bloqueante del match [BOT-PONYTAIL-200], payload exacto.
    mock_ms.update_prospect_summary.assert_any_call(
        PHONE_E164, "", {"moto_interest": item["name"], "ponytail_status": "PENDING"}
    )

    # El Juez NO interviene en la rama imagen (comportamiento vigente pineado).
    mock_judge.analyze_response.assert_not_called()

    # Visual Lock: el egreso usa la URL canónica aunque el LLM la omitió, y el
    # caption porta el precio canónico (PCC Pro, valor referenciado al ítem).
    send_image.assert_awaited_once()
    _, image_url, *rest = send_image.call_args.args
    caption = send_image.call_args.kwargs.get("caption", "")
    assert image_url == item["image_url"]
    validators.assert_price_consistency(caption, item["price"])


# ── E2E-AUDIO ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_e2e_audio_branch_transcription_lineage():
    """
    Rama audio: descarga → transcripción → alineación fonética → save user con la
    TRANSCRIPCIÓN (blinding fix) → summary anclado a last_bot_question → Juez →
    egreso texto. Pin: la transcripción (no '[AUDIO]') es lo que persiste y
    alimenta la inferencia.
    """
    item = _factory_item(idx=2)
    canonical_price = format_cop(item["price"])
    transcription = "Quiero comprar una Victory"
    llm_response = (
        f"Perfecto. Precio: {canonical_price}. "
        f"Ficha Tecnica: {item['summary']}"
    )

    history = [
        {"role": "user", "content": "hola"},
        {"role": "model", "content": "¿Qué tipo de moto buscas?"},
    ]
    mock_ms = _build_ms_mock()
    mock_ms.get_chat_history = AsyncMock(return_value=history)
    mock_cerebro = _build_cerebro_mock(llm_response)
    mock_judge = _build_judge_mock()
    mock_wa = _build_whatsapp_service_mock()
    mock_buffer = _build_buffer_mock()

    mock_audio = MagicMock()
    mock_audio.transcribe_audio = AsyncMock(return_value=transcription)

    mock_storage = MagicMock()
    mock_storage.download_media = AsyncMock(return_value=b"fake_audio_bytes")

    mock_catalog = MagicMock()
    mock_catalog.search = MagicMock(return_value=[])
    mock_catalog.normalize_transcription = MagicMock(side_effect=lambda x: x)

    send_image = AsyncMock(return_value=True)
    send_text = AsyncMock(return_value=True)

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.routers.whatsapp.judge_service", mock_judge), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_wa), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.message_buffer", mock_buffer), \
         patch("app.routers.whatsapp.AudioService", return_value=mock_audio), \
         patch("app.routers.whatsapp.storage_service", mock_storage), \
         patch("app.routers.whatsapp._send_whatsapp_image", send_image), \
         patch("app.routers.whatsapp._send_whatsapp_message", send_text), \
         patch("app.routers.whatsapp.db", MagicMock()):

        msg_payload = {
            "from": PHONE_RAW,
            "id": "wamid.e2e_audio",
            "type": "audio",
            "phone_number_id": PHONE_NUMBER_ID,
            "media_id": "media_e2e_audio",
            "mime_type": "audio/ogg; codecs=opus",
        }
        await _handle_message_background_impl(msg_payload, BackgroundTasks())

    mock_storage.download_media.assert_awaited_once_with("media_e2e_audio")
    mock_audio.transcribe_audio.assert_awaited_once_with(b"fake_audio_bytes", "audio/ogg; codecs=opus")

    # Blinding fix: persiste la transcripción real, jamás el placeholder [AUDIO].
    mock_ms.save_message.assert_any_call(PHONE_E164, "user", transcription)

    # Anclaje de linaje: summary con la última pregunta del bot extraída del historial.
    mock_ms.generate_and_update_summary.assert_awaited_once_with(
        PHONE_E164,
        f"User sent audio. Transcription: {transcription}",
        mock_cerebro,
        last_bot_question="¿Qué tipo de moto buscas?",
    )

    # Juez audita la rama audio (a diferencia de la rama imagen).
    mock_judge.analyze_response.assert_awaited_once()

    # Egreso texto con PCC Pro sobre el contenido final.
    send_text.assert_awaited_once()
    egress_text = send_text.call_args.args[1]
    validators.assert_price_consistency(egress_text, item["price"])
    validators.assert_ficha_explicit(egress_text)


# ── E2E-REACTION ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_e2e_reaction_positive_habeas_intercept():
    """
    Rama reacción 👍: tras debounce/agregación, el intercept persiste
    {"habeas_data_accepted": True, "ponytail_status": "PENDING"} de forma
    BLOQUEANTE y ANTES de cualquier inferencia; el cuerpo muta a "Sí" y fluye
    por la rama texto [BOT-PONYTAIL-200 / quick-138].
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
    mock_ms = _build_ms_mock(prospect)
    mock_cerebro = _build_cerebro_mock("Entendido, gracias por autorizar.")
    mock_judge = _build_judge_mock()
    mock_wa = _build_whatsapp_service_mock()
    mock_buffer = _build_buffer_mock()
    mock_catalog = MagicMock()
    mock_catalog.search = MagicMock(return_value=[])

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.routers.whatsapp.judge_service", mock_judge), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_wa), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.message_buffer", mock_buffer), \
         patch("app.routers.whatsapp._process_and_send_egress_message", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.db", MagicMock()):

        msg_payload = {
            "from": PHONE_RAW,
            "id": "wamid.e2e_reaction",
            "type": "reaction",
            "phone_number_id": PHONE_NUMBER_ID,
            "reaction": {"message_id": "wamid.parent_1", "emoji": "👍"},
        }
        await _handle_message_background_impl(msg_payload, BackgroundTasks())

    # Intercept Habeas Data: payload exacto, persistido por la vía bloqueante.
    mock_ms.update_prospect_summary.assert_any_call(
        PHONE_E164, "", {"habeas_data_accepted": True, "ponytail_status": "PENDING"}
    )

    # El cuerpo mutado a "Sí" alimenta la inferencia (quick-138).
    pensar_args = mock_cerebro.pensar_respuesta.call_args
    assert pensar_args.args[0] == "Sí", (
        f"La reacción positiva debe mutar el cuerpo a 'Sí'; recibido: {pensar_args.args[0]!r}"
    )


# ── E2E-RESET ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_e2e_reset_command_nuclear_wipe():
    """
    Comando "/reset": wipe nuclear síncrono + limpieza de buffer + confirmación
    determinista. Pin: jamás invoca pensar_respuesta y libera _active_resets
    (blindaje de cleanup, finally L1270-1273).
    """
    import app.routers.whatsapp as whatsapp_module

    mock_ms = _build_ms_mock()
    mock_cerebro = _build_cerebro_mock("NO DEBE INVOCARSE")
    mock_judge = _build_judge_mock()
    mock_wa = _build_whatsapp_service_mock()
    mock_buffer = _build_buffer_mock()
    mock_catalog = MagicMock()
    mock_catalog.search = MagicMock(return_value=[])

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.routers.whatsapp.judge_service", mock_judge), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_wa), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.message_buffer", mock_buffer), \
         patch("app.routers.whatsapp.db", MagicMock()):

        msg_payload = {
            "from": PHONE_RAW,
            "id": "wamid.e2e_reset",
            "type": "text",
            "phone_number_id": PHONE_NUMBER_ID,
            "text": "/reset",
        }
        await _handle_message_background_impl(msg_payload, BackgroundTasks())

    mock_ms.delete_prospect_completely.assert_awaited_once_with(PHONE_E164)
    mock_buffer.clear_buffer.assert_awaited_with(PHONE_E164)

    # Confirmación determinista enviada al usuario (Sincronía de Feedback).
    confirmation_texts = [c.args[1] for c in mock_wa.send_text_message.call_args_list]
    assert any("reiniciada" in t for t in confirmation_texts), (
        f"Sin confirmación de reset en los envíos: {confirmation_texts}"
    )

    # El wipe nuclear nunca alcanza la inferencia.
    mock_cerebro.pensar_respuesta.assert_not_called()

    # Blindaje de cleanup: el teléfono no queda atrapado en _active_resets.
    assert PHONE_E164 not in whatsapp_module._active_resets


# ── E2E-STATUSES ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_e2e_statuses_branch_delegation_and_persistence():
    """
    Rama statuses [ARCH-BULK-META-010]: (1) la frontera responde 200 y delega a
    BackgroundTasks (fuera del embudo comercial — acuses de entrega); (2) el handler
    delegado persiste el acuse con await BLOQUEANTE vía update_whatsapp_status,
    con teléfono normalizado E.164 y errores propagados.
    """
    payload_dict = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "123",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "123456", "phone_number_id": PHONE_NUMBER_ID},
                    "statuses": [{
                        "id": "wamid.e2e_status",
                        "recipient_id": PHONE_RAW,
                        "status": "read",
                        "timestamp": "1672531199",
                    }],
                },
                "field": "messages",
            }],
        }],
    }

    mock_request = MagicMock()
    mock_request.app.state.catalog_ready = True

    async def mock_body():
        return json.dumps(payload_dict).encode("utf-8")

    mock_request.body = mock_body
    mock_request.headers = {"X-Hub-Signature-256": "sha256=dummy"}

    mock_catalog = MagicMock()
    mock_catalog.get_all_items = MagicMock(return_value=[])

    with patch("app.routers.whatsapp.settings") as mock_settings, \
         patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog):

        mock_settings.whatsapp_app_secret = None
        mock_settings.min_catalog_items = 0
        mock_settings.cloud_tasks_queue_path = None
        mock_settings.task_processor_url = None

        background_tasks = BackgroundTasks()
        response = await webhook_handler(mock_request, background_tasks)

    assert response == {"status": "received"}
    assert len(background_tasks.tasks) == 1
    assert background_tasks.tasks[0].func is _handle_statuses_background
    status_data = background_tasks.tasks[0].args[0]
    assert status_data["status"] == "read"

    # Persistencia bloqueante del acuse (await dentro del handler delegado).
    mock_ms = MagicMock()
    mock_ms.update_whatsapp_status = AsyncMock()

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms):

        await _handle_statuses_background(status_data)

    mock_ms.update_whatsapp_status.assert_awaited_once_with(
        phone_number=PHONE_E164,
        status_value="read",
        wamid="wamid.e2e_status",
        errors=[],
    )
