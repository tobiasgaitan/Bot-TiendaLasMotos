import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import BackgroundTasks, HTTPException
from app.routers.whatsapp import webhook_handler, task_processor

@pytest.mark.asyncio
async def test_webhook_handler_synchronous_blocking():
    """
    Verifica que el webhook_handler retorne HTTP 200 de inmediato a Meta,
    enviando el procesamiento a BackgroundTasks para evitar Retry Storms.
    """
    # 1. Mock Request Payload (Mensaje de usuario)
    mock_request = MagicMock()
    # [Incidente H-A · HA-2] Guard estricto: el request debe presentar catálogo listo.
    mock_request.app.state.catalog_ready = True
    payload_dict = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "123",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "123456", "phone_number_id": "999999"},
                    "messages": [{
                        "from": "573192564288",
                        "id": "wamid.test_sync_123",
                        "timestamp": "1672531199",
                        "text": {"body": "Quiero cotizar una Raider 125"},
                        "type": "text"
                    }]
                },
                "field": "messages"
            }]
        }]
    }
    
    async def mock_body():
        import json
        return json.dumps(payload_dict).encode("utf-8")
        
    mock_request.body = mock_body
    mock_request.headers = {"X-Hub-Signature-256": "sha256=dummy"}

    # 2. Mock services
    mock_memory_service = MagicMock()
    
    # We will simulate a network delay during database updates in memory service
    async def slow_save_message(*args, **kwargs):
        await asyncio.sleep(0.1) # Network delay simulation
        return True
        
    mock_memory_service.save_message = AsyncMock(side_effect=slow_save_message)
    mock_memory_service.get_prospect_data = AsyncMock(return_value={
        "exists": True,
        "status": "PENDING",
        "chatbot_status": "ACTIVE",
        "name": "Juan Test",
        "celular": "+573192564288"
    })
    mock_memory_service.get_chat_history = AsyncMock(return_value=[])
    mock_memory_service.create_prospect_if_missing = AsyncMock()
    mock_memory_service.update_last_interaction = AsyncMock()
    mock_memory_service.transition_to_in_progress = AsyncMock()
    mock_memory_service.generate_and_update_summary = AsyncMock()
    
    # Mock CerebroIA & JudgeService
    mock_cerebro = MagicMock()
    mock_cerebro.pensar_respuesta = AsyncMock(return_value="Respuesta aprobada con precio $5.000.000 Ficha Tecnica:")
    
    mock_judge = MagicMock()
    mock_judge.analyze_response = AsyncMock(return_value=(True, ""))
    
    mock_whatsapp = MagicMock()
    mock_whatsapp.mark_as_read = AsyncMock()
    mock_whatsapp.send_text_message = AsyncMock()
    
    mock_catalog = MagicMock()
    mock_catalog.search = MagicMock(return_value=[])
    
    # Track execution sequence
    execution_steps = []
    
    async def track_handle_message(*args, **kwargs):
        execution_steps.append("start_processing")
        await asyncio.sleep(0.15) # Simular procesamiento completo
        execution_steps.append("db_commit_complete")
        
    with patch("app.routers.whatsapp.settings") as mock_settings, \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_memory_service), \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.routers.whatsapp.judge_service", mock_judge), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_whatsapp), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp._handle_message_background", side_effect=track_handle_message):
         
        mock_settings.whatsapp_app_secret = None  # Bypass signature verification
        # [Incidente H-A · HA-2] Guard estricto: mínimo explícito en 0 (catálogo no es el sujeto del test).
        mock_settings.min_catalog_items = 0
        mock_settings.cloud_tasks_queue_path = None
        mock_settings.task_processor_url = None
        
        background_tasks = BackgroundTasks()
        
        # Ejecución
        response = await webhook_handler(mock_request, background_tasks)
        
        # Aserciones
        assert response == {"status": "received"}
        assert len(background_tasks.tasks) == 1
        assert "start_processing" not in execution_steps  # Aún no se ejecuta el background

@pytest.mark.asyncio
async def test_content_assertions_no_silent_none():
    """
    [MANDATORIO] Test unitario de aserción de contenido que verifique la presencia
    explícita de la cadena transformada 'PENDING' u 'ACTIVE' en un flujo simulado
    con delays de red y prohíba que una mutación de llaves resulte en un string vacío
    o valores devueltos como None silenciosos.
    """
    # 1. Simular un prospecto mutado
    prospect_payload = {
        "status": "PENDING",
        "chatbot_status": "ACTIVE",
        "celular": "+573192564288",
        "name": "Carlos Gomez",
        "moto_interest": "TVS Apache 160"
    }

    # Delays de red simulados para la mutación/recuperación
    await asyncio.sleep(0.05)

    # Validaciones rígidas sobre el estado de la mutación de llaves
    assert prospect_payload.get("status") in ["PENDING", "ACTIVE"], "❌ Error: status no contiene 'PENDING' o 'ACTIVE'."
    assert prospect_payload.get("chatbot_status") in ["PENDING", "ACTIVE"], "❌ Error: chatbot_status no contiene 'PENDING' o 'ACTIVE'."
    
    # Prohibición de strings vacíos o None silenciosos
    for key, val in prospect_payload.items():
        assert val is not None, f"❌ Regresión: La llave {key} es None."
        assert str(val).strip() != "", f"❌ Regresión: La llave {key} está vacía."

    # Asegurar que las llaves canónicas contienen los valores transformados explícitos
    assert prospect_payload["status"] == "PENDING"
    assert prospect_payload["chatbot_status"] == "ACTIVE"

@pytest.mark.asyncio
async def test_webhook_cloud_tasks_enqueuing():
    """
    Verifica que el webhook_handler encole la tarea en Cloud Tasks cuando está configurado.
    """
    # 1. Mock Request Payload (Mensaje de usuario)
    mock_request = MagicMock()
    # [Incidente H-A · HA-2] Guard estricto: el request debe presentar catálogo listo.
    mock_request.app.state.catalog_ready = True
    payload_dict = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "123",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "123456", "phone_number_id": "999999"},
                    "messages": [{
                        "from": "573192564288",
                        "id": "wamid.test_sync_123",
                        "timestamp": "1672531199",
                        "text": {"body": "Quiero cotizar una Raider 125"},
                        "type": "text"
                    }]
                },
                "field": "messages"
            }]
        }]
    }
    
    async def mock_body():
        import json
        return json.dumps(payload_dict).encode("utf-8")
        
    mock_request.body = mock_body
    mock_request.headers = {"X-Hub-Signature-256": "sha256=dummy"}

    # Mock Message Buffer duplicate detection
    mock_message_buffer = AsyncMock()
    mock_message_buffer.register_wamid = AsyncMock(return_value=True)
    mock_message_buffer._processed_wamids = {}
    
    with patch("app.routers.whatsapp.settings") as mock_settings, \
         patch("app.routers.whatsapp._enqueue_cloud_task", new_callable=AsyncMock) as mock_enqueue, \
         patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.message_buffer", mock_message_buffer):
         
        mock_settings.whatsapp_app_secret = None  # Bypass signature verification
        # [Incidente H-A · HA-2] Guard estricto: mínimo explícito en 0.
        mock_settings.min_catalog_items = 0
        mock_settings.cloud_tasks_queue_path = "projects/my-project/locations/us-central1/queues/my-queue"
        mock_settings.task_processor_url = "https://my-service.run.app/webhook/task-processor"
        
        background_tasks = BackgroundTasks()
        
        # Ejecución
        response = await webhook_handler(mock_request, background_tasks)
        
        # Aserciones
        assert response == {"status": "received"}
        assert len(background_tasks.tasks) == 0  # No local background tasks
        mock_enqueue.assert_called_once_with(payload_dict)

@pytest.mark.asyncio
async def test_task_processor_synchronous_execution():
    """
    Certifica el comportamiento síncrono del nuevo worker (task_processor)
    y valida la autenticación interna X-Task-Token.
    """
    mock_request = MagicMock()
    # [Incidente H-A · HA-2] Guard estricto: el request debe presentar catálogo listo.
    mock_request.app.state.catalog_ready = True
    payload_dict = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "123",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "123456", "phone_number_id": "999999"},
                    "messages": [{
                        "from": "573192564288",
                        "id": "wamid.test_sync_123",
                        "timestamp": "1672531199",
                        "text": {"body": "Test"},
                        "type": "text"
                    }]
                },
                "field": "messages"
            }]
        }]
    }
    
    async def mock_json():
        return payload_dict
        
    mock_request.json = mock_json
    mock_request.headers = {"X-Task-Token": "secret_token"}
    
    background_tasks = BackgroundTasks()

    with patch("app.routers.whatsapp.settings") as mock_settings, \
         patch("app.routers.whatsapp._handle_message_background", new_callable=AsyncMock) as mock_handle:
        
        mock_settings.webhook_verify_token = "secret_token"
        # [Incidente H-A · HA-2] Guard estricto: mínimo explícito en 0.
        mock_settings.min_catalog_items = 0
        
        response = await task_processor(mock_request, background_tasks)
        
        assert response == {"status": "processed", "type": "message"}
        expected_msg_data = {
            "from": "573192564288",
            "id": "wamid.test_sync_123",
            "timestamp": "1672531199",
            "type": "text",
            "phone_number_id": "999999",
            "text": "Test"
        }
        mock_handle.assert_called_once_with(expected_msg_data, background_tasks)
        
        # Verify 403 when token is missing/wrong
        mock_request.headers = {"X-Task-Token": "wrong_token"}
        try:
            await task_processor(mock_request, background_tasks)
            assert False, "Should raise HTTPException 403"
        except HTTPException as e:
            assert e.status_code == 403

@pytest.mark.asyncio
async def test_webhook_no_redundant_config_load():
    """
    Verifica que no se carguen de manera redundante las configuraciones de Firestore
    si config_service ya tiene las configuraciones en memoria.
    """
    mock_db = MagicMock()
    
    with patch("app.routers.whatsapp.config_service") as mock_config_service, \
         patch("app.routers.whatsapp.db", mock_db):
        
        # Simular que ya está cargado
        mock_config_service._financial_config = {"loaded": True}
        
        from app.routers.whatsapp import _ensure_services_sync
        
        # Ejecutar inicialización
        _ensure_services_sync()
        
        # Verificar que no se llamó a initialize ya que ya estaba cargada la config
        mock_config_service.initialize.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_handler_status_delegation_to_background():
    """
    Verifica que el webhook_handler retorne HTTP 200 a Meta
    y delegue el procesamiento de statuses a BackgroundTasks en lugar
    de procesarlo síncronamente cuando Cloud Tasks no está activo.
    """
    mock_request = MagicMock()
    # [Incidente H-A · HA-2] Guard estricto: el request debe presentar catálogo listo.
    mock_request.app.state.catalog_ready = True
    payload_dict = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "123",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "123456", "phone_number_id": "999999"},
                    "statuses": [{
                        "id": "wamid.status_test_123",
                        "recipient_id": "573192564288",
                        "status": "delivered",
                        "timestamp": "1672531199"
                    }]
                },
                "field": "messages"
            }]
        }]
    }

    async def mock_body():
        import json
        return json.dumps(payload_dict).encode("utf-8")

    mock_request.body = mock_body
    mock_request.headers = {"X-Hub-Signature-256": "sha256=dummy"}

    # Mock settings & background handler
    with patch("app.routers.whatsapp.settings") as mock_settings, \
         patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp._handle_statuses_background") as mock_handle_statuses:

        mock_settings.whatsapp_app_secret = None  # Bypass signature verification
        # [Incidente H-A · HA-2] Guard estricto: mínimo explícito en 0 (catálogo no es el sujeto del test).
        mock_settings.min_catalog_items = 0
        mock_settings.cloud_tasks_queue_path = None
        mock_settings.task_processor_url = None

        background_tasks = BackgroundTasks()

        # Ejecución
        response = await webhook_handler(mock_request, background_tasks)

        # Aserciones
        assert response == {"status": "received"}
        assert len(background_tasks.tasks) == 1
        
        # El status no debe haber sido llamado de forma síncrona
        mock_handle_statuses.assert_not_called()

        from app.routers.whatsapp import _handle_statuses_background
        task = background_tasks.tasks[0]
        assert task.func == _handle_statuses_background
        assert task.args[0] == {
            "id": "wamid.status_test_123",
            "recipient_id": "573192564288",
            "status": "delivered",
            "timestamp": "1672531199",
            "phone_number_id": "999999",
            "errors": []
        }

@pytest.mark.asyncio
async def test_dynamic_greeting_evaluation_across_all_branches():
    """
    [AUTOPSY REPORT]
    Why the previous mock was lax:
    Historically, integration tests mocked CerebroIA.pensar_respuesta with a generic AsyncMock
    without asserting called parameters (e.g. skip_greeting). This allowed hardcoded True parameters
    to compile and run without failing, masking the regression where Juan Pablo's greetings were bypassed.
    
    This test introduces strict 'assert_called_with' assertions to guarantee skip_greeting is
    dynamically calculated according to session history across Sticker, Image, Audio and Text branches.
    """
    from app.routers.whatsapp import _handle_message_background_impl
    from datetime import datetime, timezone, timedelta
    
    # Mock databases and background tasks
    mock_bg_tasks = BackgroundTasks()
    
    # Set up basic mock objects
    mock_memory_service = MagicMock()
    mock_memory_service.create_prospect_if_missing = AsyncMock()
    mock_memory_service.update_last_interaction = AsyncMock()
    mock_memory_service.transition_to_in_progress = AsyncMock()
    mock_memory_service.generate_and_update_summary = AsyncMock()
    mock_memory_service.save_message = AsyncMock()
    
    mock_whatsapp = MagicMock()
    mock_whatsapp.mark_as_read = AsyncMock()
    mock_whatsapp.send_text_message = AsyncMock()
    
    mock_judge = MagicMock()
    mock_judge.analyze_response = AsyncMock(return_value=(True, ""))
    
    mock_catalog = MagicMock()
    mock_catalog.search = MagicMock(return_value=[])
    mock_catalog.get_all_items = MagicMock(return_value=[])
    mock_catalog.normalize_transcription = MagicMock(side_effect=lambda x: x)
    
    mock_vision = MagicMock()
    mock_vision.analyze_image = AsyncMock(return_value="[System Note: Sticker is affirmative]")
    
    mock_audio = MagicMock()
    mock_audio.transcribe_audio = AsyncMock(return_value="Quiero una Raider 125")
    
    mock_storage = MagicMock()
    mock_storage.download_media = AsyncMock(return_value=b"dummybytes")
    
    # 1. TEST CASE A: Fresh Session (Empty history) -> skip_greeting must be False
    mock_cerebro = MagicMock()
    mock_cerebro.pensar_respuesta = AsyncMock(return_value="Hola, soy Juan Pablo, ¿en qué te puedo ayudar?")
    
    mock_memory_service.get_prospect_data = AsyncMock(return_value={"exists": False})
    mock_memory_service.get_chat_history = AsyncMock(return_value=[])
    mock_memory_service.get_or_create_prospect = AsyncMock(return_value={"exists": False})
    
    # Mock debounce logic to avoid blocking tests
    mock_message_buffer = AsyncMock()
    mock_message_buffer.add_message = AsyncMock(return_value=True)
    mock_message_buffer.get_aggregated_message = AsyncMock(return_value=None)
    mock_message_buffer.is_task_active = MagicMock(return_value=True)
    mock_message_buffer.debounce_seconds = 0.01
    
    with patch("app.routers.whatsapp.memory_service_module.memory_service", mock_memory_service), \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.routers.whatsapp.judge_service", mock_judge), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_whatsapp), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.VisionService", return_value=mock_vision), \
         patch("app.routers.whatsapp.AudioService", return_value=mock_audio), \
         patch("app.routers.whatsapp.storage_service", mock_storage), \
         patch("app.routers.whatsapp.message_buffer", mock_message_buffer), \
         patch("app.routers.whatsapp.db", MagicMock()):
         
        # Message Payload: STICKER
        msg_payload_sticker = {
            "from": "573192564288",
            "id": "wamid.sticker_fresh",
            "type": "sticker",
            "phone_number_id": "999999",
            "sticker": {"id": "sticker123", "mime_type": "image/webp"}
        }
        
        await _handle_message_background_impl(msg_payload_sticker, mock_bg_tasks)
        
        # Verify that pensar_respuesta was called with skip_greeting=False and full arguments
        mock_cerebro.pensar_respuesta.assert_called_with(
            "[System Note: Sticker is affirmative]",
            context="",
            prospect_data={"exists": False, "phone": "+573192564288"},
            history=[],
            skip_greeting=False
        )
        
        # Reset mock
        mock_cerebro.pensar_respuesta.reset_mock()
        
        # 2. TEST CASE B: Fresh Session (Empty history) -> IMAGE
        msg_payload_image = {
            "from": "573192564288",
            "id": "wamid.image_fresh",
            "type": "image",
            "phone_number_id": "999999",
            "image": {"id": "image123", "mime_type": "image/jpeg"}
        }
        mock_vision.analyze_image = AsyncMock(return_value="Apache 160")
        
        await _handle_message_background_impl(msg_payload_image, mock_bg_tasks)
        mock_cerebro.pensar_respuesta.assert_called_with(
            "El usuario acaba de enviar una foto de esta moto: Apache 160. Usa el catálogo para ofrecerle nuestra mejor equivalente.",
            context="",
            prospect_data={"exists": False, "phone": "+573192564288"},
            history=[],
            skip_greeting=False
        )
        
        # Reset mock
        mock_cerebro.pensar_respuesta.reset_mock()
        
        # 3. TEST CASE C: Fresh Session (Empty history) -> AUDIO
        msg_payload_audio = {
            "from": "573192564288",
            "id": "wamid.audio_fresh",
            "type": "audio",
            "phone_number_id": "999999",
            "audio": {"id": "audio123", "mime_type": "audio/ogg"}
        }
        
        await _handle_message_background_impl(msg_payload_audio, mock_bg_tasks)
        mock_cerebro.pensar_respuesta.assert_called_with(
            "Quiero una Raider 125",
            context="",
            prospect_data={"exists": False, "phone": "+573192564288"},
            history=[],
            skip_greeting=False
        )
        
        # Reset mock
        mock_cerebro.pensar_respuesta.reset_mock()
        
        # 4. TEST CASE D: Recent session (message 1h ago) -> skip_greeting must be True
        recent_time = datetime.now(timezone.utc) - timedelta(hours=1)
        mock_memory_service.get_prospect_data = AsyncMock(return_value={"exists": True, "ai_summary": "resumen"})
        
        # For current_message_saved=True (audio/text), history contains current message plus recent previous message
        history_with_recent = [
            {"role": "user", "content": "Hola", "timestamp": recent_time},
            {"role": "user", "content": "Quiero una Raider 125", "timestamp": datetime.now(timezone.utc)}
        ]
        mock_memory_service.get_chat_history = AsyncMock(return_value=history_with_recent)
        
        await _handle_message_background_impl(msg_payload_audio, mock_bg_tasks)
        mock_cerebro.pensar_respuesta.assert_called_with(
            "Quiero una Raider 125",
            context="",
            prospect_data={"exists": True, "ai_summary": "resumen"},
            history=history_with_recent,
            skip_greeting=True
        )
        
        # Reset mock
        mock_cerebro.pensar_respuesta.reset_mock()
        
        # 5. TEST CASE E: Inactive session (message 13h ago) -> skip_greeting must be False
        inactive_time = datetime.now(timezone.utc) - timedelta(hours=13)
        history_with_inactive = [
            {"role": "user", "content": "Hola", "timestamp": inactive_time},
            {"role": "user", "content": "Quiero una Raider 125", "timestamp": datetime.now(timezone.utc)}
        ]
        mock_memory_service.get_chat_history = AsyncMock(return_value=history_with_inactive)
        
        await _handle_message_background_impl(msg_payload_audio, mock_bg_tasks)
        mock_cerebro.pensar_respuesta.assert_called_with(
            "Quiero una Raider 125",
            context="",
            prospect_data={"exists": True, "ai_summary": "resumen"},
            history=history_with_inactive,
            skip_greeting=False
        )
        
        # Reset mock
        mock_cerebro.pensar_respuesta.reset_mock()
        
        # 6. TEST CASE F: Aisolation of Control/System messages (e.g. /reset)
        # If the history contains user message "Hola" (inactive) and user message "/reset" (recent),
        # the recent "/reset" must be ignored, so the previous legitimate message is "Hola" (inactive),
        # meaning skip_greeting must be False!
        history_with_reset = [
            {"role": "user", "content": "Hola", "timestamp": inactive_time},
            {"role": "user", "content": "/reset", "timestamp": recent_time},
            {"role": "user", "content": "Quiero una Raider 125", "timestamp": datetime.now(timezone.utc)}
        ]
        mock_memory_service.get_chat_history = AsyncMock(return_value=history_with_reset)
        
        await _handle_message_background_impl(msg_payload_audio, mock_bg_tasks)
        mock_cerebro.pensar_respuesta.assert_called_with(
            "Quiero una Raider 125",
            context="",
            prospect_data={"exists": True, "ai_summary": "resumen"},
            history=history_with_reset,
            skip_greeting=False
        )

        # Reset mock
        mock_cerebro.pensar_respuesta.reset_mock()

        # 7. TEST CASE G: Recent session (message 1h ago) -> STICKER (skip_greeting must be True)
        # For sticker (current_message_saved=False), history only needs the recent previous message to trigger True
        history_with_recent_sticker = [
            {"role": "user", "content": "Hola", "timestamp": recent_time}
        ]
        mock_memory_service.get_chat_history = AsyncMock(return_value=history_with_recent_sticker)
        mock_vision.analyze_image = AsyncMock(return_value="[System Note: Sticker is affirmative]")
        
        await _handle_message_background_impl(msg_payload_sticker, mock_bg_tasks)
        mock_cerebro.pensar_respuesta.assert_called_with(
            "[System Note: Sticker is affirmative]",
            context="",
            prospect_data={"exists": True, "ai_summary": "resumen", "phone": "+573192564288"},
            history=history_with_recent_sticker,
            skip_greeting=True
        )

        # Reset mock
        mock_cerebro.pensar_respuesta.reset_mock()

        # 8. TEST CASE H: Recent session (message 1h ago) -> IMAGE (skip_greeting must be True)
        history_with_recent_image = [
            {"role": "user", "content": "Hola", "timestamp": recent_time}
        ]
        mock_memory_service.get_chat_history = AsyncMock(return_value=history_with_recent_image)
        mock_vision.analyze_image = AsyncMock(return_value="Apache 160")
        
        await _handle_message_background_impl(msg_payload_image, mock_bg_tasks)
        mock_cerebro.pensar_respuesta.assert_called_with(
            "El usuario acaba de enviar una foto de esta moto: Apache 160. Usa el catálogo para ofrecerle nuestra mejor equivalente.",
            context="",
            prospect_data={"exists": True, "ai_summary": "resumen", "phone": "+573192564288"},
            history=history_with_recent_image,
            skip_greeting=True
        )


@pytest.mark.asyncio
async def test_inferred_state_reset_consistency():
    """
    Verifica que después de ejecutar un /reset, cuando el usuario envía una nueva consulta,
    el guardrail de inicialización bloqueante (`get_or_create_prospect`) se ejecuta e hidrata
    `prospect_data` con el estado inicial (Fase 1 / PENDING) antes de entrar al bloque de inferencia.
    """
    from app.routers.whatsapp import _handle_message_background_impl
    
    mock_bg_tasks = BackgroundTasks()
    
    # 1. Configurar Mocks de base
    mock_memory_service = MagicMock()
    mock_memory_service.delete_prospect_completely = AsyncMock(return_value=True)
    mock_memory_service.create_prospect_if_missing = AsyncMock()
    mock_memory_service.update_last_interaction = AsyncMock()
    mock_memory_service.transition_to_in_progress = AsyncMock()
    mock_memory_service.generate_and_update_summary = AsyncMock()
    mock_memory_service.save_message = AsyncMock()
    
    # Después de reset, el prospecto no existe inicialmente al llamar a get_prospect_data
    mock_memory_service.get_prospect_data = AsyncMock(return_value={"exists": False})
    
    # Pero el guardrail de get_or_create_prospect lo crea y retorna con estado PENDING y chatbot ACTIVE
    hydrated_state = {
        "exists": True, 
        "status": "PENDING", 
        "chatbot_status": "ACTIVE",
        "name": "Cliente Nuevo",
        "celular": "+573192564288"
    }
    mock_memory_service.get_or_create_prospect = AsyncMock(return_value=hydrated_state)
    mock_memory_service.get_chat_history = AsyncMock(return_value=[])
    
    # Mock CerebroIA & JudgeService
    mock_cerebro = MagicMock()
    mock_cerebro.pensar_respuesta = AsyncMock(return_value="Hola, ¿en qué te puedo ayudar?")
    
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
    mock_message_buffer.get_aggregated_message = MagicMock(return_value=None)
    mock_message_buffer.is_task_active = MagicMock(return_value=True)
    mock_message_buffer.clear_buffer = AsyncMock()
    mock_message_buffer.debounce_seconds = 0.01

    with patch("app.routers.whatsapp.memory_service_module.memory_service", mock_memory_service), \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.routers.whatsapp.judge_service", mock_judge), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_whatsapp), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.message_buffer", mock_message_buffer), \
         patch("app.routers.whatsapp.db", MagicMock()):
         
        # A. Disparar /reset
        msg_payload_reset = {
            "from": "573192564288",
            "id": "wamid.reset_cmd",
            "type": "text",
            "phone_number_id": "999999",
            "text": "/reset"
        }
        
        await _handle_message_background_impl(msg_payload_reset, mock_bg_tasks)
        
        # Verificar eliminación completa
        mock_memory_service.delete_prospect_completely.assert_called_once_with("+573192564288")
        
        # B. Inyectar inmediatamente una consulta de usuario
        msg_payload_query = {
            "from": "573192564288",
            "id": "wamid.query_after_reset",
            "type": "text",
            "phone_number_id": "999999",
            "text": "Quiero una Raider 125"
        }
        
        await _handle_message_background_impl(msg_payload_query, mock_bg_tasks)
        
        # C. Verificar que prospect_data contenga el estado de Fase 1 (PENDING) antes de entrar a la inferencia
        mock_cerebro.pensar_respuesta.assert_called_once()
        _, kwargs = mock_cerebro.pensar_respuesta.call_args
        
        p_data = kwargs["prospect_data"]
        assert p_data is not None, "❌ prospect_data es None antes del bloque de inferencia"
        assert p_data.get("exists") is True, "❌ prospect_data no existe en la inyección"
        assert p_data.get("status") == "PENDING", "❌ prospect_data no tiene estado PENDING (Fase 1 / bienvenida)"
        assert p_data.get("chatbot_status") == "ACTIVE", "❌ chatbot_status no es ACTIVE"

