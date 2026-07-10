import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import BackgroundTasks
from app.routers.whatsapp import webhook_handler, _handle_message_background_impl

@pytest.mark.asyncio
async def test_audio_regression_last_bot_question_injection():
    """
    Test para validar que en el procesamiento de audios, el pipeline:
    1. Responda 200 OK (síncronamente del webhook_handler).
    2. Extraiga correctamente la última pregunta del bot (last_bot_question) desde la historia del chat.
    3. Inyecte esta pregunta en generate_and_update_summary en lugar de una cadena vacía.
    """
    # 1. Payload de webhook de WhatsApp con tipo 'audio'
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
                        "id": "wamid.test_audio_regression_123",
                        "timestamp": "1672531199",
                        "audio": {
                            "id": "audio_media_id_123",
                            "mime_type": "audio/ogg; codecs=opus"
                        },
                        "type": "audio"
                    }]
                },
                "field": "messages"
            }]
        }]
    }

    mock_request = MagicMock()
    async def mock_body():
        import json
        return json.dumps(payload_dict).encode("utf-8")
    mock_request.body = mock_body
    mock_request.headers = {"X-Hub-Signature-256": "sha256=dummy"}

    # Mock del MemoryService
    mock_memory_service = MagicMock()
    mock_memory_service.create_prospect_if_missing = AsyncMock()
    mock_memory_service.update_last_interaction = AsyncMock()
    mock_memory_service.save_message = AsyncMock()
    mock_memory_service.transition_to_in_progress = AsyncMock()
    mock_memory_service.delete_prospect_completely = AsyncMock()
    mock_memory_service.get_prospect_data = AsyncMock(return_value={
        "exists": True,
        "status": "PENDING",
        "chatbot_status": "ACTIVE",
        "name": "Juan Test",
        "celular": "+573192564288"
    })
    
    # Historia de chat simulada: la última pregunta del bot fue "¿Qué tipo de moto buscas?"
    mock_history = [
        {"role": "user", "content": "hola"},
        {"role": "model", "content": "¿Qué tipo de moto buscas?"}
    ]
    mock_memory_service.get_chat_history = AsyncMock(return_value=mock_history)
    mock_memory_service.generate_and_update_summary = AsyncMock()

    # Mocks de servicios requeridos
    mock_storage = MagicMock()
    mock_storage.download_media = AsyncMock(return_value=b"mock_audio_bytes")

    mock_audio = MagicMock()
    mock_audio.transcribe_audio = AsyncMock(return_value="Quiero comprar una Victory")

    mock_cerebro = MagicMock()
    mock_cerebro.pensar_respuesta = AsyncMock(return_value="Perfecto. La Victory está disponible por $6.000.000. Ficha Tecnica: http://... ![](http://victory.png)")

    mock_whatsapp = MagicMock()
    mock_whatsapp.mark_as_read = AsyncMock()
    mock_whatsapp.send_text_message = AsyncMock()
    mock_whatsapp.send_image_message = AsyncMock()

    mock_catalog = MagicMock()
    mock_catalog.search = MagicMock(return_value=[])
    mock_catalog.get_all_items = MagicMock(return_value=[{"name": "Victory"}] * 100)

    mock_judge = MagicMock()
    mock_judge.analyze_response = AsyncMock(return_value=(True, ""))

    # Parchear todas las dependencias
    with patch("app.routers.whatsapp.settings") as mock_settings, \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_memory_service), \
         patch("app.routers.whatsapp.storage_service", mock_storage), \
         patch("app.routers.whatsapp.AudioService", return_value=mock_audio), \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_whatsapp), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.judge_service", mock_judge):

        mock_settings.whatsapp_app_secret = None  # Bypass firma
        mock_settings.cloud_tasks_queue_path = None
        mock_settings.task_processor_url = None
        mock_settings.min_catalog_items = 0

        # 1. Ejecutar webhook_handler y verificar respuesta síncrona
        background_tasks = BackgroundTasks()
        response = await webhook_handler(mock_request, background_tasks)
        assert response == {"status": "received"}

        # 2. Ejecutar la lógica de fondo de forma directa para inspeccionar el flujo
        msg_data = {
            "from": "573192564288",
            "id": "wamid.test_audio_regression_123",
            "timestamp": "1672531199",
            "type": "audio",
            "media_id": "audio_media_id_123",
            "mime_type": "audio/ogg; codecs=opus"
        }
        
        # Desactivamos el buffer de mensajes para evitar falsos positivos
        with patch("app.routers.whatsapp.message_buffer.add_message", AsyncMock(return_value=True)):
            await _handle_message_background_impl(msg_data, background_tasks)

        # 3. Validaciones
        # - El audio debe haber sido descargado
        mock_storage.download_media.assert_called_once_with("audio_media_id_123")
        # - La transcripción debe haber sido solicitada con los bytes descargados
        mock_audio.transcribe_audio.assert_called_once_with(b"mock_audio_bytes", "audio/ogg; codecs=opus")
        # - El mensaje transcrito debe haber sido guardado en Firestore
        mock_memory_service.save_message.assert_any_call(
            "+573192564288", "user", "Quiero comprar una Victory"
        )
        # - generate_and_update_summary debe ser llamado con la última pregunta del bot extraída del historial
        mock_memory_service.generate_and_update_summary.assert_called_once_with(
            "+573192564288",
            "User sent audio. Transcription: Quiero comprar una Victory",
            mock_cerebro,
            last_bot_question="¿Qué tipo de moto buscas?"
        )


@pytest.mark.asyncio
async def test_audio_service_live_integration():
    """
    Test de Integración Desacoplado (Live/Integration Test)
    Intenta instanciar AudioService de forma nativa en ambos canales de autenticación
    (API Key y Vertex AI) y valida aserciones rígidas sobre el model_id unificado,
    mientras simula las llamadas a la API de Google de forma segura.
    """
    from google.auth.exceptions import DefaultCredentialsError
    from google.genai.errors import APIError, ClientError
    from app.services.audio_service import AudioService
    from unittest.mock import patch, MagicMock
    import logging
    import os

    logger = logging.getLogger("tests.test_audio_regression")

    # 1. Canal 1: API Key
    logger.info("Testing AudioService initialization via API Key channel...")
    mock_client_instance = MagicMock()
    mock_client_instance.models.list.return_value = [MagicMock()]
    
    with patch.dict(os.environ, {"GEMINI_API_KEY": "fake_api_key", "GOOGLE_GENAI_USE_VERTEXAI": "false"}), \
         patch("app.services.audio_service.genai.Client", return_value=mock_client_instance) as mock_client_cls:
        
        service = AudioService()
        assert service._model_id == "gemini-2.5-flash", "model_id no coincide con la constante unificada en el canal de API Key"
        
        # Validar la llamada simulada
        models = list(service.client.models.list())
        assert len(models) > 0
        mock_client_cls.assert_called_once_with(api_key="fake_api_key")

    # 2. Canal 2: Vertex AI
    logger.info("Testing AudioService initialization via Vertex AI channel...")
    mock_client_instance_vertex = MagicMock()
    mock_client_instance_vertex.models.list.return_value = [MagicMock()]
    mock_creds = MagicMock()
    
    with patch.dict(os.environ, {"GOOGLE_GENAI_USE_VERTEXAI": "true", "GOOGLE_CLOUD_PROJECT": "test-project", "GOOGLE_CLOUD_LOCATION": "us-central1"}), \
         patch("google.auth.default", return_value=(mock_creds, "test-project")), \
         patch("app.services.audio_service.genai.Client", return_value=mock_client_instance_vertex) as mock_client_cls_vertex:
        
        service_vertex = AudioService()
        assert service_vertex._model_id == "gemini-2.5-flash", "model_id no coincide con la constante unificada en el canal de Vertex AI"
        
        # Validar la llamada simulada
        models = list(service_vertex.client.models.list())
        assert len(models) > 0
        mock_client_cls_vertex.assert_called_once_with(
            vertexai=True,
            project="test-project",
            location="us-central1",
            credentials=mock_creds
        )
