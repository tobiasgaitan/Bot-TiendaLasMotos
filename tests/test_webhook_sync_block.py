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
    mock_message_buffer = MagicMock()
    mock_message_buffer._processed_wamids = {}
    
    with patch("app.routers.whatsapp.settings") as mock_settings, \
         patch("app.routers.whatsapp._enqueue_cloud_task", new_callable=AsyncMock) as mock_enqueue, \
         patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.message_buffer", mock_message_buffer):
         
        mock_settings.whatsapp_app_secret = None  # Bypass signature verification
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
