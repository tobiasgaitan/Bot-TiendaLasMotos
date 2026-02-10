"""
WhatsApp Webhook Router
Handles Meta WhatsApp webhook verification and message reception with intelligent routing.
"""

import logging
import httpx
import asyncio
import time
import re
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request, Query, HTTPException, BackgroundTasks
from google.cloud import firestore

from app.core.config import settings

# CRITICAL: Import CLASSES, not instances
from app.services.finance import MotorFinanciero
from app.services.catalog import MotorVentas
from app.services.ai_brain import CerebroIA
from app.services.vision_service import VisionService
from app.services.audio_service import AudioService
from app.services.audit_service import audit_service
from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)

# ============================================================================
# GLOBAL INITIALIZATION BLOCK - DEFENSE IN DEPTH
# ============================================================================
# Initialize services individually with compartmentalized error handling.
# If one service fails, others can still initialize and the bot remains operational.

# Initialize Firestore client
db = None
try:
    db = firestore.Client()
    logger.info("✅ Firestore client initialized in whatsapp router")
except Exception as e:
    logger.error(f"❌ CRITICAL: Failed to initialize Firestore client: {e}", exc_info=True)
    db = None

# Initialize ConfigLoader
config_loader = None
if db:
    try:
        from app.core.config_loader import ConfigLoader
        config_loader = ConfigLoader(db)
        logger.info("✅ ConfigLoader initialized in whatsapp router")
    except Exception as e:
        logger.error(f"❌ Failed to initialize ConfigLoader: {e}", exc_info=True)
        config_loader = None
else:
    logger.warning("⚠️ Skipping ConfigLoader initialization (no db)")

# Initialize MotorVentas
motor_ventas = None
if db:
    try:
        motor_ventas = MotorVentas(db=db, config_loader=config_loader)
        logger.info("✅ MotorVentas initialized in whatsapp router")
    except Exception as e:
        logger.error(f"❌ Failed to initialize MotorVentas: {e}", exc_info=True)
        motor_ventas = None
else:
    logger.warning("⚠️ Skipping MotorVentas initialization (no db)")

# Initialize MotorFinanciero
motor_financiero = None
if db:
    try:
        # CRITICAL FIX: Pass db as first positional argument
        motor_financiero = MotorFinanciero(db, config_loader)
        logger.info("✅ MotorFinanciero initialized in whatsapp router")
    except Exception as e:
        logger.error(f"❌ Failed to initialize MotorFinanciero: {e}", exc_info=True)
        motor_financiero = None
else:
    logger.warning("⚠️ Skipping MotorFinanciero initialization (no db)")

# Initialize MemoryService
memory_service = None
if db:
    try:
        from app.services.memory_service import MemoryService
        memory_service = MemoryService(db)
        logger.info("✅ MemoryService initialized in whatsapp router")
    except Exception as e:
        logger.error(f"❌ Failed to initialize MemoryService: {e}", exc_info=True)
        memory_service = None
else:
    logger.warning("⚠️ Skipping MemoryService initialization (no db)")

# Initialize MessageBuffer (independent of db)
message_buffer = None
try:
    from app.services.message_buffer import MessageBuffer
    message_buffer = MessageBuffer(debounce_seconds=4.0)
    logger.info("✅ MessageBuffer initialized (class import)")
except ImportError:
    logger.warning("⚠️ MessageBuffer class not found, trying instance import")
    try:
        from app.services.message_buffer import message_buffer
        logger.info("✅ MessageBuffer initialized (instance import)")
    except ImportError:
        logger.error("❌ MessageBuffer not available, debouncing disabled")
        message_buffer = None
except Exception as e:
    logger.error(f"❌ Failed to initialize MessageBuffer: {e}", exc_info=True)
    message_buffer = None

# Log initialization summary
logger.info("=" * 60)
logger.info("🚀 WhatsApp Router Initialization Summary:")
logger.info(f"   Firestore DB: {'✅' if db else '❌'}")
logger.info(f"   ConfigLoader: {'✅' if config_loader else '❌'}")
logger.info(f"   MotorVentas: {'✅' if motor_ventas else '❌'}")
logger.info(f"   MotorFinanciero: {'✅' if motor_financiero else '❌'}")
logger.info(f"   MemoryService: {'✅' if memory_service else '❌'}")
logger.info(f"   MessageBuffer: {'✅' if message_buffer else '❌'}")
logger.info("=" * 60)

# ============================================================================
# ROUTER SETUP
# ============================================================================

# Idempotency Cache: Track messages being processed
processing_messages: set = set()

# Helper Constants
SESSION_TIMEOUT_MINUTES = 30

router = APIRouter(prefix="/webhook", tags=["WhatsApp"])


# ============================================================================
# WEBHOOK ENDPOINTS
# ============================================================================

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
async def receive_message(request: Request, background_tasks: BackgroundTasks) -> Dict[str, str]:
    """
    WhatsApp message reception endpoint with async background processing.
    Returns immediately to prevent timeout retries.
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
        
        logger.info(f"👤 From: {user_phone} | Type: {msg_type} | ID: {message_id}")
        
        # IDEMPOTENCY CHECK: Prevent duplicate processing
        if message_id in processing_messages:
            logger.warning(f"⚠️  Duplicate message ignored: {message_id}")
            return {"status": "duplicate_ignored"}
        
        # Mark as processing
        processing_messages.add(message_id)
        
        # Schedule background processing
        background_tasks.add_task(
            _handle_message_background,
            msg_data=msg_data,
            message_id=message_id
        )
        
        # Return immediately to prevent timeout
        logger.info(f"✅ Message {message_id} queued for background processing")
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"❌ Error processing webhook: {str(e)}", exc_info=True)
        # Return 200 anyway to prevent Meta from retrying
        return {"status": "error", "message": str(e)}


# ============================================================================
# BACKGROUND MESSAGE PROCESSING
# ============================================================================

async def _handle_message_background(
    msg_data: Dict[str, Any],
    message_id: str
) -> None:
    """
    Background task to process WhatsApp messages asynchronously.
    Handles AI processing, artificial latency, and message sending.
    """
    try:
        user_phone = msg_data["from"]
        msg_type = msg_data["type"]
        
        logger.info(f"🔄 Background processing started for {message_id}")
        
        # PRE-PROCESSING: Retrieve prospect data from CRM FIRST (needed for gatekeeper check)
        prospect_data = None
        if memory_service:
            try:
                # DEBUG: Log the phone number being searched
                logger.info(f"🔍 Searching identity for: {user_phone}")
                prospect_data = memory_service.get_prospect_data(user_phone)
                if prospect_data and prospect_data.get("exists"):
                    logger.info(f"🧠 Prospect data loaded for {user_phone}: {prospect_data.get('name')}")
            except Exception as e:
                logger.error(f"⚠️ Failed to load prospect data: {str(e)}")
                prospect_data = None
        
        # ============================================================================
        # GATEKEEPER: Check if user requested human help
        # ============================================================================
        # If human_help_requested flag is True, bot MUST remain silent.
        # Only manual admin intervention in Firestore can reset this flag.
        if prospect_data and prospect_data.get('human_help_requested'):
            logger.info(
                f"⏸️ User in Human Mode. AI Muted. | "
                f"Phone: {user_phone} | "
                f"Flag: human_help_requested=True"
            )
            return  # Exit immediately without processing or replying
        
        # KILL SWITCH: Check if session is paused (legacy check, kept for compatibility)
        # If paused, bot will not respond to any messages from this user
        session = await _get_session(db, user_phone)
        if session.get("paused") == True:
            paused_reason = session.get("paused_reason", "unknown")
            logger.info(f"⏸️ Session paused for {user_phone} | Reason: {paused_reason} | Message ignored")
            return  # Exit immediately without sending any response
        
        # Initialize services (use global instances)
        cerebro_ia = CerebroIA(config_loader)
        vision_service = VisionService(db)
        audio_service = AudioService(config_loader)
        
        response_text = "Lo siento, no entendí ese mensaje."
        sentiment = "NEUTRAL"
        
        # Phase 4: Sentiment Check (Before routing)
        if msg_type == "text":
            sentiment = cerebro_ia.detect_sentiment(msg_data["text"])
            if sentiment == "ANGRY":
                logger.warning(f"😡 User {user_phone} is ANGRY. Pausing session.")
                await _update_session(db, user_phone, {"status": "PAUSED", "paused": True, "paused_reason": "sentiment_angry"})
                response_text = "Noto que estás molesto. Un asesor se comunicará contigo pronto. 🙏"
                await _send_whatsapp_message(user_phone, response_text)
                # Send notification to admin
                await notification_service.notify_human_handoff(user_phone, "sentiment_angry")
                return

        # Check if PAUSED (moved after sentiment check for angry users)
        session = await _get_session(db, user_phone)
        if session.get("status") == "PAUSED":
            logger.info(f"⏸️ Session paused for {user_phone}. Ignoring message.")
            return

        # Route based on message type
        if msg_type == "text":
            text = msg_data["text"]
            
            # Generate unique task ID for debounce tracking
            task_id = f"{message_id}_{time.time()}"
            
            # Add message to buffer and check if first (only if buffer is available)
            is_first_message = False
            if message_buffer:
                is_first_message = await message_buffer.add_message(user_phone, text, task_id)
            
            # CRITICAL: Send typing indicator immediately if first message
            # This provides instant feedback while we accumulate messages
            if is_first_message:
                logger.info(f"⌨️ Sending typing indicator for first message from {user_phone}")
                await _send_whatsapp_status(user_phone, "typing")
            
            # Debounce period: Wait 4 seconds to accumulate fragmented messages (only if buffer is available)
            if message_buffer:
                logger.info(f"⏳ Starting {message_buffer.debounce_seconds}s debounce for {user_phone} (task: {task_id})")
                await asyncio.sleep(message_buffer.debounce_seconds)
                
                # Check if this task is still active (not superseded by newer message)
                if not message_buffer.is_task_active(user_phone, task_id):
                    logger.info(f"⏭️ Task {task_id} superseded for {user_phone}, aborting silently")
                    return
                
                # Retrieve aggregated message from buffer
                aggregated_text = await message_buffer.get_aggregated_message(user_phone)
                
                if not aggregated_text:
                    logger.warning(f"⚠️ Empty aggregated message for {user_phone}, aborting")
                    await message_buffer.clear_buffer(user_phone)
                    return
                
                logger.info(
                    f"🔀 Processing aggregated message for {user_phone} | "
                    f"Length: {len(aggregated_text)} chars | "
                    f"Task: {task_id}"
                )
            else:
                # No buffer available, use original text
                aggregated_text = text
                logger.info(f"⚠️ MessageBuffer not available, processing message directly")
            
            # Process the aggregated message
            response_text = await _route_message(
                aggregated_text, config_loader, motor_financiero, motor_ventas, cerebro_ia, db, user_phone, prospect_data
            )
            
            # Check if AI triggered human handoff
            if response_text.startswith("HANDOFF_TRIGGERED:"):
                # Extract reason from response
                reason = response_text.split(":", 1)[1] if ":" in response_text else "unknown"
                
                logger.warning(f"🚨 Human handoff triggered for {user_phone} | Reason: {reason}")
                
                # Set the human_help_requested flag in Firestore
                if memory_service:
                    try:
                        memory_service.set_human_help_status(user_phone, True)
                        logger.info(f"✅ Set human_help_requested=True for {user_phone}")
                    except Exception as e:
                        logger.error(f"❌ Failed to set human_help_status: {str(e)}")
                
                # Pause the session (legacy compatibility)
                await _update_session(db, user_phone, {
                    "paused": True,
                    "paused_reason": "human_handoff",
                    "handoff_reason": reason,
                    "status": "PAUSED"
                })
                
                # Send notifications to admin
                await notification_service.notify_human_handoff(user_phone, reason)
                
                # Replace response with exact required phrase
                response_text = "Entendido, te paso con un asesor humano."
            
            # Clear buffer after successful processing (only if buffer is available)
            if message_buffer:
                await message_buffer.clear_buffer(user_phone)
            
        elif msg_type == "image":
            logger.info("📷 Image received")
            media_id = msg_data["media_id"]
            mime_type = msg_data["mime_type"]
            image_bytes = await _download_media(media_id)
            if image_bytes:
                response_text = await vision_service.analyze_image(image_bytes, mime_type, user_phone)
            else:
                response_text = "No pude descargar la imagen. 😢"
                
        elif msg_type == "audio":
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

        # Keep-Alive Typing Loop: Maintain "Escribiendo..." indicator
        # Cap at 5s max to avoid excessive delays (0.04s per char, ~125 chars = 5s)
        delay = min(len(response_text) * 0.04, 5.0)
        logger.info(f"⏳ Artificial Latency: {delay:.2f}s (response: {len(response_text)} chars)")
        
        elapsed = 0.0
        typing_interval = 5.0  # WhatsApp typing indicator lasts ~5s
        
        while elapsed < delay:
            await _send_whatsapp_status(user_phone, "typing")
            sleep_time = min(typing_interval, delay - elapsed)
            await asyncio.sleep(sleep_time)
            elapsed += sleep_time
        
        # Send response
        await _send_whatsapp_message(user_phone, response_text)
        
        # POST-PROCESSING: Update prospect summary in CRM (only for successful responses)
        if msg_type == "text" and not response_text.startswith("HANDOFF_TRIGGERED:"):
            if memory_service:
                try:
                    # Generate conversation summary with structured data extraction
                    aggregated_text_for_summary = locals().get("aggregated_text", msg_data.get("text", ""))
                    conversation = f"Usuario: {aggregated_text_for_summary}\nSebas: {response_text}"
                    summary_data = cerebro_ia.generate_summary(conversation)
                    
                    # Update prospect summary in Firestore
                    await memory_service.update_prospect_summary(
                        user_phone,
                        summary_data.get("summary", ""),
                        summary_data.get("extracted", {})
                    )
                    logger.info(f"💾 Prospect summary updated for {user_phone}")
                except Exception as e:
                    logger.error(f"⚠️ Failed to update prospect summary: {str(e)}")
        
        # Phase 4: Audit Log
        # For text messages, log the aggregated text (after debounce)
        # For media messages, log the type indicator
        if msg_type == "text":
            user_input = locals().get("aggregated_text", msg_data.get("text", "[Unknown]"))
        else:
            user_input = "[Media]"
        await audit_service.log_interaction(user_phone, user_input, response_text, sentiment)
        
        logger.info(f"✅ Response sent to {user_phone}")
        
    except Exception as e:
        logger.error(f"❌ Error in background processing: {str(e)}", exc_info=True)
    finally:
        # CRITICAL: Remove from processing cache
        if message_id in processing_messages:
            processing_messages.remove(message_id)
            logger.debug(f"🗑️  Removed {message_id} from processing cache")


# ============================================================================
# HELPER FUNCTIONS - MESSAGE VALIDATION & EXTRACTION
# ============================================================================

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
    """
    Extract message data from WhatsApp webhook payload.
    
    Args:
        payload: WhatsApp webhook payload
        
    Returns:
        Dictionary with message data or None if extraction fails
    """
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


# ============================================================================
# HELPER FUNCTIONS - MEDIA DOWNLOAD
# ============================================================================

async def _download_media(media_id: str) -> bytes:
    """
    Download media from WhatsApp Cloud API.
    
    Args:
        media_id: WhatsApp media ID
        
    Returns:
        Media bytes or None if download fails
    """
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


# ============================================================================
# HELPER FUNCTIONS - SESSION MANAGEMENT
# ============================================================================

async def _get_session(db: Any, phone: str) -> Dict[str, Any]:
    """
    Get user session from Firestore.
    
    Args:
        db: Firestore client
        phone: User phone number
        
    Returns:
        Session dictionary with status, answers, and last_interaction
    """
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
    """
    Update user session in Firestore.
    
    Args:
        db: Firestore client
        phone: User phone number
        data: Session data to update
    """
    try:
        doc_ref = db.collection("mensajeria").document("whatsapp").collection("sesiones").document(phone)
        data["last_interaction"] = datetime.now(timezone.utc)
        doc_ref.set(data, merge=True)
    except Exception as e:
        logger.error(f"Error updating session: {e}")


# ============================================================================
# HELPER FUNCTIONS - FINANCIAL SURVEY FLOW
# ============================================================================

async def _handle_survey_flow(
    db: Any,
    phone: str,
    message_text: str,
    current_session: Dict[str, Any],
    motor_finanzas: MotorFinanciero
) -> str:
    """
    Handle the multi-step financial survey.
    
    Args:
        db: Firestore client
        phone: User phone number
        message_text: User's message
        current_session: Current session data
        motor_finanzas: MotorFinanciero instance
        
    Returns:
        Response text for the current survey step
    """
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


# ============================================================================
# HELPER FUNCTIONS - MESSAGE ROUTING
# ============================================================================

async def _route_message(
    message_text: str,
    config_loader,
    motor_finanzas: MotorFinanciero,
    motor_ventas: MotorVentas,
    cerebro_ia: CerebroIA,
    db: Any,
    user_phone: str,
    prospect_data: Optional[Dict[str, Any]] = None
) -> str:
    """
    Route message to appropriate handler based on intent.
    
    Args:
        message_text: User's message text
        config_loader: ConfigLoader instance
        motor_finanzas: MotorFinanciero instance
        motor_ventas: MotorVentas instance
        cerebro_ia: CerebroIA instance
        db: Firestore client
        user_phone: User phone number
        prospect_data: Optional prospect data from CRM
        
    Returns:
        Response text
    """
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

    # AI Brain with Context (Memory) and Prospect Data
    context = session.get("summary", "")
    return cerebro_ia.pensar_respuesta(message_text, context=context, prospect_data=prospect_data)


def _has_financial_intent(text: str, keywords: list) -> bool:
    """
    Check for financial intent in user message.
    
    Args:
        text: User message text
        keywords: List of financial keywords
        
    Returns:
        True if financial intent detected, False otherwise
    """
    text_lower = text.lower()
    if any(keyword in text_lower for keyword in keywords):
        return True
    # Simple regex for money amounts if needed, but keywords usually suffice for "initiation"
    return False


# ============================================================================
# HELPER FUNCTIONS - WHATSAPP API
# ============================================================================

async def _send_whatsapp_message(to_phone: str, message_text: str) -> None:
    """
    Send message via WhatsApp Cloud API with guaranteed timeout enforcement.
    
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
            "recipient_type": "individual",
            "to": to_phone,
            "type": "text",
            "text": {"body": message_text}
        }
        
        logger.info(f"📤 Sending message to {to_phone} via WhatsApp API")

        # CRITICAL: Disable connection pooling AND pass timeout to post() method
        # Request-level timeout overrides client-level config
        limits = httpx.Limits(max_connections=1, max_keepalive_connections=0)
        
        # Direct HTTP call with request-level timeout
        async with httpx.AsyncClient(limits=limits) as client:
            response = await client.post(
                url,
                json=payload,
                headers=headers,
                timeout=5.0  # HARD TIMEOUT: Request-level enforcement
            )
            response.raise_for_status()
            
        logger.info(f"✅ Message sent successfully to {to_phone}")
            
    except httpx.HTTPStatusError as e:
        logger.error(f"❌ WhatsApp API error: {e.response.status_code} - {e.response.text}")
        raise
    except httpx.TimeoutException as e:
        logger.error(f"⏱️ TIMEOUT: Request exceeded 5s limit: {repr(e)}")
        raise
    except Exception as e:
        logger.error(f"❌ Error sending WhatsApp message: {repr(e)}")
        raise


async def _send_whatsapp_status(to_phone: str, status: str = "typing") -> None:
    """
    Mark message as read to show bot activity.
    
    WhatsApp Cloud API doesn't have a native typing indicator.
    We use mark-as-read to show the bot is active and processing.
    
    Args:
        to_phone: Recipient phone number
        status: Status to set (currently ignored)
    """
    # WhatsApp Cloud API limitation: No native typing indicator
    # The keep-alive loop (5s intervals) provides timing simulation
    # Mark-as-read would require a message_id which we don't have here
    # So we just log for now - the artificial delay provides the UX
    logger.debug(f"⏳ Processing for {to_phone} (keep-alive loop active)")
    pass
