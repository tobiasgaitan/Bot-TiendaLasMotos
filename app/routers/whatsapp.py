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

# --- SERVICE CLASSES (INSTANTIATED LOCALLY) ---
from app.services.finance import MotorFinanciero
from app.services.ai_brain import CerebroIA
from app.services.vision_service import VisionService
from app.services.audio_service import AudioService
from app.services.survey_service import survey_service # Singleton

# --- MEMORY SERVICE (SINGLETON) ---
from app.services.memory_service import memory_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["WhatsApp"])

# ============================================================================
# LOCAL DEPENDENCIES (To avoid import errors)
# ============================================================================

# Initialize dependencies locally for this router to ensure availability
db = None
try:
    db = firestore.Client()
    logger.info("✅ Firestore client initialized in whatsapp router")
except Exception as e:
    logger.error(f"❌ Failed to initialize Firestore: {e}", exc_info=True)

# Initialize ConfigLoader (needed for AI)
config_loader = None
if db:
    try:
        config_loader = ConfigLoader(db)
    except Exception:
        pass

# Initialize MotorFinanciero (Needed for survey)
motor_financiero = None
if db:
    try:
        motor_financiero = MotorFinanciero(db, config_loader)
    except Exception:
        pass


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

        # Use processing_messages set if desired, but kept simple here
        
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
    try:
        # 1. Extracción de Datos
        from app.core.utils import PhoneNormalizer
        
        raw_phone = msg_data["from"]
        user_phone = PhoneNormalizer.normalize(raw_phone)
        msg_type = msg_data["type"]
        message_body = ""
        
        if msg_type == "text":
            message_body = msg_data.get("text", "").strip()
            
        # Marcar como leído locally
        await _mark_message_as_read(msg_data["id"]) 

        # --- LÓGICA DE RESET NUCLEAR (PRIORIDAD 0) ---
        if message_body.lower() == "/reset":
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
                    except Exception: pass

            if deleted_count > 0:
                await _send_whatsapp_message(user_phone, "☢️ SISTEMA REINICIADO. Memoria borrada. Escribe 'Hola' para iniciar.")
            return
        # --- FIN RESET NUCLEAR ---

        # 2. Gestión de Sesión
        prospect_data = None
        if memory_service:
            # Create if missing (ensure prospect exists)
            memory_service.create_prospect_if_missing(user_phone)
            # Update timestamp
            memory_service.update_last_interaction(user_phone)
            # Get data
            prospect_data = memory_service.get_prospect_data(user_phone)
        
        # Human Gatekeeper
        if prospect_data and prospect_data.get('human_help_requested', False):
            # logger.info(f"⏸️ Ignored message from {user_phone} (Human Help Requested)")
            return

        # 3. Encuesta Financiera (Router Inteligente)
        # Initialize MotorFinanciero locally (Lazy Loading)
        motor_financiero = None
        if db:
            try:
                motor_financiero = MotorFinanciero(db, config_loader)
            except Exception: pass

        session = await _get_session(db, user_phone)
        
        # KEYWORDS que activan el SurveyService (Modo Estricto)
        KEYWORDS_FINANCIERAS = ["credito", "crédito", "financiar", "cuotas", "simular", "reportado", "viabilidad"]
        
        tiene_sesion_activa = session.get("status") != "IDLE"
        es_mensaje_financiero = any(k in message_body.lower() for k in KEYWORDS_FINANCIERAS)

        # Regla: Solo pasar a Encuesta si hay sesión activa O intención financiera explícita
        if msg_type == "text" and (tiene_sesion_activa or es_mensaje_financiero):
            # Using singleton survey_service
            survey_response = await survey_service.handle_survey_step(
                db_client=db,
                phone=user_phone,
                message_text=message_body,
                current_session=session,
                motor_finanzas=motor_financiero
            )
            
            if survey_response:
                if survey_response.startswith("HANDOFF_TRIGGERED"):
                    if memory_service:
                        memory_service.set_human_help_status(user_phone, True)
                    await _send_whatsapp_message(user_phone, "Entendido. Un asesor humano revisará tu caso. 👨💻")
                    # No notification here to keep it simple and imported-free, or import notification_service if needed.
                    try:
                        from app.services.notification_service import notification_service
                        await notification_service.notify_human_handoff(user_phone, "survey_fallback")
                    except ImportError:
                        pass
                    return
                
                await _send_whatsapp_message(user_phone, survey_response)
                return

        # 4. Cerebro IA (Juan Pablo)
        # Instantiate services that need config
        cerebro_ia = CerebroIA(config_loader)
        vision_service = VisionService(db)
        audio_service = AudioService(config_loader)

        response_text = ""
        
        if msg_type == "text":
            context = prospect_data.get("summary", "") if prospect_data else ""
            response_text = cerebro_ia.pensar_respuesta(message_body, context=context, prospect_data=prospect_data)
            
        elif msg_type == "image":
            media_id = msg_data.get("media_id")
            mime_type = msg_data.get("mime_type")
            image_bytes = await _download_media(media_id)
            if image_bytes:
                response_text = await vision_service.analyze_image(image_bytes, mime_type, user_phone)
            else:
                response_text = "No pude descargar la imagen. 😢"
                
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
            data["media_id"] = msg["image"]["id"]
            data["mime_type"] = msg["image"]["mime_type"]
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
            # 1. Get URL
            r1 = await client.get(url, headers=headers)
            if r1.status_code != 200: return None
            media_url = r1.json().get("url")
            
            # 2. Get Content
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
