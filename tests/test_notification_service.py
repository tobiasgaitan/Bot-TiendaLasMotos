"""
[BOT-BUILD-DEUDA-OTEL-03-06] Regression tests for NotificationService Graph API version.

Certifies that the WhatsApp alert URL consumes settings.whatsapp_api_version
(single-source, BOT-BUILD-REGRESSION-MULTIMODAL-01) and that no hardcoded
Graph API version literal (e.g. "v18.0") can regress into the module.
"""

import inspect
import re
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.config import settings
from app.services.notification_service import NotificationService
import app.services.notification_service as notification_module


def _make_async_client_mock():
    """Build a mock httpx.AsyncClient supporting the async context manager protocol."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


async def test_whatsapp_alert_uses_configured_api_version():
    """The request URL must be built from settings.whatsapp_api_version, never a literal."""
    service = NotificationService()
    service.admin_whatsapp = "573001112233"

    mock_client = _make_async_client_mock()
    with patch.object(settings, "whatsapp_token", "TEST_TOKEN"), \
         patch.object(settings, "phone_number_id", "TEST_PHONE_ID"), \
         patch.object(settings, "whatsapp_api_version", "vTEST_SENTINEL"), \
         patch("app.services.notification_service.httpx.AsyncClient", return_value=mock_client):
        sent = await service.send_whatsapp_alert("test message")

    assert sent is True, "send_whatsapp_alert must succeed with mocked HTTP layer"
    mock_client.post.assert_awaited_once()
    called_url = mock_client.post.call_args.args[0]
    assert called_url == (
        "https://graph.facebook.com/vTEST_SENTINEL/TEST_PHONE_ID/messages"
    ), f"URL must inject settings.whatsapp_api_version dynamically, got: {called_url}"


def test_no_hardcoded_graph_api_version_literal():
    """Static guard: fail if a hardcoded version literal regresses into the module."""
    source = inspect.getsource(notification_module)
    match = re.search(r"graph\.facebook\.com/v\d", source)
    assert match is None, (
        f"❌ REGRESIÓN DE HARDCODING: literal de versión detectado en "
        f"notification_service.py: '{match.group(0)}'. "
        f"Use settings.whatsapp_api_version (single-source)."
    )
