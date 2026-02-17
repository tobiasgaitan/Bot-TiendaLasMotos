"""
WhatsApp Webhook Router (Self-Contained Fix)
============================================
Handles Meta WhatsApp webhook verification and message reception.
Completely self-contained to avoid ModuleNotFoundError.
"""

import logging
import httpx
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Query, HTTPException, BackgroundTasks
from google.cloud import firestore

from app.core.config import settings
from app.core.config_loader import ConfigLoader
from app.core.security import get_firebase_credentials_object

# --- SERVICE CLASSES (INSTANTIATED LOCALLY) ---
from app.services.finance import MotorFinanciero
from app.services.ai_brain import CerebroIA
from app.services.vision_service import VisionService
from app.services.audio_service import AudioService
from app.services.catalog_service import CatalogService # Local instantiation class
from app.services.survey_service import survey_service # Singleton

# --- MEMORY SERVICE (SINGLETON) ---
from app.services.memory_service import memory_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["WhatsApp"])

# ============================================================================
# STATE & INITIALIZATION
# ============================================================================

# Global variables initialized to None
db = None
config_loader = None
motor_financiero = None
catalog_service_local = None

def _ensure_services():
    """Lazy initialization of services"""
    global db, config_loader, motor_financiero, catalog_service_local
    
    # 1. Firestore
    if not db:
        try:
            creds = get_firebase_credentials_object()
            db = firestore.Client(credentials=creds, project=settings.gcp_project_id)
            logger.info(f"✅ Database connected to project: {settings.gcp_project_id}")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Firestore: {e}", exc_info=True)
            return # Cannot proceed

    # 2. Config Loader
    if db and not config_loader:
        try:
            config_loader = ConfigLoader(db)
        except Exception: pass

    # 3. Motor Financiero
    if db and not motor_financiero:
         try:
            motor_financiero = MotorFinanciero(db, config_loader)
         except Exception: pass

    # 4. Catalog Service
    if db and not catalog_service_local:
        try:
            catalog_service_local = CatalogService()
            catalog_service_local.initialize(db)
            logger.info("✅ CatalogService initialized")
        except Exception as e:
             logger.error(f"❌ Failed to initialize CatalogService: {e}")

# ============================================================================
# WEBHOOK ENDPOINTS
# ============================================================================

@router.get("")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
) -> str:
    """Verificación del Webhook de Meta"""
    if hub_mode == "subscribe" and hub_verify_token == settings.webhook_verify_token:
        logger.info("✅ Webhook verificado correctamente.")
        return hub_challenge
    else:
        logger.error("❌ Token de verificación incorrecto.")
        raise HTTPException(status_code=403, detail="Forbidden")

@router.post("")
async def webhook_handler(
    request: Request,
    background_tasks: BackgroundTasks,
) -> Dict[str, str]:
    """Recepción de mensajes de WhatsApp"""
    try:
        payload = await request.json()
        
        # Validación básica de estructura
        if not _is_valid_message(payload):
            return {"status": "ignored"}
            
        msg_data = _extract_message_data(payload)
        if not msg_data:
            return {"status": "ignored"}

        # Procesamiento en segundo plano
        background_tasks.add_task(_handle_message_background, msg_data)
        return {"status": "received"}
        
    except Exception as e:
        logger.error(f"Error procesando webhook: {e}")
        return {"status": "error"}


# ============================================================================
# BACKGROUND LOGIC
# ============================================================================

async def _handle_message_background(msg_data: Dict[str, Any]) -> None:
    """Lógica principal del bot (Procesamiento Asíncrono)"""
    # Ensure services are initialized before proceeding
    _ensure_services()

    try:
        # 1. Extracción de Datos
        from app.core.utils import PhoneNormalizer
        
        raw_phone = msg_data["from"]
        user_phone = PhoneNormalizer.normalize(raw_phone)
        msg_type = msg_data["type"].lower()
        
        # DEBUG LOG for Image Troubleshooting
        logger.info(f"🕵️ DEBUG: Received message from {user_phone} | Type: '{msg_type}' | Keys: {list(msg_data.keys())}")
        
        message_body = ""
        
        if msg_type == "text":
            message_body = msg_data.get("text", "").strip()
            
        elif msg_type in ["image", "document"]:
            logger.info(f"📸 Media detected from {user_phone} (Type: {msg_type}). Processing immediately...")
            await _mark_message_as_read(msg_data["id"])
            
            # Initialize Vision Service locally if needed
            if db:
                try:
                    vision_service = VisionService(db)
                    
                    # Robust extraction for Image OR Document
                    media_data = {}
                    if msg_type == "image":
                        media_data = msg_data.get("image", {})
                    elif msg_type == "document":
                        media_data = msg_data.get("document", {})
                    
                    # Fallback to root keys
                    media_id = media_data.get("id") or msg_data.get("media_id")
                    mime_type = media_data.get("mime_type") or msg_data.get("mime_type")
                    caption = media_data.get("caption", "")
                    
                    # FILTER: If it's a document, ensure it's an image
                    if msg_type == "document" and not mime_type.startswith("image/"):
                        logger.info(f"📄 Document ignored (MIME: {mime_type}). Not an image.")
                        return 
                    
                    if not media_id:
                        logger.error("❌ Failed to extract media_id from message")
                        await _send_whatsapp_message(user_phone, "No pude procesar el archivo. 😢")
                        return

                    image_bytes = await _download_media(media_id)
                    if image_bytes:
                        logger.info(f"📥 Media downloaded ({len(image_bytes)} bytes). Analyzing with caption: '{caption}'...")
                        response_text = await vision_service.analyze_image(image_bytes, mime_type, user_phone, caption=caption)
                        logger.info(f"🧠 Vision response: {response_text}")
                        
                        if response_text:
                            await _send_whatsapp_message(user_phone, response_text)
                        else:
                            await _send_whatsapp_message(user_phone, "¡Uff, qué nave! 🏍️ Pero no alcanzo a ver bien los detalles. ¿Me cuentas qué modelo es?")
                    else:
                        await _send_whatsapp_message(user_phone, "No pude descargar el archivo. Intenta de nuevo.")
                except Exception as e:
                    logger.error(f"❌ Error processing media: {e}")
                    await _send_whatsapp_message(user_phone, "Tuve un problema viendo el archivo. ¿Me cuentas qué es? 😅")
            
            return  # EARLY EXIT: Stop processing here
            
        # Marcar como leído locally
        await _mark_message_as_read(msg_data["id"]) 

        # 1.5 Save User Message to History (PERSISTENCE FIX)
        if memory_service and msg_type == "text":
            # Optimistic save (don't block too long)
            await memory_service.save_message(user_phone, "user", message_body)

        # --- LÓGICA DE RESET NUCLEAR (PRIORIDAD 0) ---
        # FIX: Ensure it is strict text match
        if msg_type == "text" and message_body.strip() == "/reset":
            logger.warning(f"☢️ NUCLEAR RESET TRIGGERED for {user_phone}")
            
            # Variantes de ID
            ids_to_purge = list(set([user_phone, raw_phone, user_phone.replace("57", "", 1)]))
            deleted_count = 0
            
            collections_to_check = ["sessions", "prospectos"]
            
            if db:
                for pid in ids_to_purge:
                    # 1. Main Collections
                    for col in collections_to_check:
                        try:
                            doc_ref = db.collection(col).document(pid)
                            if doc_ref.get().exists:
                                doc_ref.delete()
                                deleted_count += 1
                                logger.info(f"🗑️ Deleted {col}/{pid}")
                        except Exception: pass
                    
                    # 2. Nested Session Collection (mensajeria/whatsapp/sesiones)
                    try:
                        doc_ref_active = db.collection("mensajeria").document("whatsapp").collection("sesiones").document(pid)
                        if doc_ref_active.get().exists:
                            doc_ref_active.delete()
                            deleted_count += 1
                            logger.info(f"🗑️ Deleted active session {pid}")
                        
                        # 3. Clean history as well
                        history_ref = db.collection("mensajeria").document("whatsapp").collection("sesiones").document(pid).collection("historial")
                        formatted_docs = history_ref.limit(50).stream() 
                        for hdoc in formatted_docs:
                            hdoc.reference.delete()
                            
                    except Exception: pass

            # Always send confirmation
            await _send_whatsapp_message(user_phone, "☢️ RESET COMPLETADO. Memoria limpia. Escribe 'Hola' para iniciar.")
            return
        # --- FIN RESET NUCLEAR ---

        # 2. Gestión de Sesión
        prospect_data = None
        current_history = []
        
        if memory_service:
            # Create if missing (ensure prospect exists)
            memory_service.create_prospect_if_missing(user_phone)
            # Update timestamp
            memory_service.update_last_interaction(user_phone)
            # Get data
            prospect_data = memory_service.get_prospect_data(user_phone)
            
            # LOAD HISTORY for Context (CONTEXT FIX)
            current_history = await memory_service.get_chat_history(user_phone, limit=10)
            
            # GREETING BYPASS LOGIC (Time-Based)
            skip_greeting = False
            if current_history:
                last_msg = current_history[-1]
                last_ts = last_msg.get("timestamp")
                
                # Normalize timestamp to datetime
                last_time = None
                if hasattr(last_ts, 'timestamp'): # Firestore Timestamp
                    last_time = datetime.fromtimestamp(last_ts.timestamp(), tz=timezone.utc)
                elif isinstance(last_ts, datetime):
                    last_time = last_ts
                elif isinstance(last_ts, str): # String ISO format fallback
                    try:
                        last_time = datetime.fromisoformat(last_ts.replace('Z', '+00:00'))
                    except: pass
                
                if last_time:
                    # Calculate duration since last message
                    now = datetime.now(timezone.utc)
                    # Ensure last_time is timezone aware for subtraction
                    if last_time.tzinfo is None:
                        last_time = last_time.replace(tzinfo=timezone.utc)
                        
                    delta = now - last_time
                    diff_seconds = delta.total_seconds()
                    
                    # If less than 2 hours (7200s), skip greeting
                    if diff_seconds < 7200:
                        skip_greeting = True
                        logger.info(f"⏳ Recent conversation detected ({int(diff_seconds)}s ago). Skipping greeting.")

            response_text = cerebro_ia.pensar_respuesta(
                message_body, 
                context=context, 
                prospect_data=prospect_data,
                history=current_history,
                skip_greeting=skip_greeting
            )
            
        elif msg_type == "audio":
            media_id = msg_data.get("media_id")
            mime_type = msg_data.get("mime_type")
            audio_bytes = await _download_media(media_id)
            if audio_bytes:
                response_text = await audio_service.process_audio(audio_bytes, mime_type)
            else:
                response_text = "No pude descargar el audio. 😢"
            
        if response_text:
            # Check for AI Handoff
            if response_text.startswith("HANDOFF_TRIGGERED"):
                if memory_service:
                    memory_service.set_human_help_status(user_phone, True)
                await _send_whatsapp_message(user_phone, "Entendido. Buscando un humano... 🔍")
                try:
                    from app.services.notification_service import notification_service
                    await notification_service.notify_human_handoff(user_phone, "ai_trigger")
                except ImportError: pass
            else:
                await _send_whatsapp_message(user_phone, response_text)
                
                # Save Bot Response to History (PERSISTENCE FIX)
                if memory_service:
                    await memory_service.save_message(user_phone, "model", response_text)

                # Update Summary
                if msg_type == "text" and memory_service:
                    try:
                        conversation = f"User: {message_body}\nBot: {response_text}"
                        summary_data = cerebro_ia.generate_summary(conversation)
                        await memory_service.update_prospect_summary(
                            user_phone, 
                            summary_data.get("summary", ""), 
                            summary_data.get("extracted", {})
                        )
                    except Exception as e:
                        logger.warning(f"Failed to update summary: {e}")

    except Exception as e:
        logger.error(f"🔥 Error CRÍTICO en handle_message: {e}", exc_info=True)


# ============================================================================
# LOCAL HELPERS (Defined here to avoid missing dependency errors)
# ============================================================================

def _is_valid_message(payload: Dict[str, Any]) -> bool:
    try:
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        return len(messages) > 0
    except:
        return False

def _extract_message_data(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
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
            image_obj = msg["image"]
            data["image"] = image_obj
            data["media_id"] = image_obj.get("id")
            data["mime_type"] = image_obj.get("mime_type")
            data["caption"] = image_obj.get("caption", "")
        elif msg_type == "document":
            doc_obj = msg["document"]
            data["document"] = doc_obj
            data["media_id"] = doc_obj.get("id")
            data["mime_type"] = doc_obj.get("mime_type")
            data["caption"] = doc_obj.get("caption", "")
            data["filename"] = doc_obj.get("filename", "")
        elif msg_type == "audio":
            data["media_id"] = msg["audio"]["id"]
            data["mime_type"] = msg["audio"]["mime_type"]
        return data
    except:
        return None

async def _send_whatsapp_message(to_phone: str, message_text: str) -> None:
    """Send WhatsApp message via Cloud API."""
    try:
        phone_number_id = settings.phone_number_id
        if not phone_number_id or not settings.whatsapp_token:
            logger.error("Missing WhatsApp credentials")
            return

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
        
        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload, headers=headers, timeout=10.0)
            
    except Exception as e:
        logger.error(f"Error sending message: {e}")

async def _mark_message_as_read(message_id: str) -> None:
    """Mark WhatsApp message as read."""
    try:
        phone_number_id = settings.phone_number_id
        if not phone_number_id or not settings.whatsapp_token:
            return

        url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {settings.whatsapp_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
        
        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload, headers=headers, timeout=5.0)
            
    except Exception as e:
        logger.error(f"Error marking message as read: {e}")

async def _download_media(media_id: str) -> Optional[bytes]:
    """Download media from WhatsApp."""
    try:
        url = f"https://graph.facebook.com/v18.0/{media_id}"
        headers = {"Authorization": f"Bearer {settings.whatsapp_token}"}
        
        async with httpx.AsyncClient() as client:
            r1 = await client.get(url, headers=headers)
            if r1.status_code != 200: return None
            media_url = r1.json().get("url")
            
            r2 = await client.get(media_url, headers=headers)
            if r2.status_code != 200: return None
            return r2.content
    except Exception as e:
        logger.error(f"Error downloading media: {e}")
        return None

async def _get_session(db_client, phone) -> Dict[str, Any]:
    try:
        if not db_client: return {}
        ref = db_client.collection("mensajeria").document("whatsapp").collection("sesiones").document(phone)
        doc = ref.get()
        if doc.exists:
            return doc.to_dict()
        return {"status": "IDLE", "answers": {}}
    except:
        return {"status": "IDLE"}
