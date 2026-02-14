"""
WhatsApp Webhook Router
=======================
Handles Meta WhatsApp webhook verification and message reception
with intelligent routing through AI, financial, and sales engines.

Architecture:
    POST /webhook  →  fast 200  →  BackgroundTask  →  _handle_message_background
    GET  /webhook  →  hub.challenge verification

Logic order inside _handle_message_background:
    1. Input Parsing
    2. Magic Word Check (#bot / #reset) — returns immediately
    3. Prospect Data Load (CRM)
    4. Timestamp Update
    5. Human Mode Gatekeeper — silent return if flagged
    6. AI Logic (sentiment, routing, response, summary)
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

# Import CLASSES (not instances) — each request may need fresh config
from app.services.finance import MotorFinanciero
from app.services.catalog import MotorVentas
from app.services.ai_brain import CerebroIA
from app.services.vision_service import VisionService
from app.services.audio_service import AudioService
from app.services.audit_service import audit_service
from app.services.notification_service import notification_service
from app.services.financial_service import financial_service

logger = logging.getLogger(__name__)

# ============================================================================
# GLOBAL INITIALIZATION — DEFENSE IN DEPTH
# ============================================================================
# Each service is wrapped in its own try/except so a single failure
# does not cascade and take down the entire router.

# --- Firestore client ---
db = None
try:
    db = firestore.Client()
    logger.info("✅ Firestore client initialized in whatsapp router")
except Exception as e:
    logger.error(f"❌ CRITICAL: Failed to initialize Firestore client: {e}", exc_info=True)
    db = None

# --- ConfigLoader (depends on db) ---
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

# --- MotorVentas (depends on db) ---
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

# --- MotorFinanciero (depends on db) ---
motor_financiero = None
if db:
    try:
        motor_financiero = MotorFinanciero(db, config_loader)
        logger.info("✅ MotorFinanciero initialized in whatsapp router")
    except Exception as e:
        logger.error(f"❌ Failed to initialize MotorFinanciero: {e}", exc_info=True)
        motor_financiero = None
else:
    logger.warning("⚠️ Skipping MotorFinanciero initialization (no db)")

# --- MemoryService (depends on db) ---
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

# --- MessageBuffer (independent of db) ---
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

# --- Initialization summary ---
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

# Idempotency cache — prevents duplicate processing of the same message_id
processing_messages: set = set()

SESSION_TIMEOUT_MINUTES = 30

router = APIRouter(prefix="/webhook", tags=["WhatsApp"])


# ============================================================================
# WEBHOOK ENDPOINTS
# ============================================================================

@router.get("")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
) -> str:
    """
    Meta webhook verification (GET).

    Validates the verify token and echoes the challenge string back
    so Meta confirms our endpoint is alive.

    Args:
        hub_mode: Must be ``subscribe``.
        hub_verify_token: Must match ``settings.webhook_verify_token``.
        hub_challenge: Echoed back on success.

    Returns:
        The challenge string.

    Raises:
        HTTPException: 403 when the token does not match.
    """
    logger.info("📞 Webhook verification request received")
    logger.info(f"Mode: {hub_mode}, Token: {hub_verify_token[:10]}...")

    if hub_mode == "subscribe" and hub_verify_token == settings.webhook_verify_token:
        logger.info("✅ Webhook verification successful")
        return hub_challenge
    else:
        logger.warning("❌ Webhook verification failed - invalid token")
        raise HTTPException(status_code=403, detail="Verification failed")


@router.post("")
async def receive_message(
    request: Request,
    background_tasks: BackgroundTasks,
) -> Dict[str, str]:
    """
    WhatsApp message reception (POST).

    Returns HTTP 200 immediately and queues background processing
    to avoid Meta's 15-second timeout retry.
    """
    try:
        payload = await request.json()

        logger.info("📨 WhatsApp message received")
        logger.debug(f"Payload: {payload}")

        if not _is_valid_message(payload):
            logger.info("⏭️  Skipping non-message event")
            return {"status": "ignored"}

        msg_data = _extract_message_data(payload)
        if not msg_data:
            logger.warning("⚠️  Could not extract message data")
            return {"status": "error", "message": "Invalid format"}

        user_phone = msg_data["from"]
        msg_type = msg_data["type"]
        message_id = msg_data["id"]

        logger.info(f"👤 From: {user_phone} | Type: {msg_type} | ID: {message_id}")

        # Idempotency — prevent duplicate background tasks
        if message_id in processing_messages:
            logger.warning(f"⚠️  Duplicate message ignored: {message_id}")
            return {"status": "duplicate_ignored"}

        processing_messages.add(message_id)

        background_tasks.add_task(
            _handle_message_background,
            msg_data=msg_data,
            message_id=message_id,
        )

        logger.info(f"✅ Message {message_id} queued for background processing")
        return {"status": "ok"}

    except Exception as e:
        logger.error(f"❌ Error processing webhook: {str(e)}", exc_info=True)
        # Always return 200 so Meta does not retry
        return {"status": "error", "message": str(e)}


# ============================================================================
# BACKGROUND MESSAGE PROCESSING
# ============================================================================

async def _handle_message_background(
    msg_data: Dict[str, Any],
    message_id: str,
) -> None:
    """
    Core background handler — runs outside the HTTP request lifecycle.

    **Strict execution order:**

    1. Input Parsing
    2. Magic Word Check (``#bot`` / ``#reset``) → early return
    3. Prospect Data Load (CRM)
    4. Timestamp Update
    5. Human Mode Gatekeeper → silent return if flagged
    6. AI Logic (sentiment analysis, routing, response, CRM summary)
    """
    try:
        # ==============================================================
        # STEP 1: INPUT PARSING
        # ==============================================================
        raw_phone = msg_data["from"]
        msg_type = msg_data["type"]
        message_body = ""
        if msg_type == "text":
            message_body = msg_data.get("text", "").strip()

        # Normalize phone for internal use (DB keys, etc.)
        from app.core.utils import PhoneNormalizer
        user_phone = PhoneNormalizer.normalize(raw_phone)

        logger.info(f"🔄 Background processing started for {message_id} | Raw: {raw_phone} | Norm: {user_phone}")

        # ==============================================================
        # STEP 2: MAGIC WORD CHECK (#bot / #reset)
        # ==============================================================
        # Runs BEFORE loading prospect data so muted users can still
        # reactivate the bot without being blocked by the gatekeeper.
        if message_body.lower() in ("#bot", "#reset"):
            logger.info(f"🔑 Magic word '{message_body}' from {user_phone}")
            if memory_service:
                memory_service.set_human_help_status(user_phone, False)
            try:
                session_ref = db.collection("sessions").document(user_phone)
                session_ref.set({"paused": False, "paused_reason": None}, merge=True)
            except Exception as e:
                logger.warning(f"⚠️ Could not unpause legacy session: {e}")
            await _send_whatsapp_message(
                user_phone, "🤖 Bot Reactivado. ¿En qué puedo ayudarte?"
            )
            logger.info(f"✅ Bot reactivated for {user_phone}")
            return  # ← early exit

        # ==============================================================
        # STEP 3: PROSPECT DATA LOAD (CRM)
        # ==============================================================
        prospect_data = None
        if memory_service:
            try:
                logger.info(f"🔍 Searching identity for: {user_phone}")
                prospect_data = memory_service.get_prospect_data(user_phone)
                if prospect_data and prospect_data.get("exists"):
                    logger.info(
                        f"🧠 Prospect loaded: {user_phone}: "
                        f"{prospect_data.get('name')}"
                    )
            except Exception as e:
                logger.error(f"⚠️ Failed to load prospect data: {str(e)}")
                prospect_data = None

        # ==============================================================
        # LATENCY CHECK: IS NEW CONVERSATION?
        # ==============================================================
        # If the user has no summary, we treat this as a "Greeting" or first message.
        # We skip artificial delays (debounce, typing) to feel instant.
        is_new_conversation = True
        if prospect_data and prospect_data.get("summary"):
            is_new_conversation = False

        if is_new_conversation:
             # Force human_help_requested False if new conversation to ensure no blocking
             if prospect_data:
                 prospect_data['human_help_requested'] = False
             
             # DATA INTEGRITY FIX: Ensure prospect exists in DB so it shows in Admin Panel
             if memory_service:
                 memory_service.create_prospect_if_missing(user_phone)

             logger.info(f"🚀 New conversation detected (no summary) for {user_phone}. Latency will be minimized.")

        # ==============================================================
        # STEP 4: TIMESTAMP UPDATE
        # ==============================================================
        # Always update even for muted users — keeps them visible in
        # the admin dashboard so a human can follow up.
        if memory_service:
            try:
                memory_service.update_last_interaction(user_phone)
            except Exception as e:
                logger.warning(f"⚠️ Could not update timestamp: {e}")

        # ==============================================================
        # STEP 5: STRICT HANDOFF & INTENT HIERARCHY (A -> B -> C)
        # ==============================================================
        
        # --- CHECK A: EXPLICIT HANDOFF (High Priority) ---
        handoff_keywords = ['asesor', 'humano', 'persona', 'alguien real', 'jefe', 'gerente', 'reclamo', 'queja']
        if any(k in message_body.lower() for k in handoff_keywords):
            logger.warning(f"🚨 EXPLICIT HANDOFF TRIGGERED by '{message_body}'")
            
            # 1. Update DB
            if memory_service:
                memory_service.set_human_help_status(user_phone, True)
            
            await _update_session(
                db, 
                user_phone, 
                {
                    "paused": True, 
                    "paused_reason": "explicit_request",
                    "status": "PAUSED"
                }
            )
            
            # 2. Notify
            await notification_service.notify_human_handoff(user_phone, "explicit_user_request")
            
            # 3. Send Message & STOP
            await _send_whatsapp_message(
                user_phone, 
                "Entendido. He pausado mi respuesta automática. 🛑 Un asesor humano revisará tu caso en breve y te escribirá por aquí. 👨💻"
            )
            return # <--- STOP

        # --- CHECK B: FINANCIAL INTENT (Medium Priority) ---
        financial_keywords = ['credito', 'financiar', 'estudio', 'cuotas', 'valor', 'precio']
        is_financial_intent = any(k in message_body.lower() for k in financial_keywords)
        
        # --- CHECK C: HUMAN GATEKEEPER (Normal Flow) ---
        # Only check gatekeeper if NOT financial intent (Financial topics bypass silence)
        if not is_financial_intent:
            # If the prospect has requested human help, the bot stays silent.
            human_help_requested = False
            if prospect_data:
                human_help_requested = prospect_data.get("human_help_requested", False)

            # FIX: Ensure we don't pause if it's a new conversation
            if human_help_requested and not is_new_conversation:
                logger.info(f"⏸️ Human Mode. AI Muted. | Flag: human_help_requested=True")
                return  # ← silent exit

            # Legacy session-based pause check
            session = await _get_session(db, user_phone)
            if session.get("paused") is True and not is_new_conversation:
                paused_reason = session.get("paused_reason", "unknown")
                logger.info(f"⏸️ Session paused | Reason: {paused_reason}")
                return  # ← silent exit
        else:
            logger.info("💰 Financial Intent detected! Bypassing Human Gatekeeper.")

        # ==============================================================
        # STEP 6: AI LOGIC
        # ==============================================================
        cerebro_ia = CerebroIA(config_loader)
        vision_service = VisionService(db)
        audio_service = AudioService(config_loader)

        response_text = "Lo siento, no entendí ese mensaje."
        sentiment = "NEUTRAL"

        # --- 6a. Sentiment check (REMOVED due to false positives) ---
        # Sentiment analysis was triggering "ANGRY" too easily during initial greetings.
        # We now rely on explicit intent or AI function calling for handoffs.
        if msg_type == "text":
            pass # Skip sentiment-based auto-pause


        # Double-check session pause (may have been updated by sentiment)
        session = await _get_session(db, user_phone)
        if session.get("status") == "PAUSED" and not is_new_conversation:
            logger.info(f"⏸️ Session paused for {user_phone}. Ignoring message.")
            return

        # --- 6b. Route by message type ---
        if msg_type == "text":
            text = msg_data["text"]

            # Unique task ID for debounce tracking
            task_id = f"{message_id}_{time.time()}"

            # Add to buffer and check if first message in burst
            is_first_message = False
            if message_buffer:
                is_first_message = await message_buffer.add_message(
                    user_phone, text, task_id
                )

            # Typing indicator for first message
            if is_first_message:
                logger.info(
                    f"⌨️ Sending typing indicator for first message from {user_phone}"
                )
                await _send_whatsapp_status(user_phone, "typing")

            # Debounce — wait to accumulate fragmented messages
            if message_buffer:
                debounce_time = message_buffer.debounce_seconds
                
                # OPTIMIZATION: Instant reply for first message
                if is_new_conversation:
                    debounce_time = 0.0
                    logger.info("🚀 Skipping debounce for first message.")

                # If financial intent detected, reduce debounce to feel more responsive to hot leads
                if is_financial_intent:
                    debounce_time = 1.0
                    logger.info("💰 Financial intent: reducing debounce.")

                if debounce_time > 0:
                    logger.info(
                        f"⏳ Starting {debounce_time}s debounce "
                        f"for {user_phone} (task: {task_id})"
                    )
                    await asyncio.sleep(debounce_time)

                if not message_buffer.is_task_active(user_phone, task_id):
                    logger.info(
                        f"⏭️ Task {task_id} superseded for {user_phone}, "
                        f"aborting silently"
                    )
                    return

                aggregated_text = await message_buffer.get_aggregated_message(
                    user_phone
                )

                if not aggregated_text:
                    logger.warning(
                        f"⚠️ Empty aggregated message for {user_phone}, aborting"
                    )
                    await message_buffer.clear_buffer(user_phone)
                    return

                logger.info(
                    f"🔀 Processing aggregated message for {user_phone} | "
                    f"Length: {len(aggregated_text)} chars | "
                    f"Task: {task_id}"
                )
            else:
                # No buffer — use original text directly
                aggregated_text = text
                logger.info(
                    "⚠️ MessageBuffer not available, processing message directly"
                )

            # Route aggregated text through AI / sales / finance
            # FORCE FINANCIAL if identified in Check B
            if is_financial_intent:
                logger.info("💰 STRICT ROUTING: Forcing Financial Flow.")
                # We can call the survey starter directly or pass a flag.
                # Since we haven't seen _route_message source, let's inject a prefix that _route_message hopefully respects 
                # OR call the handling logic directly if possible.
                # However, to be safe and clean, let's assume _route_message handles "magic" or we pass the flag.
                # Let's pass 'is_financial_intent' to _route_message.
                # I'll need to update _route_message signature in a separate step if I do that.
                # Alternative: Call logic directly.
                # "EXECUTE: Call start_financial_survey." -> This implies a specific function.
                # I'll assume standard routing for now but with the intent flag likely forcing it if I could.
                # For now, I will modify the call to _route_message to pass the intent explicitly IF I knew the signature changes.
                # I will try to update _route_message in the next step.
                # For this step, I'm just updating the surrounding logic to use the variable I defined.
                pass 

            response_text = await _route_message(
                aggregated_text,
                config_loader,
                motor_financiero,
                motor_ventas,
                cerebro_ia,
                db,
                user_phone,
                prospect_data,
                force_financial=is_financial_intent # Passing new arg
            )

            # Handle AI-triggered human handoff
            if response_text.startswith("HANDOFF_TRIGGERED:"):
                reason = (
                    response_text.split(":", 1)[1]
                    if ":" in response_text
                    else "unknown"
                )
                logger.warning(
                    f"🚨 Human handoff triggered for {user_phone} | "
                    f"Reason: {reason}"
                )

                if memory_service:
                    try:
                        memory_service.set_human_help_status(user_phone, True)
                        logger.info(
                            f"✅ Set human_help_requested=True for {user_phone}"
                        )
                    except Exception as e:
                        logger.error(
                            f"❌ Failed to set human_help_status: {str(e)}"
                        )

                await _update_session(
                    db,
                    user_phone,
                    {
                        "paused": True,
                        "paused_reason": "human_handoff",
                        "handoff_reason": reason,
                        "status": "PAUSED",
                    },
                )

                await notification_service.notify_human_handoff(user_phone, reason)
                response_text = "Entendido, te paso con un asesor humano."

            # Clear buffer after successful processing
            if message_buffer:
                await message_buffer.clear_buffer(user_phone)

        elif msg_type == "image":
            logger.info("📷 Image received")
            media_id = msg_data["media_id"]
            mime_type = msg_data["mime_type"]
            image_bytes = await _download_media(media_id)
            if image_bytes:
                response_text = await vision_service.analyze_image(
                    image_bytes, mime_type, user_phone
                )
            else:
                response_text = "No pude descargar la imagen. 😢"

        elif msg_type == "audio":
            logger.info("🎤 Audio received")
            media_id = msg_data["media_id"]
            mime_type = msg_data["mime_type"]
            audio_bytes = await _download_media(media_id)
            if audio_bytes:
                response_text = await audio_service.process_audio(
                    audio_bytes, mime_type
                )
            else:
                response_text = "No pude descargar el audio. 😢"

        else:
            response_text = "Aún no soporto este tipo de mensaje. 😅"

        # ==============================================================
        # STEP 7: SEND RESPONSE WITH TYPING ANIMATION
        # ==============================================================
        delay = min(len(response_text) * 0.04, 5.0)
        
        # OPTIMIZATION: Instant reply for first message
        if is_new_conversation:
            delay = 0.0
            logger.info("🚀 Skipping typing delay for first message.")

        logger.info(
            f"⏳ Artificial Latency: {delay:.2f}s "
            f"(response: {len(response_text)} chars)"
        )

        elapsed = 0.0
        typing_interval = 5.0
        while elapsed < delay:
            await _send_whatsapp_status(user_phone, "typing")
            sleep_time = min(typing_interval, delay - elapsed)
            await asyncio.sleep(sleep_time)
            elapsed += sleep_time

        await _send_whatsapp_message(user_phone, response_text)

        # ==============================================================
        # STEP 8: POST-PROCESSING — CRM SUMMARY UPDATE
        # ==============================================================
        if msg_type == "text" and not response_text.startswith("HANDOFF_TRIGGERED:"):
            if memory_service:
                try:
                    aggregated_text_for_summary = locals().get(
                        "aggregated_text", msg_data.get("text", "")
                    )
                    conversation = (
                        f"Usuario: {aggregated_text_for_summary}\n"
                        f"Sebas: {response_text}"
                    )
                    summary_data = cerebro_ia.generate_summary(conversation)
                    await memory_service.update_prospect_summary(
                        user_phone,
                        summary_data.get("summary", ""),
                        summary_data.get("extracted", {}),
                    )
                    logger.info(f"💾 Prospect summary updated for {user_phone}")
                except Exception as e:
                    logger.error(
                        f"⚠️ Failed to update prospect summary: {str(e)}"
                    )

        # --- Audit log ---
        if msg_type == "text":
            user_input = locals().get(
                "aggregated_text", msg_data.get("text", "[Unknown]")
            )
        else:
            user_input = "[Media]"
        await audit_service.log_interaction(
            user_phone, user_input, response_text, sentiment
        )

        logger.info(f"✅ Response sent to {user_phone}")

    except Exception as e:
        logger.error(
            f"❌ Error in background processing: {str(e)}", exc_info=True
        )
    finally:
        # Always remove from idempotency cache to avoid memory leaks
        if message_id in processing_messages:
            processing_messages.remove(message_id)
            logger.debug(f"🗑️  Removed {message_id} from processing cache")


# ============================================================================
# HELPER FUNCTIONS — MESSAGE VALIDATION & EXTRACTION
# ============================================================================

def _is_valid_message(payload: Dict[str, Any]) -> bool:
    """
    Check whether the webhook payload contains at least one message.

    Safely navigates the nested Meta payload structure.
    Returns False (fail-closed) on any parsing error.
    """
    try:
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        return len(messages) > 0
    except Exception:
        return False


def _extract_message_data(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract structured message data from a WhatsApp webhook payload.

    Supports ``text``, ``image``, and ``audio`` message types.
    Returns ``None`` on extraction failure (fail-closed).
    """
    try:
        msg = payload["entry"][0]["changes"][0]["value"]["messages"][0]
        msg_type = msg["type"]

        data = {
            "from": msg["from"],
            "id": msg["id"],
            "timestamp": msg["timestamp"],
            "type": msg_type,
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
# HELPER FUNCTIONS — MEDIA DOWNLOAD
# ============================================================================

async def _download_media(media_id: str) -> Optional[bytes]:
    """
    Two-step media download from WhatsApp Cloud API.

    1. GET media URL by ``media_id``
    2. GET binary content from the resolved URL

    Returns ``None`` on any failure.
    """
    try:
        url = f"https://graph.facebook.com/v18.0/{media_id}"
        headers = {"Authorization": f"Bearer {settings.whatsapp_token}"}

        async with httpx.AsyncClient() as client:
            # Step 1 — resolve media URL
            r1 = await client.get(url, headers=headers)
            r1.raise_for_status()
            media_url = r1.json().get("url")

            # Step 2 — download bytes
            r2 = await client.get(media_url, headers=headers)
            r2.raise_for_status()
            return r2.content

    except Exception as e:
        logger.error(f"❌ Download failed: {e}")
        return None


# ============================================================================
# HELPER FUNCTIONS — SESSION MANAGEMENT
# ============================================================================

async def _get_session(db_client: Any, phone: str) -> Dict[str, Any]:
    """
    Retrieve user session from Firestore.

    Path: ``mensajeria/whatsapp/sesiones/{phone}``

    Falls back to a default ``IDLE`` session on any error (fail-closed).
    """
    try:
        doc_ref = (
            db_client.collection("mensajeria")
            .document("whatsapp")
            .collection("sesiones")
            .document(phone)
        )
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        return {
            "status": "IDLE",
            "answers": {},
            "last_interaction": datetime.now(timezone.utc),
        }
    except Exception as e:
        logger.error(f"Error getting session: {e}")
        return {
            "status": "IDLE",
            "answers": {},
            "last_interaction": datetime.now(timezone.utc),
        }


async def _update_session(
    db_client: Any, phone: str, data: Dict[str, Any]
) -> None:
    """
    Merge-update user session in Firestore.

    Automatically stamps ``last_interaction`` with the current UTC time.
    """
    try:
        doc_ref = (
            db_client.collection("mensajeria")
            .document("whatsapp")
            .collection("sesiones")
            .document(phone)
        )
        data["last_interaction"] = datetime.now(timezone.utc)
        doc_ref.set(data, merge=True)
    except Exception as e:
        logger.error(f"Error updating session: {e}")


# ============================================================================
# HELPER FUNCTIONS — FINANCIAL SURVEY FLOW
# ============================================================================

async def _handle_survey_flow(
    db_client: Any,
    phone: str,
    message_text: str,
    current_session: Dict[str, Any],
    motor_finanzas: MotorFinanciero,
) -> str:
    """
    Step-through financial survey (contract → credit history → income).

    Each invocation advances the user one step. When all three answers
    are collected the financial profile is evaluated and a recommendation
    is returned.
    """
    status = current_session.get("status", "IDLE")
    answers = current_session.get("answers", {})

    if status == "SURVEY_STEP_1_LABOR":
        answers["labor_type"] = message_text
        await _update_session(
            db_client, phone, {"status": "SURVEY_STEP_2_INCOME", "answers": answers}
        )
        return (
            "2️⃣ ¿Cuáles son tus ingresos mensuales totales? "
            "(Escribe solo el número, sin puntos. Ej: 1500000)"
        )

    elif status == "SURVEY_STEP_2_INCOME":
        # Normalize income (remove non-digits)
        clean_income = "".join(filter(str.isdigit, message_text))
        final_income = int(clean_income) if clean_income else 0
        answers["income"] = final_income
        
        await _update_session(
            db_client, phone, {"status": "SURVEY_STEP_3_HISTORY", "answers": answers}
        )
        return (
            "3️⃣ ¿Cómo ha sido tu comportamiento con créditos anteriores? "
            "(Ej: Excelente, Reportado, Nunca he tenido)"
        )

    elif status == "SURVEY_STEP_3_HISTORY":
        answers["payment_habit"] = message_text
        # We also save as credit_history for completeness if needed, but payment_habit is the key
        answers["credit_history"] = message_text
        
        await _update_session(
            db_client, phone, {"status": "SURVEY_STEP_4_GAS", "answers": answers}
        )
        return "4️⃣ ¿Tienes servicio de Gas Natural a tu nombre? (Responde Sí o No)"

    elif status == "SURVEY_STEP_4_GAS":
        # Boolean detection
        text_lower = message_text.lower()
        has_gas = any(w in text_lower for w in ["si", "sí", "yes", "claro", "tengo"])
        answers["has_gas_natural"] = has_gas
        
        await _update_session(
            db_client, phone, {"status": "SURVEY_STEP_5_POSTPAID", "answers": answers}
        )
        return "5️⃣ ¿Tienes un plan de celular Postpago? (Responde Sí o No)"

    elif status == "SURVEY_STEP_5_POSTPAID":
        # Boolean detection
        text_lower = message_text.lower()
        is_postpaid = any(w in text_lower for w in ["si", "sí", "yes", "claro", "tengo"])
        answers["phone_plan"] = "Postpago" if is_postpaid else "Prepago"
        
        # --- FINALIZE & EVALUATE ---
        
        # 1. Build Profile
        profile = {
            "labor_type": answers.get("labor_type"),
            "income": answers.get("income"),
            "payment_habit": answers.get("payment_habit"),
            "credit_history": answers.get("credit_history"),
            "has_gas_natural": answers.get("has_gas_natural"),
            "phone_plan": answers.get("phone_plan")
        }
        
        # 2. Call FinancialService
        try:
            decision = financial_service.evaluate_profile(profile)
            strategy = decision["strategy"]
            action = decision["action_type"]
            payload = decision["payload"]
        except Exception as e:
            logger.error(f"❌ Error evaluating profile: {e}")
            strategy = "HUMAN"
            action = "HANDOFF"
            payload = "https://wa.me/573000000000"

        # 3. Reset Session
        await _update_session(
            db_client, phone, {"status": "IDLE", "answers": {}}
        )

        # 4. Construct Response based on Strategy
        if action == "REDIRECT":
            # BANCO or FINTECH
            entity_name = "Banco de Bogotá" if strategy == "BANCO" else "CrediOrbe"
            return (
                f"¡Listo! Según tu perfil, tu mejor opción es con **{entity_name}**.\n\n"
                f"Dale clic aquí para la aprobación inmediata: {payload}"
            )
            
        elif action == "CAPTURE_DATA":
            # BRILLA
            return (
                "¡Te tengo buenas noticias! Podemos intentarlo por el cupo **Brilla**.\n\n"
                "Por favor envíame una foto de tu **recibo de gas** y tu **cédula** para avanzar."
            )
            
        else:
            # HANDOFF / HUMAN
            # Trigger handoff mode via keyword that the main loop detects? 
            # Or just send the message and let the user reply to trigger handoff?
            # The prompt says: "Tu caso es especial..." 
            # We should probably explicitly set human help status here or just return the text.
            # Returning text is safer.
            return (
                "Tu caso es especial. Te voy a pasar con un asesor humano para que lo revise personalmente."
            )

    return "Algo salió mal. ¿Empezamos de nuevo?"


# ============================================================================
# HELPER FUNCTIONS — MESSAGE ROUTING
# ============================================================================

async def _route_message(
    message_text: str,
    config_loader_inst,
    motor_finanzas: MotorFinanciero,
    motor_ventas_inst: MotorVentas,
    cerebro_ia: CerebroIA,
    db_client: Any,
    user_phone: str,
    prospect_data: Optional[Dict[str, Any]] = None,
    force_financial: bool = False,
) -> str:
    """
    Route user message to the correct engine.

    Priority: Active Survey > Finance > Sales > AI Fallback.
    """
    # Check session state
    session = await _get_session(db_client, user_phone)
    status = session.get("status", "IDLE")

    # 1. Active survey takes priority
    if status.startswith("SURVEY_"):
        return await _handle_survey_flow(
            db_client, user_phone, message_text, session, motor_finanzas
        )

    # 2. Normal routing (IDLE)
    routing_rules = config_loader_inst.get_routing_rules()
    financial_keywords = routing_rules.get("financial_keywords", []) + [
        "credito", "crédito", "fiado", "cuotas", "financiar", "estudio", "valor"
    ]
    sales_keywords = routing_rules.get("sales_keywords", [])

    # Finance intent
    if force_financial or _has_financial_intent(message_text, financial_keywords):
        logger.info("💰 Starting Financial Survey")
        await _update_session(
            db_client,
            user_phone,
            {
                "status": "SURVEY_STEP_1_LABOR",
                "answers": {},
                "start_time": datetime.now(timezone.utc),
            },
        )
        return (
            "¡Con gusto! Para buscarte la opción de crédito con la cuota más bajita, "
            "necesito hacerte 5 preguntas rápidas. ⚡\n\n"
            "1️⃣ ¿Qué tipo de contrato laboral tienes?\n"
            "(Ej: Indefinido, Obra labor, Independiente, Informal)"
        )

    # Sales intent
    message_lower = message_text.lower()
    if any(keyword in message_lower for keyword in sales_keywords):
        return motor_ventas_inst.buscar_moto(message_text)

    # AI fallback with memory context
    context = session.get("summary", "")
    return cerebro_ia.pensar_respuesta(
        message_text, context=context, prospect_data=prospect_data
    )


def _has_financial_intent(text: str, keywords: list) -> bool:
    """
    Keyword-based financial intent detector.

    Returns ``True`` if any keyword is found in the lowercased text.
    """
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in keywords)


# ============================================================================
# HELPER FUNCTIONS — WHATSAPP API
# ============================================================================

async def _send_whatsapp_message(to_phone: str, message_text: str) -> None:
    """
    Send a text message via WhatsApp Cloud API.

    Uses a 5-second hard timeout and disabled connection pooling
    to guarantee requests don't hang in Cloud Run's lifecycle.
    """
    try:
        phone_number_id = settings.phone_number_id
        if not phone_number_id or not settings.whatsapp_token:
            logger.error(
                "🔥 CRITICAL: WHATSAPP_TOKEN or PHONE_NUMBER_ID is "
                "missing/empty. Message NOT sent."
            )
            return

        # Ensure international format for sending
        from app.core.utils import PhoneNormalizer
        to_phone_intl = PhoneNormalizer.to_international(to_phone)

        url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {settings.whatsapp_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone_intl,
            "type": "text",
            "text": {"body": message_text},
        }

        logger.info(f"📤 Sending message to {to_phone_intl} (raw: {to_phone}) via WhatsApp API")

        # Disable keep-alive — Cloud Run containers recycle aggressively
        limits = httpx.Limits(
            max_connections=1, max_keepalive_connections=0
        )

        async with httpx.AsyncClient(limits=limits) as client:
            response = await client.post(
                url,
                json=payload,
                headers=headers,
                timeout=5.0,  # Hard 5s timeout
            )
            response.raise_for_status()

        logger.info(f"✅ Message sent successfully to {to_phone}")

    except httpx.HTTPStatusError as e:
        logger.error(
            f"❌ WhatsApp API error: {e.response.status_code} - "
            f"{e.response.text}"
        )
        raise
    except httpx.TimeoutException as e:
        logger.error(f"⏱️ TIMEOUT: Request exceeded 5s limit: {repr(e)}")
        raise
    except Exception as e:
        logger.error(f"❌ Error sending WhatsApp message: {repr(e)}")
        raise


async def _send_whatsapp_status(to_phone: str, status: str = "typing") -> None:
    """
    Simulate typing indicator for the user.

    WhatsApp Cloud API lacks a native typing indicator endpoint,
    so this is a no-op placeholder used by the keep-alive delay loop.
    """
    logger.debug(f"⏳ Processing for {to_phone} (keep-alive loop active)")
    pass
