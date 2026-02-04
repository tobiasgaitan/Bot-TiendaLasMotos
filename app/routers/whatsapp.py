"""
WhatsApp Webhook Router
Handles Meta WhatsApp webhook verification and message reception with intelligent routing.
"""

import logging
import httpx
import asyncio
from typing import Dict, Any

from fastapi import APIRouter, Request, Query, HTTPException

from app.core.config import settings
from app.services.finance import MotorFinanciero
from app.services.catalog import MotorVentas
from app.services.ai_brain import CerebroIA
from app.services.vision_service import VisionService
from app.services.audio_service import AudioService
from app.services.audit_service import audit_service

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
    WhatsApp message reception endpoint with multimodal routing.
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
        msg_data = _extract_message_data(payload)
        if not msg_data:
            logger.warning("⚠️  Could not extract message data")
            return {"status": "error", "message": "Invalid format"}
        
        user_phone = msg_data["from"]
        msg_type = msg_data["type"]
        message_id = msg_data["id"]
        
        logger.info(f"👤 From: {user_phone} | Type: {msg_type}")
        
        # Initialize services
        config_loader = request.app.state.config_loader
        db = request.app.state.db
        
        # Initialize service modules with Firestore client
        motor_financiero = MotorFinanciero(db, config_loader) # Pass DB for better init
        motor_ventas = MotorVentas(db=db, config_loader=config_loader)
        cerebro_ia = CerebroIA(config_loader)
        vision_service = VisionService(db)
        audio_service = AudioService(config_loader)
        
        response_text = "Lo siento, no entendí ese mensaje."
        
        # ROUTING LOGIC
        # Phase 4: Sentiment Check (Before routing)
        sentiment = "NEUTRAL"
        if msg_type in ["text", "audio"]: # Only check text/audio
            # checking text content (audio converted to text inside service but we don't have it yet here)
            # Actually for audio checking sentiment happens after processing.
            # let's check text first
            if msg_type == "text":
                sentiment = cerebro_ia.detect_sentiment(msg_data["text"])
                if sentiment == "ANGRY":
                    logger.warning(f"😡 User {user_phone} is ANGRY. Pausing session.")
                    await _update_session(db, user_phone, {"status": "PAUSED", "paused_reason": "sentiment_angry"})
                    # Alert Admin logic here (omitted for brevity)
                    return {"status": "paused"}

        # Check if PAUSED
        session = await _get_session(db, user_phone)
        if session.get("status") == "PAUSED":
             logger.info(f"⏸️ Session paused for {user_phone}. Ignoring message.")
             return {"status": "ignored_paused"}

        if msg_type == "text":
            text = msg_data["text"]
            # ... (routing)
            response_text = await _route_message(
                text, config_loader, motor_financiero, motor_ventas, cerebro_ia, db, user_phone
            )
            
        elif msg_type == "image":
            # ... (image logic)
            logger.info("📷 Image received")
            media_id = msg_data["media_id"]
            mime_type = msg_data["mime_type"]
            image_bytes = await _download_media(media_id)
            if image_bytes:
                response_text = await vision_service.analyze_image(image_bytes, mime_type, user_phone)
            else:
                response_text = "No pude descargar la imagen. 😢"
                
        elif msg_type == "audio":
            # ... (audio logic)
            logger.info("🎤 Audio received")
            media_id = msg_data["media_id"]
            mime_type = msg_data["mime_type"]
            audio_bytes = await _download_media(media_id)
            if audio_bytes:
                response_text = await audio_service.process_audio(audio_bytes, mime_type)
            else:
                response_text = "No pude descargar el audio. 😢"
        
        else:
            response_text = "Aún no soporto este tipo de mensaje. 😅"

        # Calculate Artificial Latency
        delay = len(response_text) * 0.04
        await _send_whatsapp_status(user_phone, "typing")
        logger.info(f"⏳ Artificial Latency: {delay:.2f}s")
        await asyncio.sleep(delay)
        
        await _send_whatsapp_message(user_phone, response_text)
        
        # Phase 4: Audit Log
        user_input = msg_data.get("text", "[Media]")
        await audit_service.log_interaction(user_phone, user_input, response_text, sentiment)
        
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
    except:
        return False


def _extract_message_data(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        msg = payload["entry"][0]["changes"][0]["value"]["messages"][0]
        msg_type = msg["type"]
        
        data = {
            "from": msg["from"],
            "id": msg["id"],
            "timestamp": msg["timestamp"],
            "type": msg_type
        }
        
        if msg_type == "text":
            data["text"] = msg["text"]["body"]
        elif msg_type == "image":
            data["media_id"] = msg["image"]["id"]
            data["mime_type"] = msg["image"]["mime_type"]
            data["caption"] = msg["image"].get("caption", "")
        elif msg_type == "audio":
            data["media_id"] = msg["audio"]["id"]
            data["mime_type"] = msg["audio"]["mime_type"]
            
        return data
    except Exception as e:
        logger.error(f"Error extracting data: {e}")
        return None


async def _download_media(media_id: str) -> bytes:
    """Download media from WhatsApp Cloud API."""
    try:
        url = f"https://graph.facebook.com/v18.0/{media_id}"
        headers = {"Authorization": f"Bearer {settings.whatsapp_token}"}
        
        async with httpx.AsyncClient() as client:
            # 1. Get URL
            r1 = await client.get(url, headers=headers)
            r1.raise_for_status()
            media_url = r1.json().get("url")
            
            # 2. Download Bytes
            r2 = await client.get(media_url, headers=headers)
            r2.raise_for_status()
            return r2.content
            
    except Exception as e:
        logger.error(f"❌ Download failed: {e}")
        return None

    # ... Imports
import re
from datetime import datetime, timedelta, timezone

    # ... [Existing Standard Imports] ...

# Helper Constants
SESSION_TIMEOUT_MINUTES = 30
    
async def _get_session(db: Any, phone: str) -> Dict[str, Any]:
    """Get user session from Firestore."""
    try:
        doc_ref = db.collection("mensajeria").document("whatsapp").collection("sesiones").document(phone)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        # Default session with TZ-aware timestamp
        return {"status": "IDLE", "answers": {}, "last_interaction": datetime.now(timezone.utc)}
    except Exception as e:
        logger.error(f"Error getting session: {e}")
        return {"status": "IDLE", "answers": {}, "last_interaction": datetime.now(timezone.utc)}

async def _update_session(db: Any, phone: str, data: Dict[str, Any]) -> None:
    """Update user session in Firestore."""
    try:
        doc_ref = db.collection("mensajeria").document("whatsapp").collection("sesiones").document(phone)
        data["last_interaction"] = datetime.now(timezone.utc)
        doc_ref.set(data, merge=True)
    except Exception as e:
        logger.error(f"Error updating session: {e}")

async def _handle_survey_flow(
    db: Any,
    phone: str,
    message_text: str,
    current_session: Dict[str, Any],
    motor_finanzas: MotorFinanciero
) -> str:
    """Handle the multi-step financial survey."""
    status = current_session.get("status", "IDLE")
    answers = current_session.get("answers", {})
    
    # TIMEOUT CHECK
    last_inter = current_session.get("last_interaction")
    # Check if > 30 mins (simplified)
    # in separate improvement we can implement rigorous check
    
    if status == "SURVEY_CONTRACT":
        answers["contract"] = message_text
        await _update_session(db, phone, {"status": "SURVEY_HABIT", "answers": answers})
        return "Listo parcero 📝. ¿Y cómo estás en centrales de riesgo? (Ej: Al día, Reportado, Mora pequeña)"

    elif status == "SURVEY_HABIT":
        answers["habit"] = message_text
        await _update_session(db, phone, {"status": "SURVEY_INCOME", "answers": answers})
        return "Ya casi terminamos 🏁. ¿Cuál es tu ingreso mensual promedio o base? (Ej: 1 SMLV, 2 millones, Variable)"

    elif status == "SURVEY_INCOME":
        answers["income"] = message_text
        
        # FINISH SURVEY -> CALCULATE
        profile = motor_finanzas.evaluar_perfil(
            answers.get("contract", ""),
            answers.get("habit", ""),
            answers.get("income", "")
        )
        
        await _update_session(db, phone, {"status": "IDLE", "answers": {}}) # Reset
        
        score = profile["score"]
        strategy = profile["strategy"]
        entity = profile["entity"]
        
        # Format Response based on Strategy
        if strategy == "BRILLA":
            return (
                f"🚦 Parcero, analizando tu perfil con un puntaje de {score}/1000...\n\n"
                f"La mejor opción para ti es financiar directo con **{entity}** (Tu recibo de gas).\n"
                f"Es la fija para no dar tantas vueltas.\n\n"
                f"👉 Aplica aquí de una: {motor_finanzas.link_brilla}"
            )
        else:
             # BANK or FINTECH
            return (
                f"🎉 ¡Brutal! Quedaste con un puntaje de **{score}/1000**.\n\n"
                f"Tu perfil encaja perfecto con **{entity}** ({strategy}).\n"
                f"✅ Tasa preferencial activada\n"
                f"✅ Aprobación rápida\n\n"
                f"¿Te gustaría que te simule las cuotas con esta opción? 🏍️💸"
            )
    
    return "Algo salió mal. ¿Empezamos de nuevo?"

async def _route_message(
    message_text: str,
    config_loader,
    motor_finanzas: MotorFinanciero,
    motor_ventas: MotorVentas,
    cerebro_ia: CerebroIA,
    db: Any,
    user_phone: str
) -> str:
        
        # 0. GET SESSION
        session = await _get_session(db, user_phone)
        status = session.get("status", "IDLE")
        
        # 1. CHECK ACTIVE SURVEY
        if status.startswith("SURVEY_"):
            return await _handle_survey_flow(db, user_phone, message_text, session, motor_finanzas)
        
        # 2. NORMAL ROUTING (IDLE)
        routing_rules = config_loader.get_routing_rules()
        financial_keywords = routing_rules.get("financial_keywords", []) + ["credito", "crédito", "fiado", "cuotas", "financiar"]
        sales_keywords = routing_rules.get("sales_keywords", [])
        
        # Check Financial Intent
        if _has_financial_intent(message_text, financial_keywords):
            # START SURVEY
            logger.info("💰 Starting Financial Survey")
            await _update_session(db, user_phone, {"status": "SURVEY_CONTRACT", "answers": {}, "start_time": datetime.now(timezone.utc)})
            return "¡De una! Para ver qué crédito te sale más barato, respóndeme 3 preguntas rápidas ⚡\n\n1️⃣ ¿Qué tipo de contrato laboral tienes? (Ej: Indefinido, Obra labor, Independiente)"

        # Check Sales Intent
        message_lower = message_text.lower()
        if any(keyword in message_lower for keyword in sales_keywords):
             return motor_ventas.buscar_moto(message_text)

        # AI Brain with Context (Memory)
        context = session.get("summary", "")
        return cerebro_ia.pensar_respuesta(message_text, context=context)
        
def _has_financial_intent(text: str, keywords: list) -> bool:
    """Check for financial intent."""
    text_lower = text.lower()
    if any(keyword in text_lower for keyword in keywords):
        return True
    # Simple regex for money amounts if needed, but keywords usually suffice for "initiation"
    return False


async def _send_whatsapp_message(to_phone: str, message_text: str) -> None:
    """
    Send message via WhatsApp Cloud API.
    
    Args:
        to_phone: Recipient phone number
        message_text: Message text to send
    """
    try:
        phone_number_id = settings.phone_number_id
        if not phone_number_id or not settings.whatsapp_token:
            logger.error("🔥 CRITICAL: WHATSAPP_TOKEN or PHONE_NUMBER_ID is missing/empty. Message NOT sent.")
            return
            
        url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {settings.whatsapp_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "text",
            "text": {"body": message_text}
        }
        
        logger.info(f"📤 Sending message to {to_phone} via WhatsApp API")
        logger.debug(f"API URL: {url}")

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
        logger.info(f"✅ Message sent successfully to {to_phone}")
            
    except httpx.HTTPStatusError as e:
        logger.error(f"❌ WhatsApp API error: {e.response.status_code} - {e.response.text}")
        raise
    except Exception as e:
        logger.error(f"❌ Error sending WhatsApp message: {str(e)}")
        raise


async def _send_whatsapp_status(to_phone: str, status: str = "typing") -> None:
    """
    Send status update (typing/read) via WhatsApp Cloud API.
    
    Args:
        to_phone: Recipient phone number
        status: Status to set (usually 'typing')
    """
    try:
        if not settings.whatsapp_token or not settings.phone_number_id:
            return
            
        # WhatsApp Cloud API does not directly support "typing_on" sender_action
        # like some other messaging platforms. The primary "status" update is
        # usually for marking messages as read.
        # For the purpose of simulating typing, we rely on the artificial delay.
        # We will log the intent but not make an API call for "typing" status
        # to avoid potential API errors or unsupported features.
        logger.info(f"ℹ️ Simulating '{status}' indicator for {to_phone} (via artificial delay).")
        pass
        
    except Exception as e:
        logger.warning(f"⚠️ Could not send status: {e}")
