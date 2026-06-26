import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import BackgroundTasks
from app.routers.whatsapp import _handle_message_background

@pytest.mark.asyncio
async def test_handle_message_background_zombie_recovery():
    """
    [BOT-INTEGRATION-110] Test de integración real.
    Verifica que si entra un mensaje de texto plano y el prospecto en Firestore 
    es un 'zombi' (metadata_only generado por un acuse concurrente), el enrutador
    active el recovery, inicialice el CRM y complete la inferencia de CerebroIA
    en lugar de abortar con el mensaje de intermitencia del sistema.
    """
    # 1. Configurar Payload de Meta del mensaje entrante
    msg_data = {
        "from": "573192564288",
        "id": "wamid.text_test_123",
        "type": "text",
        "text": "me interesa la VICTORY MRX 125, ¿qué precio tiene?",
        "phone_number_id": "1021779847693778"
    }
    background_tasks = BackgroundTasks()

    # 2. Mockear el prospecto zombi (Existe en DB pero no tiene ai_summary)
    mock_prospect_data = {
        "exists": True,
        "celular": "+573192564288",
        "chatbot_status": "ACTIVE",
        "status": "PENDING",
        "source": "whatsapp_bot"
        # Omitimos deliberadamente 'ai_summary' para simular el zombi
    }

    mock_ms = AsyncMock()
    mock_ms.get_prospect_data = AsyncMock(return_value=mock_prospect_data)
    mock_ms.create_prospect_if_missing = AsyncMock()
    mock_ms.get_chat_history = AsyncMock(return_value=[])
    mock_ms.save_message = AsyncMock()
    mock_ms.generate_and_update_summary = AsyncMock()
    mock_ms.update_last_interaction = AsyncMock()
    mock_ms.transition_to_in_progress = AsyncMock()

    # Mockear CerebroIA para verificar que la llamada al LLM SÍ se intente
    mock_cerebro = AsyncMock()
    mock_cerebro.pensar_respuesta = AsyncMock(return_value="La Victory MRX 125 cuesta $8.500.000.")

    # Mocks para evitar la inicialización real de Firestore en el enrutador
    mock_db = MagicMock()
    mock_db.project = "tiendalasmotos"
    
    mock_message_buffer = AsyncMock()
    mock_message_buffer.add_message = AsyncMock(return_value=True)
    
    mock_config_loader = MagicMock()
    mock_catalog = MagicMock()
    mock_catalog.search = MagicMock(return_value=[])
    
    mock_config_service = MagicMock()
    
    mock_judge = AsyncMock()
    mock_judge.analyze_response = AsyncMock(return_value=(True, ""))

    mock_wa_service = AsyncMock()
    mock_wa_service.mark_as_read = AsyncMock(return_value=True)
    mock_wa_service.send_text_message = AsyncMock()
    mock_wa_service.send_image_message = AsyncMock()

    # 3. Patching de módulos con control estricto de namespaces
    with patch("app.routers.whatsapp.db", mock_db), \
         patch("app.routers.whatsapp.message_buffer", mock_message_buffer), \
         patch("app.routers.whatsapp.config_loader", mock_config_loader), \
         patch("app.routers.whatsapp.catalog_service_local", mock_catalog), \
         patch("app.routers.whatsapp.config_service", mock_config_service), \
         patch("app.routers.whatsapp.judge_service", mock_judge), \
         patch("app.routers.whatsapp.memory_service_module") as mock_mem_module, \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.routers.whatsapp._send_whatsapp_message") as mock_send_wa, \
         patch("app.services.whatsapp_service.whatsapp_service", mock_wa_service):
         
        mock_mem_module.memory_service = mock_ms
        mock_send_wa.return_value = True

        # Ejecución del handler crítico de producción
        await _handle_message_background(msg_data, background_tasks)

        # ASERCIONES DE CONTROL DE CALIDAD
        # A) Debió detectar el zombi y llamar a la inicialización forzada del CRM
        mock_ms.create_prospect_if_missing.assert_called_with("+573192564288")
        
        # B) Debió llamar a re-cargar los datos tras la inicialización
        assert mock_ms.get_prospect_data.call_count >= 2

        # C) ¡MANDATORIO! La inferencia del LLM NO debió abortar
        mock_cerebro.pensar_respuesta.assert_called_once()
        
        # D) No debió enviar el mensaje de error de intermitencias del sistema
        sent_payload = mock_send_wa.call_args[0][1]
        assert "intermitencias" not in sent_payload, "❌ Error: El bot envió el fallback de error al cliente."
        assert "Victory" in sent_payload, "✅ Éxito: El bot procesó la respuesta comercial real."

    print("🏁 [TEST PASSED] Flujo de recuperación de documento zombi validado correctamente.")
