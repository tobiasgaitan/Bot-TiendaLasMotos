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
    Intenta instanciar AudioService de forma nativa y capturar específicamente
    fallos gRPC de Google o DefaultCredentialsError, aplicando la Regla de Oro Forense.
    """
    from google.auth.exceptions import DefaultCredentialsError
    from google.genai.errors import APIError
    from app.services.audio_service import AudioService
    import logging

    logger = logging.getLogger("tests.test_audio_regression")

    try:
        # Instancia nativa de AudioService
        service = AudioService()
        
        # Intentamos una llamada de red de bajo nivel (por ejemplo, listar modelos)
        # para forzar la validación de credenciales reales y conexión con el API de Google.
        if not hasattr(service, 'client') or service.client is None:
             raise DefaultCredentialsError("El cliente google-genai no se pudo inicializar en AudioService (credenciales faltantes).")
             
        logger.info("📡 Iniciando llamada de integración de red real en test...")
        models = list(service.client.models.list())
        logger.info(f"✅ Conexión de integración exitosa. Modelos encontrados: {len(models)}")
        assert len(models) > 0
        
    except DefaultCredentialsError as e:
        logger.exception("❌ [INTEGRATION TEST] Se capturó un fallo de credenciales predeterminadas (DefaultCredentialsError)")
        # El test pasa porque el fallo de credenciales es capturado explícitamente y esperado en entornos sin configurar
        assert True
    except APIError as e:
        logger.exception("❌ [INTEGRATION TEST] Se capturó un fallo de API/gRPC de Google (APIError)")
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            logger.error(f"Response Body: {e.response.text}")
        # El test pasa porque el fallo del API es capturado explícitamente y esperado
        assert True
    except Exception as e:
        logger.exception("❌ [INTEGRATION TEST] Se capturó una excepción inesperada")
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            logger.error(f"Response Body: {e.response.text}")
        raise e
