import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.routers.whatsapp import _handle_message_background

def test_handle_message_background_is_decorated():
    """
    Verify that the webhook handler _handle_message_background is decorated with @observe
    by asserting the structural wrapper attribute '__wrapped__'.
    """
    assert hasattr(_handle_message_background, "__wrapped__"), "The function _handle_message_background must be decorated with @observe"

@pytest.mark.asyncio
async def test_trace_propagation_context_update():
    """
    Verify that when _handle_message_background is called, it propagates
    user_id and session_id to langfuse_context.update_current_trace.
    """
    msg_data = {
        "from": "573001234567",
        "type": "text",
        "text": "Hola, me interesa la TVS Sport 100",
        "id": "wamid.HBgLNTczMDAxMjM0NTY3FQIAERgSRTk0OTM5OTg1RkMxMEM5NTI3AA==",
        "phone_number_id": "123456789"
    }
    
    mock_lf_context = MagicMock()
    
    # Mock dependencies to isolate test and stop execution early (return False on add_message)
    with patch("app.routers.whatsapp._ensure_services") as mock_ensure_services, \
         patch("app.routers.whatsapp.message_buffer") as mock_message_buffer, \
         patch("langfuse.decorators.langfuse_context", mock_lf_context, create=True), \
         patch("app.routers.whatsapp.langfuse_context", mock_lf_context):
         
        # Simulate add_message returning False to trigger early exit (idempotency check)
        mock_message_buffer.add_message = AsyncMock(return_value=False)
        
        # We also need a mock background tasks
        mock_bg_tasks = MagicMock()
        
        # Invoke the handler (it should run update_current_trace and then return early)
        await _handle_message_background(msg_data, mock_bg_tasks)
        
        # Assertions
        mock_ensure_services.assert_called_once()
        mock_lf_context.update_current_trace.assert_called_once_with(
            user_id="+573001234567",
            session_id="wa_+573001234567",
            metadata={
                "msg_id": "wamid.HBgLNTczMDAxMjM0NTY3FQIAERgSRTk0OTM5OTg1RkMxMEM5NTI3AA==",
                "phone_number_id": "123456789",
                "msg_type": "text"
            }
        )
        
        # Verify it exited early via message_buffer.add_message call
        mock_message_buffer.add_message.assert_called_once_with(
            "+573001234567", "Hola, me interesa la TVS Sport 100", "wamid.HBgLNTczMDAxMjM0NTY3FQIAERgSRTk0OTM5OTg1RkMxMEM5NTI3AA=="
        )
