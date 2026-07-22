"""
Red de Caracterización (Feathers) — Etapa 1 [BOT-BUILD-REFACTOR-ETAPA1-WAVE1-199]

Captura el comportamiento ACTUAL del flujo Meta→Firestore (correcto o no) como red
de seguridad previa a la fragmentación del enrutador (docs/OPENCODE.md Fase 7).

Pins:
  CH-1  Comportamiento actual (DEFECTUOSO) de doble procesamiento en task_processor.
        WHY: Feathers pinea el comportamiento vigente. El Plan 03-02 (RF-1, Resolución
        R-B del Auditor) INVERTIRÁ esta aserción a exactly-once.
  CH-2  La dedup de ingreso (register_wamid real) gobierna también el encolado a
        Cloud Tasks.
  CH-3  Orden de la secuencia transicional CRM en rama texto:
        create_prospect_if_missing → update_last_interaction → transition_to_in_progress
        (+ re-fetch anti-stale HOTFIX v9.8.3).
  CH-4  Invariante BOT-PONYTAIL-200: ante HANDOFF_TRIGGERED, set_human_help_status(True)
        precede a update_prospect_summary(..., {"ponytail_status": "DEPRIORITIZED"}).
  CH-5  Egreso unificado (BOT-BUGFIX-UNIFIED-EGRESS-PIPELINE-125): exactamente 1
        save_message("user") + 1 save_message("model") + 1 envío de egreso.
"""
import json

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import BackgroundTasks, HTTPException
from tests.factories import make_catalog
from google.api_core import exceptions as gcp_exceptions

from app.routers.whatsapp import webhook_handler, task_processor
from app.services.memory_service import MemoryService
from app.services.message_buffer import MessageBuffer

PHONE_E164 = "+573192564288"


def _build_payload(wamid: str, text: str = "Quiero una Raider 125") -> dict:
    """Payload canónico de webhook de Meta (mensaje de texto)."""
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "123",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "123456", "phone_number_id": "999999"},
                    "messages": [{
                        "from": "573192564288",
                        "id": wamid,
                        "timestamp": "1672531199",
                        "text": {"body": text},
                        "type": "text"
                    }]
                },
                "field": "messages"
            }]
        }]
    }


def _mock_webhook_request(payload_dict: dict) -> MagicMock:
    mock_request = MagicMock()

    async def mock_body():
        return json.dumps(payload_dict).encode("utf-8")

    mock_request.body = mock_body
    mock_request.headers = {"X-Hub-Signature-256": "sha256=dummy"}
    # [Incidente H-A · HA-2] Guard estricto: el request debe presentar catálogo listo.
    mock_request.app.state.catalog_ready = True
    return mock_request


def _build_impl_mocks(cerebro_response: str):
    """
    Set de mocks probado en test_webhook_sync_block.py para conducir
    `_handle_message_background_impl` por la rama de texto hasta el egreso.
    """
    mock_memory_service = MagicMock()
    mock_memory_service.create_prospect_if_missing = AsyncMock()
    mock_memory_service.update_last_interaction = AsyncMock()
    mock_memory_service.transition_to_in_progress = AsyncMock()
    mock_memory_service.generate_and_update_summary = AsyncMock()
    mock_memory_service.save_message = AsyncMock()
    mock_memory_service.set_human_help_status = AsyncMock()
    mock_memory_service.update_prospect_summary = AsyncMock()
    mock_memory_service.get_prospect_data = AsyncMock(return_value={
        "exists": True,
        "status": "IN_PROGRESS",
        "chatbot_status": "ACTIVE",
        "name": "Juan Test",
        "celular": PHONE_E164
    })
    mock_memory_service.get_chat_history = AsyncMock(return_value=[])

    mock_cerebro = MagicMock()
    mock_cerebro.pensar_respuesta = AsyncMock(return_value=cerebro_response)

    mock_judge = MagicMock()
    mock_judge.analyze_response = AsyncMock(return_value=(True, ""))

    mock_whatsapp = MagicMock()
    mock_whatsapp.mark_as_read = AsyncMock()
    mock_whatsapp.send_text_message = AsyncMock()

    mock_catalog = MagicMock()
    mock_catalog.search = MagicMock(return_value=[])
    mock_catalog.get_all_items = MagicMock(return_value=[])

    mock_message_buffer = AsyncMock()
    mock_message_buffer.add_message = AsyncMock(return_value=True)
    mock_message_buffer.is_task_active = MagicMock(return_value=True)
    mock_message_buffer.clear_buffer = AsyncMock()
    mock_message_buffer.debounce_seconds = 0.01

    return (mock_memory_service, mock_cerebro, mock_judge, mock_whatsapp,
            mock_catalog, mock_message_buffer)


@pytest.mark.asyncio
async def test_ch1_task_processor_duplicate_delivery_exactly_once():
    """
    [PIN INVERTIDO — RF-1 / Resolución R-B / Plan 03-02]
    Historial Feathers: WAVE1-199 pineó el comportamiento DEFECTUOSO vigente
    (doble entrega del mismo payload a /task-processor → 2 invocaciones del pipeline).
    La barrera durable 'processed_webhooks' (Piso 2, reclamo create-only en el embudo
    unificado `_handle_message_background`) invierte el pin: la segunda entrega es
    filtrada por el reclamo y el impacto en base de datos ocurre UNA sola vez
    (efecto exactly-once bajo reintentos de Cloud Tasks).
    """
    payload_dict = _build_payload("wamid.ch1_duplicate")
    mock_request = MagicMock()
    # [Incidente H-A · HA-2] Guard estricto: el request debe presentar catálogo listo.
    mock_request.app.state.catalog_ready = True

    async def mock_json():
        return payload_dict

    mock_request.json = mock_json
    mock_request.headers = {"X-Task-Token": "secret_token"}

    mock_catalog = MagicMock()
    mock_catalog.get_all_items = MagicMock(return_value=make_catalog(10))

    mock_ms = MagicMock()
    # Primera entrega reclama (True); la duplicada encuentra AlreadyExists (False).
    mock_ms.claim_webhook_idempotency = AsyncMock(side_effect=[True, False])
    mock_ms.release_webhook_claim = AsyncMock()

    with patch("app.routers.whatsapp.settings") as mock_settings, \
         patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp._handle_message_background_impl", new_callable=AsyncMock) as mock_impl:

        mock_settings.webhook_verify_token = "secret_token"
        mock_settings.min_catalog_items = 0
        mock_settings.webhook_idempotency_enabled = True

        res_1 = await task_processor(mock_request, BackgroundTasks())
        res_2 = await task_processor(mock_request, BackgroundTasks())

        # Cloud Tasks recibe HTTP 200 en ambas entregas (la duplicada es no-op controlado).
        assert res_1 == {"status": "processed", "type": "message"}
        assert res_2 == {"status": "processed", "type": "message"}
        # EFECTO EXACTLY-ONCE: el pipeline transaccional se ejecutó una sola vez.
        assert mock_impl.call_count == 1
        assert mock_ms.claim_webhook_idempotency.await_count == 2
        mock_ms.release_webhook_claim.assert_not_called()


@pytest.mark.asyncio
async def test_rf1_claim_released_on_processing_failure_allows_retry():
    """
    [RF-1 — Contrato de fallo obligatorio] Si el procesamiento lanza excepción,
    el embudo libera el reclamo durable (release_webhook_claim) y propaga el error
    para que Cloud Tasks reintente (HTTP 500); el reintento posterior vuelve a
    reclamar y procesa con éxito (reproceso habilitado por la liberación, TTL 120s).
    """
    payload_dict = _build_payload("wamid.rf1_release")
    mock_request = MagicMock()
    # [Incidente H-A · HA-2] Guard estricto: el request debe presentar catálogo listo.
    mock_request.app.state.catalog_ready = True

    async def mock_json():
        return payload_dict

    mock_request.json = mock_json
    mock_request.headers = {"X-Task-Token": "secret_token"}

    mock_catalog = MagicMock()
    mock_catalog.get_all_items = MagicMock(return_value=make_catalog(10))

    mock_ms = MagicMock()
    # Intento 1 reclama OK; el reintento (tras liberación) vuelve a reclamar OK.
    mock_ms.claim_webhook_idempotency = AsyncMock(side_effect=[True, True])
    mock_ms.release_webhook_claim = AsyncMock()

    mock_impl = AsyncMock(side_effect=[RuntimeError("forced pipeline failure"), None])

    with patch("app.routers.whatsapp.settings") as mock_settings, \
         patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp._handle_message_background_impl", mock_impl):

        mock_settings.webhook_verify_token = "secret_token"
        mock_settings.min_catalog_items = 0
        mock_settings.webhook_idempotency_enabled = True

        # Entrega 1: fallo forzado → 500 para retry de Cloud Tasks + reclamo liberado.
        with pytest.raises(HTTPException) as exc_info:
            await task_processor(mock_request, BackgroundTasks())
        assert exc_info.value.status_code == 500
        mock_ms.release_webhook_claim.assert_awaited_once_with("wamid.rf1_release", PHONE_E164)

        # Entrega 2 (reintento Cloud Tasks): reclama de nuevo y procesa con éxito.
        res_retry = await task_processor(mock_request, BackgroundTasks())
        assert res_retry == {"status": "processed", "type": "message"}
        assert mock_impl.call_count == 2
        assert mock_ms.release_webhook_claim.await_count == 1


@pytest.mark.asyncio
async def test_rf1_memory_service_claim_create_only_semantics():
    """
    [RF-1] Semántica create-only del puerto de persistencia MemoryService:
    - create() exitoso → True (primera entrega) con payload wamid/phone/claimed_at
      en la colección 'processed_webhooks'.
    - AlreadyExists → False (entrega duplicada) sin propagar excepción.
    - release_webhook_claim → delete() invocado; un fallo de delete se loguea
      y NO se propaga (best-effort: jamás enmascara la excepción original).
    """
    mock_db = MagicMock()
    doc_ref = mock_db.collection.return_value.document.return_value
    doc_ref.create = AsyncMock()
    doc_ref.delete = AsyncMock()

    ms = MemoryService(mock_db)

    # 1. Primera entrega: reclamo exitoso con payload canónico.
    claimed = await ms.claim_webhook_idempotency("wamid.rf1_unit", PHONE_E164)
    assert claimed is True
    create_payload = doc_ref.create.await_args.args[0]
    assert create_payload["wamid"] == "wamid.rf1_unit"
    assert create_payload["phone"] == PHONE_E164
    assert "claimed_at" in create_payload
    mock_db.collection.assert_called_with("processed_webhooks")

    # 2. Entrega duplicada: AlreadyExists → False sin excepción.
    doc_ref.create = AsyncMock(side_effect=gcp_exceptions.AlreadyExists("document exists"))
    claimed_dup = await ms.claim_webhook_idempotency("wamid.rf1_unit", PHONE_E164)
    assert claimed_dup is False

    # 3. Liberación: delete() invocado sobre el mismo documento.
    await ms.release_webhook_claim("wamid.rf1_unit", PHONE_E164)
    doc_ref.delete.assert_awaited_once()

    # 4. Fallo de liberación: best-effort, no propaga (auditoría vía logger.exception).
    doc_ref.delete = AsyncMock(side_effect=RuntimeError("firestore outage"))
    await ms.release_webhook_claim("wamid.rf1_unit", PHONE_E164)  # No debe lanzar.


@pytest.mark.asyncio
async def test_ch2_ingress_dedup_governs_cloud_tasks_enqueue():
    """
    La barrera de ingreso (`register_wamid` con MessageBuffer REAL) también
    gobierna el encolado: un segundo webhook con el mismo wamid es ignorado
    y NO encola una segunda tarea.
    """
    payload_dict = _build_payload("wamid.ch2_ingress_gate")
    mb_instance = MessageBuffer(debounce_seconds=1.0)

    mock_catalog = MagicMock()
    mock_catalog.get_all_items = MagicMock(return_value=make_catalog(10))

    with patch("app.routers.whatsapp.settings") as mock_settings, \
         patch("app.routers.whatsapp._enqueue_cloud_task", new_callable=AsyncMock) as mock_enqueue, \
         patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.message_buffer", mb_instance), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog):

        mock_settings.whatsapp_app_secret = None  # Bypass signature
        mock_settings.cloud_tasks_queue_path = "projects/p/locations/us-central1/queues/q"
        mock_settings.task_processor_url = "https://svc.run.app/webhook/task-processor"
        mock_settings.min_catalog_items = 0

        res_1 = await webhook_handler(_mock_webhook_request(payload_dict), BackgroundTasks())
        res_2 = await webhook_handler(_mock_webhook_request(payload_dict), BackgroundTasks())

        assert res_1 == {"status": "received"}
        assert res_2 == {"status": "ignored", "procesado": False}
        assert mock_enqueue.call_count == 1


@pytest.mark.asyncio
async def test_ch3_transitional_crm_sequence_order_text_branch():
    """
    [RF-2 baseline] En la rama texto de `_handle_message_background_impl`, la
    secuencia transicional CRM se ejecuta en orden estricto:
    create_prospect_if_missing → update_last_interaction → transition_to_in_progress
    [ARCH-BULK-META-010], seguida de re-fetch anti-stale [HOTFIX v9.8.3]
    (get_prospect_data ≥ 2 lecturas: inicial + refresco post-transición).
    """
    from app.routers.whatsapp import _handle_message_background_impl

    (mock_ms, mock_cerebro, mock_judge, mock_whatsapp,
     mock_catalog, mock_buffer) = _build_impl_mocks(
        "La Raider 125 es excelente. Ficha Tecnica: 125cc"
    )

    call_order = []
    mock_ms.create_prospect_if_missing = AsyncMock(
        side_effect=lambda *a, **k: call_order.append("create_prospect_if_missing"))
    mock_ms.update_last_interaction = AsyncMock(
        side_effect=lambda *a, **k: call_order.append("update_last_interaction"))
    mock_ms.transition_to_in_progress = AsyncMock(
        side_effect=lambda *a, **k: call_order.append("transition_to_in_progress"))

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.routers.whatsapp.judge_service", mock_judge), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_whatsapp), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.message_buffer", mock_buffer), \
         patch("app.routers.whatsapp._process_and_send_egress_message", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.db", MagicMock()):

        msg_payload = {
            "from": "573192564288",
            "id": "wamid.ch3_sequence",
            "type": "text",
            "phone_number_id": "999999",
            "text": "Quiero una Raider 125"
        }
        await _handle_message_background_impl(msg_payload, BackgroundTasks())

        i_create = call_order.index("create_prospect_if_missing")
        i_update = call_order.index("update_last_interaction")
        i_transition = call_order.index("transition_to_in_progress")
        assert i_create < i_update < i_transition, (
            f"❌ Orden transicional roto: {call_order}"
        )
        # Pin del HOTFIX v9.8.3: lectura inicial + re-fetch post-transición.
        assert mock_ms.get_prospect_data.await_count >= 2


@pytest.mark.asyncio
async def test_ch4_ponytail_deprioritized_after_human_help_on_handoff():
    """
    [INVARIANTE BOT-PONYTAIL-200] Ante respuesta HANDOFF_TRIGGERED aprobada por
    el Juez, la persistencia sigue el orden: set_human_help_status(True) →
    update_prospect_summary(phone, "", {"ponytail_status": "DEPRIORITIZED"})
    con payload exacto. Protegido por la skill ponytail (lógica de negocio).
    """
    from app.routers.whatsapp import _handle_message_background_impl

    (mock_ms, mock_cerebro, mock_judge, mock_whatsapp,
     mock_catalog, mock_buffer) = _build_impl_mocks("HANDOFF_TRIGGERED: asesor humano")

    mock_notification = MagicMock()
    mock_notification.notify_human_handoff = AsyncMock()

    call_order = []
    mock_ms.set_human_help_status = AsyncMock(
        side_effect=lambda *a, **k: call_order.append("set_human_help_status"))
    mock_ms.update_prospect_summary = AsyncMock(
        side_effect=lambda *a, **k: call_order.append("update_prospect_summary"))

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.routers.whatsapp.judge_service", mock_judge), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_whatsapp), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.message_buffer", mock_buffer), \
         patch("app.services.notification_service.notification_service", mock_notification), \
         patch("app.routers.whatsapp.db", MagicMock()):

        msg_payload = {
            "from": "573192564288",
            "id": "wamid.ch4_handoff",
            "type": "text",
            "phone_number_id": "999999",
            "text": "Quiero hablar con un asesor"
        }
        await _handle_message_background_impl(msg_payload, BackgroundTasks())

        assert call_order == ["set_human_help_status", "update_prospect_summary"], (
            f"❌ Orden ponytail/handoff roto: {call_order}"
        )
        mock_ms.set_human_help_status.assert_called_once_with(PHONE_E164, True)
        mock_ms.update_prospect_summary.assert_called_once_with(
            PHONE_E164, "", {"ponytail_status": "DEPRIORITIZED"}
        )


@pytest.mark.asyncio
async def test_ch5_unified_egress_single_persistence_and_send():
    """
    [BOT-BUGFIX-UNIFIED-EGRESS-PIPELINE-125] En el flujo texto aprobado:
    exactamente 1 save_message("user"), exactamente 1 save_message("model")
    con el response_text final, y exactamente 1 invocación de egreso unificado.
    Red contra la persistencia duplicada al fragmentar pipelines (RF-5).
    """
    from app.routers.whatsapp import _handle_message_background_impl

    final_text = "La Raider 125 es excelente. Ficha Tecnica: 125cc"
    (mock_ms, mock_cerebro, mock_judge, mock_whatsapp,
     mock_catalog, mock_buffer) = _build_impl_mocks(final_text)

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.routers.whatsapp.judge_service", mock_judge), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_whatsapp), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.message_buffer", mock_buffer), \
         patch("app.routers.whatsapp._process_and_send_egress_message", new_callable=AsyncMock) as mock_egress, \
         patch("app.routers.whatsapp.db", MagicMock()):

        msg_payload = {
            "from": "573192564288",
            "id": "wamid.ch5_egress",
            "type": "text",
            "phone_number_id": "999999",
            "text": "Quiero una Raider 125"
        }
        await _handle_message_background_impl(msg_payload, BackgroundTasks())

        save_calls = mock_ms.save_message.call_args_list
        user_saves = [c for c in save_calls if c.args[1] == "user"]
        model_saves = [c for c in save_calls if c.args[1] == "model"]

        assert len(user_saves) == 1, f"❌ Persistencia 'user' duplicada/ausente: {save_calls}"
        assert user_saves[0].args == (PHONE_E164, "user", "Quiero una Raider 125")
        assert len(model_saves) == 1, f"❌ Persistencia 'model' duplicada/ausente: {save_calls}"
        assert model_saves[0].args == (PHONE_E164, "model", final_text)

        mock_egress.assert_called_once_with(
            PHONE_E164, final_text, phone_number_id="999999"
        )
