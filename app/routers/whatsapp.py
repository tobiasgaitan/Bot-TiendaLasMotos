"""
WhatsApp Webhook Router
Handles Meta WhatsApp webhook verification and message reception with intelligent routing.
"""

import logging
import httpx
from typing import Dict, Any

from fastapi import APIRouter, Request, Query, HTTPException

from app.core.config import settings
from app.services.finance import MotorFinanciero
from app.services.catalog import MotorVentas
from app.services.ai_brain import CerebroIA

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["WhatsApp"])


@router.get("")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge")
) -> str:
    """
    WhatsApp webhook verification endpoint.
    
    Meta sends a GET request to verify the webhook URL.
    We validate the token and return the challenge to confirm.
    
    Args:
        hub_mode: Should be "subscribe"
        hub_verify_token: Token to verify (must match our configured token)
        hub_challenge: Challenge string to return if verification succeeds
        
    Returns:
        The challenge string if verification succeeds
        
    Raises:
        HTTPException: 403 if verification fails
    """
    logger.info(f"📞 Webhook verification request received")
    logger.info(f"Mode: {hub_mode}, Token: {hub_verify_token[:10]}...")
    
    # Verify the token matches our configured token
    if hub_mode == "subscribe" and hub_verify_token == settings.webhook_verify_token:
        logger.info("✅ Webhook verification successful")
        return hub_challenge
    else:
        logger.warning(f"❌ Webhook verification failed - invalid token")
        raise HTTPException(status_code=403, detail="Verification failed")


@router.post("")
async def receive_message(request: Request) -> Dict[str, str]:
    """
    WhatsApp message reception endpoint with intelligent routing.
    
    Meta sends POST requests with message data to this endpoint.
    Routes messages to appropriate service based on content and configuration.
    
    Args:
        request: FastAPI request object containing the webhook payload
        
    Returns:
        Success confirmation
    """
    try:
        # Parse the JSON payload
        payload = await request.json()
        
        logger.info("📨 WhatsApp message received")
        logger.debug(f"Payload: {payload}")
        
        # Extract message data
        if not _is_valid_message(payload):
            logger.info("⏭️  Skipping non-message event")
            return {"status": "ignored"}
        
        # Get message details
        message_data = _extract_message_data(payload)
        if not message_data:
            logger.warning("⚠️  Could not extract message data")
            return {"status": "error", "message": "Invalid message format"}
        
        user_phone = message_data["from"]
        message_text = message_data["text"]
        message_id = message_data["id"]
        
        logger.info(f"👤 From: {user_phone}")
        logger.info(f"💬 Message: {message_text}")
        
        # Initialize services
        config_loader = request.app.state.config_loader
        db = request.app.state.db
        
        # Initialize service modules with Firestore client
        motor_financiero = MotorFinanciero(config_loader)
        motor_ventas = MotorVentas(db=db, config_loader=config_loader)  # Pass Firestore client
        cerebro_ia = CerebroIA(config_loader)
        
        # Route message based on keywords
        response_text = await _route_message(
            message_text,
            config_loader,
            motor_financiero,
            motor_ventas,
            cerebro_ia
        )
        
        # Send response via WhatsApp API
        await _send_whatsapp_message(user_phone, response_text)
        
        logger.info(f"✅ Response sent to {user_phone}")
        
        return {"status": "success", "message_id": message_id}
        
    except Exception as e:
        logger.error(f"❌ Error processing webhook: {str(e)}", exc_info=True)
        # Return 200 anyway to prevent Meta from retrying
        return {"status": "error", "message": str(e)}


def _is_valid_message(payload: Dict[str, Any]) -> bool:
    """
    Check if payload contains a valid message.
    
    Args:
        payload: WhatsApp webhook payload
    
    Returns:
        True if payload contains a message, False otherwise
    """
    try:
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        
        return len(messages) > 0
    except (IndexError, KeyError):
        return False


def _extract_message_data(payload: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract message data from WhatsApp payload.
    
    Args:
        payload: WhatsApp webhook payload
    
    Returns:
        Dictionary with message data or None if extraction fails
    """
    try:
        entry = payload["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]
        message = value["messages"][0]
        
        return {
            "from": message["from"],
            "id": message["id"],
            "text": message.get("text", {}).get("body", ""),
            "timestamp": message["timestamp"]
        }
    except (IndexError, KeyError) as e:
        logger.error(f"Error extracting message data: {str(e)}")
        return None


async def _route_message(
    message_text: str,
    config_loader,
    motor_finanzas: MotorFinanciero,
    motor_ventas: MotorVentas,
    cerebro_ia: CerebroIA
) -> str:
    """
    Route message to appropriate service based on keywords.
    
    Args:
        message_text: User message text
        config_loader: ConfigLoader instance
        motor_finanzas: Financial motor instance
        motor_ventas: Sales motor instance
        cerebro_ia: AI brain instance
    
    Returns:
        Response text from appropriate service
    """
    try:
        # Get routing rules from configuration
        routing_rules = config_loader.get_routing_rules()
        financial_keywords = routing_rules.get("financial_keywords", [])
        sales_keywords = routing_rules.get("sales_keywords", [])
        
        # Add hardcoded financial keywords for robustness
        extended_finance_keywords = financial_keywords + [
            "deuda", "pagar", "financiar", "financiación", "financiacion", 
            "millones", "palos", "k", "cuota", "interés", "interes", 
            "crédito", "credito", "incial", "inicial"
        ]
        
        # Step 1: Check for financial intent (Priority #1)
        # We check this FIRST to capture "How much down payment for NKD?" as finance, not sales
        if _has_financial_intent(message_text, extended_finance_keywords):
            logger.info("💰 Routing to MotorFinanciero (Financial Intent Detected)")
            # Pass the full message so entity extraction can find the bike name
            return motor_finanzas.simular_credito(message_text, motor_ventas)
        
        # Step 2: Check for sales/catalog keywords
        message_lower = message_text.lower()
        if any(keyword in message_lower for keyword in sales_keywords):
            logger.info("🏍️  Routing to MotorVentas")
            return motor_ventas.buscar_moto(message_text)
        
        # Step 3: Default to AI brain
        else:
            logger.info("🧠 Routing to CerebroIA")
            return cerebro_ia.pensar_respuesta(message_text)
            
    except Exception as e:
        logger.error(f"❌ Error routing message: {str(e)}")
        # Fallback to AI brain
        return cerebro_ia.pensar_respuesta(message_text)


def _has_financial_intent(text: str, keywords: list) -> bool:
    """
    Check if message has financial intent based on keywords or numeric values.
    
    Args:
        text: Message text
        keywords: List of financial keywords
        
    Returns:
        True if financial intent detected
    """
    text_lower = text.lower()
    
    # 1. Check Keywords
    if any(keyword in text_lower for keyword in keywords):
        return True
        
    # 2. Check for large numbers or specific formats
    import re
    
    # Pattern for "k" notation (e.g., 500k, 500K) -> indicates money
    if re.search(r'\d+\s*k\b', text_lower):
        return True
        
    # Pattern for "millones" or "m" (explicitly handled in keywords, but good to double check context)
    
    # Pattern for large numbers (> 100,000)
    # Removing dots/commas to parse "1.000.000" or "1000000"
    try:
        # Extract potential number sequences
        numbers = re.findall(r'\b\d[\d\.,]*\d\b|\b\d\b', text)
        for num_str in numbers:
            # Clean strings like "1.000.000" -> "1000000"
            clean_num = num_str.replace('.', '').replace(',', '')
            if clean_num.isdigit():
                value = int(clean_num)
                # If user mentions > 100,000, they are likely talking about money/down payment
                if value > 100000: 
                    return True
    except:
        pass # Ignore parsing errors
        
    return False


async def _send_whatsapp_message(to_phone: str, message_text: str) -> None:
    """
    Send message via WhatsApp Cloud API.
    
    Args:
        to_phone: Recipient phone number
        message_text: Message text to send
    """
    try:
        # CRITICAL: Early check - prevent crash if token is missing
        if not settings.whatsapp_token:
            logger.error("🔥 CRITICAL: Attempting to send message but WHATSAPP_TOKEN is empty!")
            logger.error("Message NOT sent. Please configure WHATSAPP_TOKEN in Cloud Run.")
            return
        
        if not settings.phone_number_id:
            logger.error("🔥 CRITICAL: Attempting to send message but PHONE_NUMBER_ID is empty!")
            logger.error("Message NOT sent. Please configure PHONE_NUMBER_ID in Cloud Run.")
            return
        
        # CRITICAL: Validate token before making request
        if not settings.whatsapp_token or settings.whatsapp_token.strip() == "":
            logger.critical("❌ CRITICAL: WHATSAPP_TOKEN IS MISSING OR EMPTY!")
            logger.critical(f"Token value: '{settings.whatsapp_token}'")
            logger.critical("Please set WHATSAPP_TOKEN environment variable in Cloud Run")
            raise ValueError("WhatsApp token is not configured")
        
        if not settings.phone_number_id or settings.phone_number_id.strip() == "":
            logger.critical("❌ CRITICAL: PHONE_NUMBER_ID IS MISSING OR EMPTY!")
            logger.critical(f"Phone Number ID value: '{settings.phone_number_id}'")
            logger.critical("Please set PHONE_NUMBER_ID environment variable in Cloud Run")
            raise ValueError("Phone Number ID is not configured")
        
        # WhatsApp Cloud API endpoint
        phone_number_id = settings.phone_number_id
        url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
        
        # Request headers
        headers = {
            "Authorization": f"Bearer {settings.whatsapp_token}",
            "Content-Type": "application/json"
        }
        
        # Request payload
        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "text",
            "text": {
                "body": message_text
            }
        }
        
        logger.info(f"📤 Sending message to {to_phone} via WhatsApp API")
        logger.debug(f"API URL: {url}")
        
        # Send request
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
        logger.info(f"✅ Message sent successfully to {to_phone}")
        
    except ValueError as e:
        logger.error(f"❌ Configuration error: {str(e)}")
        raise
    except httpx.HTTPStatusError as e:
        logger.error(f"❌ WhatsApp API error: {e.response.status_code} - {e.response.text}")
        raise
    except Exception as e:
        logger.error(f"❌ Error sending WhatsApp message: {str(e)}")
        raise
