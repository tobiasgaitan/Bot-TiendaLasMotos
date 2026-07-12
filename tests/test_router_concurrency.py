import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import BackgroundTasks
from app.routers.whatsapp import webhook_handler
from app.services.message_buffer import MessageBuffer

@pytest.mark.asyncio
async def test_concurrent_webhook_idempotency():
    """
    Verifica que dos peticiones asíncronas simultáneas con el mismo WAMID
    sean filtradas de manera que solo la primera llega a la fase de inferencia/cola
    y la segunda sea rechazada/descartada en la frontera del router con:
    {"status": "ignored", "procesado": False}
    """
    # 1. Mock Request Payload (Mensaje de usuario)
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
                        "id": "wamid.concurrent_test_unique_123",
                        "timestamp": "1672531199",
                        "text": {"body": "Quiero comprar una Raider"},
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

    mock_request_1 = MagicMock()
    mock_request_1.body = mock_body
    mock_request_1.headers = {"X-Hub-Signature-256": "sha256=dummy"}

    mock_request_2 = MagicMock()
    mock_request_2.body = mock_body
    mock_request_2.headers = {"X-Hub-Signature-256": "sha256=dummy"}

    # Mock dependencies
    # We use a real MessageBuffer instance to test the actual Lock/deduplication logic!
    mb_instance = MessageBuffer(debounce_seconds=1.0)

    mock_catalog = MagicMock()
    mock_catalog.get_all_items = MagicMock(return_value=[MagicMock()] * 10) # catalog is loaded

    with patch("app.routers.whatsapp.settings") as mock_settings, \
         patch("app.routers.whatsapp._enqueue_cloud_task", new_callable=AsyncMock) as mock_enqueue, \
         patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.message_buffer", mb_instance), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog):

        mock_settings.whatsapp_app_secret = None  # Bypass signature
        mock_settings.cloud_tasks_queue_path = None
        mock_settings.task_processor_url = None
        mock_settings.min_catalog_items = 0

        # Launch them concurrently
        background_tasks_1 = BackgroundTasks()
        background_tasks_2 = BackgroundTasks()

        res1, res2 = await asyncio.gather(
            webhook_handler(mock_request_1, background_tasks_1),
            webhook_handler(mock_request_2, background_tasks_2)
        )

        # Assertions
        # One must succeed with "received" and the other must be ignored
        results = [res1, res2]
        assert {"status": "received"} in results
        assert {"status": "ignored", "procesado": False} in results

        # Verify that only one got enqueued into BackgroundTasks
        total_tasks = len(background_tasks_1.tasks) + len(background_tasks_2.tasks)
        assert total_tasks == 1
