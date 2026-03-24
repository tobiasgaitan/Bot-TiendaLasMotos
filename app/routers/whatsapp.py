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
from app.services.storage_service import storage_service # Singleton
from app.services.message_buffer import MessageBuffer # Local instantiation

# --- MEMORY SERVICE (MODULE IMPORT FOR SINGLETON ACCESS) ---
import app.services.memory_service as memory_service_module
# Note: Access via memory_service_module.memory_service to get the updated instance


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
message_buffer = None

def _ensure_services():
    """Lazy initialization of services"""
    global db, config_loader, motor_financiero, catalog_service_local, message_buffer
    
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
            # Ensure configuration is actually loaded in this worker process
            if not config_loader.get_juan_pablo_personality().get("name"):
                 logger.info("🔧 ConfigLoader initialized empty in worker. forcing load_all()...")
                 config_loader.load_all()
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
             
    # 5. Message Buffer
    if not message_buffer:
        message_buffer = MessageBuffer(debounce_seconds=5.0)

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
        background_tasks.add_task(_handle_message_background, msg_data, background_tasks)
        return {"status": "received"}
        
    except Exception as e:
        logger.error(f"Error procesando webhook: {e}")
        return {"status": "error"}


# ============================================================================
# BACKGROUND LOGIC
# ============================================================================

async def _handle_message_background(msg_data: Dict[str, Any], background_tasks: BackgroundTasks) -> None:
    """Lógica principal del bot (Procesamiento Asíncrono)"""
    # Ensure services are initialized before proceeding
    _ensure_services()

    try:
        # 1. Extracción de Datos
        from app.core.utils import PhoneNormalizer
        
        raw_phone = msg_data["from"]
        user_phone = PhoneNormalizer.normalize(raw_phone)
        msg_type = msg_data["type"].lower()
        msg_id_unique = msg_data.get("id") or f"{user_phone}_{int(datetime.now().timestamp())}"

        # --- PROTOCOLO READ-FIRST (PRIORIDAD 1) ---
        # Marcamos como leído ANTES de cualquier lógica para evitar el 'check gris'
        # y confirmar a Meta que el webhook fue recibido.
        from app.services.whatsapp_service import whatsapp_service
        await whatsapp_service.mark_as_read(msg_id_unique)
        
        # DEBUG LOG for Image Troubleshooting
        logger.info(f"🕵️ DEBUG: Received message {msg_id_unique} from {user_phone} | Type: '{msg_type}'")
        
        message_body = ""
        response_text = None 
        
        if msg_type == "text":
            message_body = msg_data.get("text", "").strip()

        elif msg_type == "reaction":
            emoji = msg_data.get("emoji", "")
            message_id = msg_data.get("message_id", "")
            logger.info(f"👍 User reacted with '{emoji}' to message '{message_id}'")
            
            positive_emojis = ["👍", "❤️", "💯", "🔥", "✅", "👌", "😊", "🥰", "😍"]
            if emoji in positive_emojis:
                message_body = "Sí"
                msg_type = "text"
            else:
                return 

        # --- DEDUPLICACIÓN ESTRICTA Y BUFFERING ---
        if msg_type == "text":
            # Agregamos al buffer. Si retorna False, es un duplicado exacto de msg_id (vía Meta retry)
            is_added = await message_buffer.add_message(user_phone, message_body, msg_id_unique)
            if not is_added:
                logger.warning(f"🔄 Duplicate msg_id ignored: {msg_id_unique}")
                return

            # --- RESET ASÍNCRONO (CONFIRMACIÓN FLASH) ---
            if message_body.strip().lower() in ["reset", "/reset"]:
                logger.warning(f"☢️ NUCLEAR RESET TRIGGERED (Sync) for {user_phone}")
                
                # 1. Purga síncrona/esperable (Evita Zombie Data)
                if memory_service_module.memory_service:
                    ms = memory_service_module.memory_service
                    logger.info(f"🧹 [WIPE] Clearing local memory instances for {user_phone}...")
                    await ms.delete_prospect_completely(user_phone)
                
                await message_buffer.clear_buffer(user_phone)
                
                # 2. Respuesta confirmando el estado limpio
                await whatsapp_service.send_text_message(user_phone, "✅ Tu sesión ha sido reiniciada por completo. Cuéntame, ¿en qué moto estás interesado?")
                return 

            # Wait for debounce window (3s)
            await asyncio.sleep(message_buffer.debounce_seconds)
            
            # Check if this task is still active (superseded means another msg arrived)
            if not message_buffer.is_task_active(user_phone, msg_id_unique):
                logger.info(f"⏭️ Task {msg_id_unique} superseded. Aggregating...")
                return
            
            # Get aggregated message
            message_body = await message_buffer.get_aggregated_message(user_phone)
            await message_buffer.clear_buffer(user_phone)
            
            if not message_body:
                return

            # --- DEBOUNCE LOGIC END ---
            
        elif msg_type in ["image", "document", "sticker"]:
            logger.info(f"📸 Media detected from {user_phone} (Type: {msg_type}). Processing immediately...")
            await _mark_message_as_read(msg_data["id"])
            
            # Initialize Vision Service locally if needed
            if db:
                try:
                    vision_service = VisionService(db)
                    
                    # Robust extraction for Image, Document OR Sticker
                    media_data = {}
                    if msg_type == "image":
                        media_data = msg_data.get("image", {})
                    elif msg_type == "document":
                        media_data = msg_data.get("document", {})
                    elif msg_type == "sticker":
                        media_data = msg_data.get("sticker", {})
                    
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
                        vision_response = await vision_service.analyze_image(image_bytes, mime_type, user_phone, caption=caption)
                        logger.info(f"🧠 Raw Vision response: {vision_response}")
                        
                        if vision_response:
                            # 0. Handle Document Quality & Classification (v6.7.x)
                            if "QUALITY_CHECK:" in vision_response:
                                if "QUALITY_CHECK: FAILED" in vision_response:
                                    motivo = "borrosa o ilegible"
                                    if "|" in vision_response:
                                        parts = vision_response.split("|")
                                        for p in parts:
                                            if "Motivo:" in p:
                                                motivo = p.replace("Motivo:", "").strip().lower()
                                    
                                    p_name = "amigo"
                                    if memory_service_module.memory_service:
                                        pd = await memory_service_module.memory_service.get_prospect_data(user_phone)
                                        p_name = pd.get("name") or "amigo"
                                    
                                    await _send_whatsapp_message(user_phone, f"¡Uy {p_name}! 📸 La foto parece {motivo}. ¿Podrías enviarla de nuevo que se vea bien clarita? Así el banco no nos la rechaza.")
                                    return

                                elif "QUALITY_CHECK: PASSED" in vision_response:
                                    tipo = "CEDULA" # Default
                                    if "DOCUMENTO_DETECTADO:" in vision_response:
                                        tipo_raw = vision_response.split("DOCUMENTO_DETECTADO:")[1].strip().upper()
                                        if "CEDULA" in tipo_raw: tipo = "CEDULA"
                                        elif "RECIBO" in tipo_raw or "GAS" in tipo_raw: tipo = "RECIBO_GAS"
                                    
                                    logger.info(f"✅ Document quality passed: {tipo}. Uploading to Storage...")
                                    
                                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                    filename = f"prospectos/{user_phone}/{tipo.lower()}_{timestamp}.jpg"
                                    
                                    try:
                                        public_url = await asyncio.to_thread(
                                            storage_service.upload_document, 
                                            image_bytes, 
                                            filename, 
                                            mime_type
                                        )
                                        
                                        if memory_service_module.memory_service:
                                            ms = memory_service_module.memory_service
                                            field_url = "doc_cedula_url" if tipo == "CEDULA" else "doc_recibo_gas_url"
                                            field_flag = "doc_cedula" if tipo == "CEDULA" else "doc_recibo_gas"
                                            
                                            await ms.update_prospect_summary(user_phone, "", {
                                                field_url: public_url,
                                                field_flag: True
                                            })
                                            
                                            prospect = await ms.get_prospect_data(user_phone)
                                            if prospect.get("doc_cedula") and prospect.get("doc_recibo_gas"):
                                                await _send_whatsapp_message(user_phone, "¡Excelente! Ya tengo todo tu expediente completo. ✅ Un asesor lo revisará en breve.")
                                            else:
                                                faltante = "el recibo de gas" if tipo == "CEDULA" else "tu cédula"
                                                nombre_doc = "cédula" if tipo == "CEDULA" else "recibo de gas"
                                                await _send_whatsapp_message(user_phone, f"¡Recibida tu {nombre_doc}! ✅ Ya solo me falta {faltante} para terminar.")
                                        return
                                    except Exception as e:
                                        logger.error(f"❌ Error uploading document: {e}")
                                        await _send_whatsapp_message(user_phone, "Tuve un problemita guardando tu documento. ¿Podrías intentarlo de nuevo?")
                                        return

                            # 1. Handle Moto Detection (Legacy / Main Vision Logic)
                            elif "[MOTO_DETECTADA]" in vision_response:
                                vision_description = vision_response.replace("[MOTO_DETECTADA]", "").strip()
                                _ensure_services()
                                cerebro_ia = CerebroIA(config_loader, catalog_service_local)
                                cerebro_ia.motor_financiero = motor_financiero
                                
                                if memory_service_module.memory_service:
                                    ms = memory_service_module.memory_service
                                    await ms.create_prospect_if_missing(user_phone)
                                    # Memory Sync for context
                                    await ms.generate_and_update_summary(user_phone, f"User sent image of: {vision_description}", cerebro_ia)
                                    
                                    prospect_data = await ms.get_prospect_data(user_phone)
                                    current_history = await ms.get_chat_history(user_phone, limit=10)
                                    
                                    if prospect_data and prospect_data.get('human_help_requested', False):
                                        logger.info(f"🛑 Human Help Requested active for {user_phone}. Silencing bot.")
                                        return

                                    simulated_user_msg = f"El usuario acaba de enviar una foto de esta moto: {vision_description}. Usa el catálogo para ofrecerle nuestra mejor equivalente."
                                    final_response = await cerebro_ia.pensar_respuesta(
                                        simulated_user_msg, 
                                        context="", 
                                        prospect_data=prospect_data,
                                        history=current_history,
                                        skip_greeting=True
                                    )
                                    
                                    if not final_response:
                                        final_response = "Lo siento, tuve un problema procesando esa información. ¿Podrías repetirme qué buscas?"
                                    
                                    await _send_whatsapp_message(user_phone, final_response)
                                    await ms.save_message(user_phone, "user", simulated_user_msg)
                                    await ms.save_message(user_phone, "model", final_response)
                                    return

                            # 2. Handle Sentiment / Memes / Stickers
                            elif vision_response.startswith("[System Note:"):
                                logger.info("🧠 General image/meme/sticker detected.")
                                _ensure_services()
                                cerebro_ia = CerebroIA(config_loader, catalog_service_local)
                                cerebro_ia.motor_financiero = motor_financiero
                                
                                if memory_service_module.memory_service:
                                    ms = memory_service_module.memory_service
                                    await ms.create_prospect_if_missing(user_phone)
                                    await ms.generate_and_update_summary(user_phone, f"User sent media: {vision_response}", cerebro_ia)
                                    
                                    prospect_data = await ms.get_prospect_data(user_phone)
                                    current_history = await ms.get_chat_history(user_phone, limit=10)
                                    
                                    if prospect_data and prospect_data.get('human_help_requested', False):
                                        return
                                    
                                    final_response = await cerebro_ia.pensar_respuesta(
                                        vision_response,
                                        context="", 
                                        prospect_data=prospect_data,
                                        history=current_history,
                                        skip_greeting=True
                                    )
                                    
                                    if not final_response:
                                        final_response = "¡Estuvo bueno! 😅 Pero cuéntame, ¿en qué moto estabas pensando?"
                                    
                                    await _send_whatsapp_message(user_phone, final_response)
                                    await ms.save_message(user_phone, "user", vision_response)
                                    await ms.save_message(user_phone, "model", final_response)
                                    return

                            # 3. Fallback text
                            else:
                                logger.info("🧠 Fallback text returned from Vision AI.")
                                response_text = f"🏍️ **Catálogo Auteco Las Motos**\n\n{vision_response}"
                                await _send_whatsapp_message(user_phone, response_text)
                                return

                        
                        else:
                            await _send_whatsapp_message(user_phone, "¡Uff! Pero no alcanzo a ver bien los detalles. ¿Me cuentas qué es?")
                    else:
                        await _send_whatsapp_message(user_phone, "No pude descargar el archivo. Intenta de nuevo.")
                except Exception as e:
                    logger.error(f"❌ Error processing media: {e}")
                    await _send_whatsapp_message(user_phone, "Tuve un problema viendo el archivo. ¿Me cuentas qué es? 😅")
            
            return  # EARLY EXIT: Stop processing here
            
        # Marcar como leído locally
        await _mark_message_as_read(msg_data["id"]) 

        # 1.5 Save User Message to History (PERSISTENCE FIX)
        if memory_service_module.memory_service:
            if msg_type == "text" and message_body:
                # Optimistic save (don't block too long)
                await memory_service_module.memory_service.save_message(user_phone, "user", message_body)
            # AUDIO: [Mensaje de Voz] removed here to avoid blinding the extractor.
            # It will be saved with the actual transcription inside the audio block.


        # --- UPDATE CATALOG CACHE ---
        if msg_type == "text" and message_body.strip() in ["/update", "/refresh_catalog"]:
            logger.warning(f"🔄 CATALOG REFRESH TRIGGERED by {user_phone}")
            try:
                catalog_service_local.refresh()
                confirm_msg = "✅ Catálogo actualizado en memoria exitosamente."
            except Exception as e:
                logger.error(f"❌ Error refreshing catalog: {e}")
                confirm_msg = f"❌ Error al actualizar el catálogo: {str(e)}"
                
            await _send_whatsapp_message(user_phone, confirm_msg)
            return

        # 2. Gestión de Sesión
        # 2. Gestión de Sesión & Servicios
        logger.info(f"⚙️ Starting Session Management for {user_phone}...")
        prospect_data = None
        current_history = []
        skip_greeting = False
        context = "" # Initialize context to prevent UnboundLocalError
        
        # Initialize Services Locally
        logger.info("🧠 Initializing CerebroIA...")
        cerebro_ia = CerebroIA(config_loader, catalog_service_local)
        cerebro_ia.motor_financiero = motor_financiero # Inject Financial Motor
        vision_service = VisionService(db)
        audio_service = AudioService(config_loader)
        
        if memory_service_module.memory_service:
            ms = memory_service_module.memory_service
            
            # 1. Get existing data FIRST to decide on greeting
            prospect_data = await ms.get_prospect_data(user_phone)
            newly_created = not (prospect_data and prospect_data.get("exists", False))
            
            # 2. LOAD HISTORY for Context
            logger.info(f"📜 Loading chat history for {user_phone}...")
            current_history = await ms.get_chat_history(user_phone, limit=10)
            
            # GREETING BYPASS LOGIC (Time-Based)
            # ULTIMATUM: If it's a new prospect or history is empty, skip_greeting MUST be False.
            if len(current_history) <= 1 or newly_created:
                skip_greeting = False
                logger.info(f"🆕 Fresh start detected (Newly created: {newly_created}). Full greeting enabled.")
            else:
                # Check the second to last message (the previous interaction)
                prev_msg = current_history[-2]
                last_ts = prev_msg.get("timestamp")
                
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
                    # Calculate duration since previous message
                    now = datetime.now(timezone.utc)
                    if last_time.tzinfo is None:
                        last_time = last_time.replace(tzinfo=timezone.utc)
                        
                    delta = now - last_time
                    diff_seconds = delta.total_seconds()
                    
                    if diff_seconds < 43200: # 12 hours
                        skip_greeting = True
                        logger.info(f"⏳ Recent conversation detected ({int(diff_seconds)}s ago). Skipping greeting.")

            # 3. NOW update/create timestamps AFTER decision is made
            ms.create_prospect_if_missing(user_phone)
            ms.update_last_interaction(user_phone)
            
            logger.info(f"👤 Prospect Data Processed: {prospect_data.get('name', 'Unknown') if prospect_data else 'None'}")
            
            # Human Gatekeeper Check (Mantenibilidad)
            if prospect_data and prospect_data.get('human_help_requested', False):
                logger.info(f"🛑 Human Help Requested flag active for {user_phone}. Silencing bot.")
                return
        else:
            logger.warning("⚠️ Memory Service is NOT initialized. Skipping persistence.")

        # SurveyService state machine REMOVED — 2026-03-12
        # WHY: The deterministic branch (is_answering_survey) completely bypassed pensar_respuesta
        # when a survey session was active. It returned hardcoded survey questions directly from
        # Python, so the LLM never ran and Phase 2/3 Firestore guardrails were never evaluated.
        # The LLM now handles the full credit survey flow organically via the Firestore prompt.
        # The background generate_summary still extracts answers and saves them to Firestore.

        # --- END CONTEXT SWITCHING LOGIC ---

        # 3. Generar Respuesta (LLM exclusivo — pensar_respuesta)
        if msg_type == "text":
            # --- LINEAR BLOCKING: Memory Update (Wait for Firestore) ---
            try:
                # Identify last bot question for anchoring
                last_bot_q = ""
                for m in reversed(current_history or []):
                    if m.get("role") == "model":
                        last_bot_q = m.get("content", "")
                        break
                
                # Full Context for Extraction
                history_context = ""
                context_messages = (current_history or [])[-6:]
                for m in context_messages:
                    role = "User" if m.get("role") == "user" else "Bot"
                    history_context += f"{role}: {m.get('content', '')}\n"
                
                conversation = f"{history_context}User: {message_body}"

                # 1. Generate & Update Summary (BLOCKING)
                logger.info(f"🧠 [LINEAR BLOCKING] Starting Memory Sync for {user_phone}")
                await ms.generate_and_update_summary(
                    user_phone, 
                    conversation, 
                    cerebro_ia, 
                    last_bot_question=last_bot_q
                )
                
                # 2. GESTIÓN DE VERDAD: Re-fetch fresh prospect data from Firestore
                prospect_data = await ms.get_prospect_data(user_phone)
                logger.info(f"✅ [LINEAR BLOCKING] Memory Synced. Identity: {prospect_data.get('name')}")

            except Exception as e:
                logger.error(f"❌ Error in Linear Blocking flow: {e}")
                # Fallback to local data if sync fails
                if not prospect_data:
                    prospect_data = await ms.get_prospect_data(user_phone)

            # ALTERNATIVE C: Pre-processing Message Enrichment (Anchor)
            enriched_message = message_body
            if prospect_data and prospect_data.get("moto_interest"):
                moto_interes = prospect_data.get("moto_interest")
                if len(message_body) < 60 and not any(m in message_body.lower() for m in ["otra", "cambiar", "no la"]):
                    enriched_message = f"[Contexto CRM: Hablando sobre {moto_interes}]\nMensaje: {message_body}"
                    logger.info(f"💉 Enriched user message with Moto Anchor: {moto_interes}")

            # 3. Inferencia de la IA (Solo con datos confirmados)
            logger.info(f"🧠 Calling CerebroIA.pensar_respuesta (Await)...")
            response_text = await cerebro_ia.pensar_respuesta(
                enriched_message,
                context=context,
                prospect_data=prospect_data,
                history=current_history,
                skip_greeting=skip_greeting
            )

            # TRIGGER_SURVEY interception REMOVED — 2026-03-12
            # WHY: This block replaced the LLM's natural response with hardcoded survey
            # text whenever start_credit_survey was called. The LLM now handles all
            # Phase 3 credit questions organically via the Firestore prompt.

            logger.info(f"🧠 Response determined: '{str(response_text)[:50]}...'")
            
            # LATENCY SIMULATION (Natural Typing Delay)
            # Rule: First response to a new session (or after long pause) must be instant (0s).
            # Rule: Subsequent responses need natural delay (Calculated).
            if not skip_greeting:
                logger.info("🚀 Smart Latency: New session detected. Skipping typing delay (0s).")
                typing_delay = 0
            else:
                import random
                
                # 1. Simulación y Naturalidad
                base_delay = len(str(response_text)) / 35.0
                jitter = random.uniform(0.5, 1.5)
                calculated_delay = base_delay + jitter
                
                # 2. Límite de seguridad
                typing_delay = min(8.0, calculated_delay)
                logger.info(f"⏳ Human Latency: len={len(str(response_text))}, delay={typing_delay:.2f}s")

            if typing_delay > 0:
                await asyncio.sleep(typing_delay)
            
        elif msg_type == "audio":
            media_id = msg_data.get("media_id")
            mime_type = msg_data.get("mime_type")
            audio_bytes = await _download_media(media_id)
            
            # GET HISTORY BEFORE AI
            current_history = []
            if memory_service_module.memory_service:
                ms = memory_service_module.memory_service
                ms.create_prospect_if_missing(user_phone) # Good practice
                ms.update_last_interaction(user_phone)
                
                # Check for Human Handoff status
                prospect_data = await ms.get_prospect_data(user_phone)
                if prospect_data and prospect_data.get("human_help_requested", False):
                     logger.info(f"👤 User {user_phone} is assigned to Human. Ignoring AI.")
                     return
                
                current_history = await ms.get_chat_history(user_phone, limit=10)
                
            if audio_bytes:
                # Transcribe Audio
                transcription = await audio_service.transcribe_audio(audio_bytes, mime_type)
                
                if transcription:
                    logger.info(f"🎤 Audio Transcribed: '{transcription}'")
                    
                    # 1. Save actual transcription to history (blinding fix)
                    if memory_service_module.memory_service:
                        await ms.save_message(user_phone, "user", transcription)
                    
                    # 1. LINEAR BLOCKING: Memory Sync (Wait for Firestore)
                    logger.info(f"🧠 [LINEAR BLOCKING] Starting Memory Sync (Audio) for {user_phone}")
                    await ms.generate_and_update_summary(
                        user_phone, 
                        f"User sent audio. Transcription: {transcription}", 
                        cerebro_ia, 
                        last_bot_question=""
                    )
                    
                    # 2. Re-fetch
                    prospect_data = await ms.get_prospect_data(user_phone)
                    current_history = await ms.get_chat_history(user_phone, limit=10)

                    # 3. AI Inference (Await)
                    response_text = await cerebro_ia.pensar_respuesta(
                        transcription,
                        context=context, 
                        prospect_data=prospect_data,
                        history=current_history,
                        skip_greeting=True
                    )
                else:
                    response_text = "Escuché el audio pero no entendí bien. ¿Me repites? 😅"
            else:
                response_text = "No pude descargar el audio. 😢"
            
        if response_text:
            # Check for AI Handoff
            if response_text.startswith("HANDOFF_TRIGGERED"):
                if memory_service_module.memory_service:
                    memory_service_module.memory_service.set_human_help_status(user_phone, True)
                await _send_whatsapp_message(user_phone, "Te voy a transferir con un compañero para que te ayude con esto. Dame un momento...")
                try:
                    from app.services.notification_service import notification_service
                    await notification_service.notify_human_handoff(user_phone, "ai_trigger")
                except ImportError: pass
            else:
                # --- PHASE-GATE IMAGE INJECTION (Update v6.3.1) ---
                if response_text.startswith("PHASE_GATE_TRIGGERED:"):
                    logger.info("🛡️ PHASE-GATE TRIGGERED detected.")
                    response_text = response_text.replace("PHASE_GATE_TRIGGERED:", "").strip()
                    
                    # 🚀 [BYPASS OPTIMIZATION] (v6.6.1)
                    moto_confirmada = prospect_data.get("moto_confirmada", False) if prospect_data else False
                    
                    if not moto_confirmada:
                        logger.info("📸 Injecting dynamic image (moto not confirmed).")
                        # Logica v6.3.1: Priorizar interes, sino Raider 125
                        moto_interest = prospect_data.get("moto_interest") if prospect_data else None
                        moto_to_search = moto_interest if moto_interest else "RAIDER 125"
                        
                        if catalog_service_local:
                            try:
                                # Search for interested bike or default
                                moto_results = catalog_service_local.search_items(moto_to_search)
                                
                                # Fallback if interest search failed (Competitor or not found)
                                if not moto_results and moto_interest:
                                    logger.info(f"🔄 No results for '{moto_interest}' (Competitor?). Falling back to Raider 125.")
                                    moto_results = catalog_service_local.search_items("RAIDER 125")
                                
                                if moto_results:
                                    moto = moto_results[0]
                                    image_url = moto.get("image_url")
                                    moto_name = moto.get("name")
                                    
                                    if image_url:
                                        # Caption v6.3.1: "Mira esta [Moto]"
                                        caption = f"Mira esta {moto_name}\n\n{response_text}"
                                        logger.info(f"📸 Sending Phase-Gate dynamic image: {image_url} for {moto_name}")
                                        await _send_whatsapp_image(user_phone, image_url, caption=caption)
                                        
                                        # Save to history and stop
                                        if memory_service_module.memory_service:
                                            await memory_service_module.memory_service.save_message(user_phone, "model", response_text)
                                        return 
                            except Exception as e:
                                logger.error(f"⚠️ Error injecting dynamic Phase-Gate image: {e}")
                    else:
                        logger.info("⏩ [BYPASS] Skipping image injection: moto already confirmed.")

                # --- NATIVE IMAGE INTEGRATION ---
                import re
                # Support both Markdown ![alt](url) and legacy [IMAGE: url]
                # RESILIENCE FIX: Handle optional ! and spaces between ] and ( to catch degraded LLM formatting
                image_pattern = r'!?\[.*?\]\s*\((https?://[^\s\)]+)\)|\[IMAGE:\s*(https?://[^\s\]]+)\]'
                all_matches = re.findall(image_pattern, response_text)
                
                # Extract clean URLs from both groups
                images_found = [m[0] or m[1] for m in all_matches if m[0] or m[1]]
                
                # Remove all image tags from the text to avoid showing raw markdown/tags to the user
                cleaned_response_text = re.sub(image_pattern, '', response_text).strip()
                
                # If images found, send them using Strategy A (Caption) for better .webp compatibility
                if images_found:
                    image_url = images_found[0] # Take the first image
                    
                    # STRATEGY A (Caption): Single payload for better .webp compatibility
                    # WhatsApp Caption Limit: 1024 characters
                    MAX_CAPTION = 1024
                    
                    caption = cleaned_response_text
                    overflow_text = ""
                    
                    if len(caption) > MAX_CAPTION:
                        logger.warning(f"⚠️ Caption too long ({len(caption)} chars). Splitting...")
                        # Find last space within limit to avoid cutting words
                        split_idx = caption.rfind(' ', 0, MAX_CAPTION)
                        if split_idx == -1: split_idx = MAX_CAPTION
                        overflow_text = caption[split_idx:].strip()
                        caption = caption[:split_idx].strip()
                    
                    logger.info(f"📸 Strategy A (Caption): url={image_url}")
                    await _send_whatsapp_image(user_phone, image_url, caption=caption)
                    
                    if overflow_text:
                        logger.info(f"📤 Sending overflow text ({len(overflow_text)} chars)")
                        await _send_whatsapp_message(user_phone, overflow_text)
                    
                    # Store the cleaned text for history to avoid raw markdown clutter
                    response_text = cleaned_response_text 
                else:
                    await _send_whatsapp_message(user_phone, response_text)
                
                # Save Bot Response to History (PERSISTENCE FIX)
                if memory_service_module.memory_service:
                    await memory_service_module.memory_service.save_message(user_phone, "model", response_text)

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
        elif msg_type == "sticker":
            sticker_obj = msg["sticker"]
            data["sticker"] = sticker_obj
            data["media_id"] = sticker_obj.get("id")
            data["mime_type"] = sticker_obj.get("mime_type")
        elif msg_type == "reaction":
            reaction_obj = msg["reaction"]
            data["reaction"] = reaction_obj
            data["message_id"] = reaction_obj.get("message_id")
            data["emoji"] = reaction_obj.get("emoji")
        return data
    except:
        return None

async def _send_whatsapp_message(to_phone: str, message_text: str) -> None:
    """Send WhatsApp message via WhatsAppService."""
    from app.services.whatsapp_service import whatsapp_service
    await whatsapp_service.send_text_message(to_phone, message_text)

async def _send_whatsapp_image(to_phone: str, image_url: str, caption: str = "") -> bool:
    """Send Image via WhatsAppService."""
    from app.services.whatsapp_service import whatsapp_service
    try:
        await whatsapp_service.send_image_message(to_phone, image_url, caption)
        return True
    except Exception as e:
        logger.error(f"Error in _send_whatsapp_image: {e}")
        return False

async def _mark_message_as_read(message_id: str) -> None:
    """Mark as read via WhatsAppService."""
    from app.services.whatsapp_service import whatsapp_service
    await whatsapp_service.mark_as_read(message_id)

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
