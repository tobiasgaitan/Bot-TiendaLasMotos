import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from tests.conftest_chaos import slow_async_mock, timed_assertion, mock_firestore_with_latency, mock_gemini_with_latency

@pytest.mark.asyncio
async def test_webhook_response_within_meta_window(timed_assertion, mock_firestore_with_latency, mock_gemini_with_latency):
    from app.routers.whatsapp import webhook_handler
    from fastapi import BackgroundTasks
    
    # WHY sin spec=Request [Incidente H-A · HA-2]: con spec, el mock hereda __len__
    # de la interfaz Mapping de HTTPConnection (retorna 0) → bool(request) es False
    # y el guard `if request and ...` hace short-circuit ignorando catalog_ready.
    request = MagicMock()
    request.headers = {}
    async def mock_body():
        return b'{"object":"whatsapp_business_account","entry":[{"id":"123","changes":[{"value":{"messaging_product":"whatsapp","metadata":{"display_phone_number":"123456","phone_number_id":"999999"},"messages":[{"from":"5730000000","id":"wamid.1","timestamp":"1672531199","text":{"body":"Test"},"type":"text"}]},"field":"messages"}]}]}'
    request.body = mock_body
    # [Incidente H-A · HA-2] Guard estricto: catálogo listo + mínimo explícito en 0.
    request.app.state.catalog_ready = True
    
    bg_tasks = BackgroundTasks()
    
    with patch("app.routers.whatsapp.settings") as mock_settings, \
         patch("app.routers.whatsapp.db", mock_firestore_with_latency(0.1)), \
         patch("app.routers.whatsapp.motor_financiero", MagicMock()), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", MagicMock()):
         
        mock_settings.whatsapp_app_secret = None
        mock_settings.min_catalog_items = 0
        mock_settings.cloud_tasks_queue_path = None
        mock_settings.task_processor_url = None
        
        async with timed_assertion(15.0):
            response = await webhook_handler(request, bg_tasks)
            assert response == {"status": "received"}

@pytest.mark.asyncio
async def test_typing_delay_cap(timed_assertion):
    from app.routers.whatsapp import _handle_message_background
    from fastapi import BackgroundTasks
    
    msg_data = {
        "from": "5730000000",
        "id": "wamid.1",
        "timestamp": "1672531199",
        "text": "Test",
        "type": "text"
    }
    
    mock_memory = MagicMock()
    mock_memory.get_chat_history = AsyncMock(return_value=[])
    mock_memory.get_prospect_data = AsyncMock(return_value={"exists": True})
    mock_memory.save_message = AsyncMock()
    
    mock_cerebro = MagicMock()
    # Mock to trigger a long typing delay (long response text)
    mock_cerebro.pensar_respuesta = AsyncMock(return_value="A" * 1000) 
    
    bg_tasks = BackgroundTasks()
    
    with patch("app.routers.whatsapp.memory_service_module.memory_service", mock_memory), \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.routers.whatsapp.judge_service.analyze_response", AsyncMock(return_value=(True, ""))), \
         patch("app.routers.whatsapp._send_whatsapp_message", AsyncMock(return_value=True)):
         
         # The typing_delay logic max is 1.5s
         async with timed_assertion(3.0):
             await _handle_message_background(msg_data, bg_tasks)
