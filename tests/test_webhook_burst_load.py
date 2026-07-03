import pytest
import asyncio
from unittest.mock import patch, MagicMock

@pytest.mark.asyncio
async def test_10_concurrent_webhooks_no_deadlock(concurrent_webhook_factory):
    from app.routers.whatsapp import webhook_handler
    from fastapi import BackgroundTasks, Request
    from unittest.mock import AsyncMock
    
    # Generate 10 concurrent requests
    payloads = concurrent_webhook_factory(count=10)
    
    bg_tasks = BackgroundTasks()
    
    async def run_webhook(payload):
        req = MagicMock(spec=Request)
        req.headers = {}
        import json
        req.body = AsyncMock(return_value=json.dumps(payload).encode("utf-8"))
        return await webhook_handler(req, bg_tasks)

    with patch("app.routers.whatsapp.settings") as mock_settings, \
         patch("app.routers.whatsapp.db", MagicMock()), \
         patch("app.routers.whatsapp.motor_financiero", MagicMock()), \
         patch("app.routers.whatsapp._handle_message_background", AsyncMock()) as mock_handle:
         
         mock_settings.whatsapp_app_secret = None
         
         # Execute concurrently
         responses = await asyncio.gather(*(run_webhook(p) for p in payloads))
         
         assert len(responses) == 10
         for r in responses:
             assert r == {"status": "received"}
         
         # _handle_message_background is queued in bg_tasks.
         # Fast API executes background tasks sequentially or concurrently.
         # Here we just verify that bg_tasks has 10 tasks queued.
         assert len(bg_tasks.tasks) == 10
