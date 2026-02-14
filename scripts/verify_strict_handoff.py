
# scripts/verify_strict_handoff.py
import sys
import os
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

# Add app to path
sys.path.append(os.getcwd())

from unittest.mock import MagicMock
sys.modules['ffmpeg'] = MagicMock()

from app.routers import whatsapp

async def run_test():
    print("🚀 STARTING STRICT HANDOFF VERIFICATION")
    print("=" * 50)

    # --- MOCKS ---
    mock_db = MagicMock()
    mock_config_loader = MagicMock()
    mock_motor_ventas = MagicMock()
    mock_motor_financiero = MagicMock()
    mock_cerebro_ia = MagicMock()
    mock_memory_service = MagicMock()
    mock_notification_service = AsyncMock()

    # Patch global services in whatsapp.py
    whatsapp.db = mock_db
    whatsapp.config_loader = mock_config_loader
    whatsapp.motor_ventas = mock_motor_ventas
    whatsapp.motor_financiero = mock_motor_financiero
    whatsapp.memory_service = mock_memory_service
    whatsapp.notification_service = mock_notification_service
    
    # Mock Helper Functions
    whatsapp._get_session = AsyncMock(return_value={"status": "IDLE", "paused": False})
    whatsapp._update_session = AsyncMock()
    whatsapp._send_whatsapp_message = AsyncMock()
    whatsapp._send_whatsapp_status = AsyncMock()
    whatsapp._route_message = AsyncMock(return_value="AI Response")
    
    # --- TEST CASE 1: EXPLICIT HANDOFF (Check A) ---
    print("\n🧪 TEST 1: Check A - Explicit Handoff ('quiero un asesor')")
    msg_data = {"from": "573001234567", "type": "text", "text": "quiero un asesor"}
    
    # Mock prospect data (not paused yet)
    mock_memory_service.get_prospect_data.return_value = {"human_help_requested": False, "name": "Test User"}
    
    await whatsapp._handle_message_background(msg_data, "msg_id_1")
    
    # Assertions
    # 1. Should notify admin
    mock_notification_service.notify_human_handoff.assert_called()
    print("✅ Notify Admin called")
    
    # 2. Should send handoff message to user
    whatsapp._send_whatsapp_message.assert_called_with(
        "3001234567", 
        "Entendido. He pausado mi respuesta automática. 🛑 Un asesor humano revisará tu caso en breve y te escribirá por aquí. 👨💻"
    )
    print("✅ User Notification sent")
    
    # 3. Should NOT call route_message (Stopped)
    whatsapp._route_message.assert_not_called()
    print("✅ Logic STOPPED (No routing called)")
    
    
    # --- TEST CASE 2: FINANCIAL INTENT (Check B) ---
    print("\n🧪 TEST 2: Check B - Financial Intent ('necesito un credito')")
    # Reset mocks
    whatsapp._route_message.reset_mock()
    whatsapp._send_whatsapp_message.reset_mock()
    mock_notification_service.notify_human_handoff.reset_mock()
    
    msg_data = {"from": "573001234567", "type": "text", "text": "necesito un credito"}
    
    # Even if human help requested is True (simulating a paused session), Finance should BYPASS it?
    # Requirement: "Disable any internal 'Safety Handoff' ... Block valid sales topics."
    # Also "STOP: Do NOT check for handoff."
    # Let's simulate a paused session to see if it bypasses gatekeeper.
    mock_memory_service.get_prospect_data.return_value = {"human_help_requested": True, "name": "Buffered User"}
    whatsapp._get_session.return_value = {"status": "PAUSED", "paused": True}
    
    await whatsapp._handle_message_background(msg_data, "msg_id_2")
    
    # Assertions
    # 1. Should call _route_message with force_financial=True
    whatsapp._route_message.assert_called()
    call_args = whatsapp._route_message.call_args
    # Check if force_financial was passed as True
    # The signature is (..., force_financial=False)
    # We can check kwargs
    assert call_args.kwargs.get('force_financial') == True, f"Force Financial NOT set! Args: {call_args}"
    print("✅ Force Financial Flag passed correctly")
    
    # 2. Should NOT have triggered explicit handoff
    mock_notification_service.notify_human_handoff.assert_not_called()
    print("✅ No Explicit Handoff triggered")

    print("\n🎉 ALL TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(run_test())
