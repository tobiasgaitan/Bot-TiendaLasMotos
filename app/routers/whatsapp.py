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
from app.services.catalog_service import CatalogService # Local instantiation class
from app.services.survey_service import survey_service # Singleton
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
        response_text = None # FIX: Initialize to prevent UnboundLocalError
        
        msg_id_unique = msg_data.get("id") or f"{user_phone}_{int(datetime.now().timestamp())}"
        
        if msg_type == "text":
            message_body = msg_data.get("text", "").strip()
            
            # --- DEBOUNCE LOGIC START ---
            if message_buffer:
                # Add to buffer
                is_added = await message_buffer.add_message(user_phone, message_body, msg_id_unique)
                if not is_added:
                    logger.info(f"⏭️ Duplicate webhook ignored immediately for {msg_id_unique}")
                    return
                
                # Wait for debounce window (3s)
                await asyncio.sleep(message_buffer.debounce_seconds)
                
                # Check if this task is still active (or superseded by newer message)
                if not message_buffer.is_task_active(user_phone, msg_id_unique):
                    logger.info(f"⏭️ Task {msg_id_unique} superseded. Skipping processing.")
                    return
                
                # Get aggregated message
                message_body = await message_buffer.get_aggregated_message(user_phone)
                # Clear buffer immediately to prepare for next batch (or keep if we want strict window)
                # But here we consume it, so we should clear.
                await message_buffer.clear_buffer(user_phone)
                
                if not message_body:
                    return # Should not happen if logic is correct
            # --- DEBOUNCE LOGIC END ---
            
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
                            if response_text.startswith("MOTO_DETECTADA:"):
                                logger.info("🧠 Moto detected. Routing to CerebroIA for cross-selling...")
                                _ensure_services()
                                cerebro_ia = CerebroIA(config_loader, catalog_service_local)
                                cerebro_ia.motor_financiero = motor_financiero
                                
                                vision_description = response_text.replace("MOTO_DETECTADA:", "").strip()
                                
                                prospect_data = None
                                current_history = []
                                skip_greeting = True # Skip greeting since we are mid-conversation usually
                                
                                if memory_service_module.memory_service:
                                    ms = memory_service_module.memory_service
                                    ms.create_prospect_if_missing(user_phone)
                                    ms.update_last_interaction(user_phone)
                                    prospect_data = ms.get_prospect_data(user_phone)
                                    
                                    if prospect_data and prospect_data.get('human_help_requested', False):
                                        logger.info(f"🛑 Human Help Requested flag active for {user_phone}. Silencing bot.")
                                        return
                                    
                                    current_history = await ms.get_chat_history(user_phone, limit=10)
                                    simulated_user_msg = f"El usuario acaba de enviar una foto de esta moto: {vision_description}. Usa el catálogo para ofrecerle nuestra mejor equivalente."
                                    
                                    final_response = cerebro_ia.pensar_respuesta(
                                        simulated_user_msg, 
                                        context="", 
                                        prospect_data=prospect_data,
                                        history=current_history,
                                        skip_greeting=skip_greeting
                                    )
                                    
                                    if not final_response or not str(final_response).strip():
                                        final_response = "¡Qué buena máquina, parcero! Esa no la manejo, pero tengo opciones equivalentes en nuestro catálogo. ¿Te gustaría que busquemos una parecida?"
                                        logger.warning(f"⚠️ CerebroIA returned empty response for moto image. Injected fallback.")
                                    
                                    await _send_whatsapp_message(user_phone, final_response)
                                    
                                    # Save to History
                                    await ms.save_message(user_phone, "user", simulated_user_msg)
                                    await ms.save_message(user_phone, "model", final_response)
                                    
                                    # Update Summary
                                    try:
                                        summary_data = cerebro_ia.generate_summary(f"User: {simulated_user_msg}\nBot: {final_response}")
                                        await ms.update_prospect_summary(user_phone, summary_data.get("summary", ""), summary_data.get("extracted", {}))
                                    except Exception as e:
                                        logger.warning(f"Failed to update summary: {e}")
                                else:
                                    logger.warning("⚠️ Memory Service is NOT initialized. Cannot route image properly.")
                                    await _send_whatsapp_message(user_phone, "No pude conectar con mi cerebro para buscar esta moto. 😢")
                            else:
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
        if memory_service_module.memory_service and msg_type == "text":
            # Optimistic save (don't block too long)
            await memory_service_module.memory_service.save_message(user_phone, "user", message_body)

        # --- LÓGICA DE RESET NUCLEAR (PRIORIDAD 0) ---
        # FIX: Ensure it is strict text match
        if msg_type == "text" and message_body.strip() == "/reset":
            logger.warning(f"☢️ NUCLEAR RESET TRIGGERED for {user_phone}")
            
            # Variantes de ID
            ids_to_purge = list(set([user_phone, raw_phone, user_phone.replace("57", "", 1)]))
            deleted_count = 0
            
            collections_to_check = ["sessions", "prospectos"]
            
            if db:
                # 1. NUCLEAR PROSPECT WIPE (IDs and Auto-generated IDs)
                if memory_service_module.memory_service:
                    ms = memory_service_module.memory_service
                    p_deleted = ms.delete_prospect_completely(user_phone)
                    logger.info(f"🧹 Nuclear Prospect Wipe for {user_phone}. Docs deleted: {p_deleted}")

                for pid in ids_to_purge:
                    # 2. Main Sessions Collection (ROOT)
                    try:
                        doc_ref_session = db.collection("sessions").document(pid)
                        if doc_ref_session.get().exists:
                            doc_ref_session.delete()
                            logger.info(f"🗑️ Deleted ROOT session document {pid}")
                    except Exception: pass
                    
                    # 3. Deep Wipe of Global Session State (Absolute Purge)
                    try:
                        # 3.1 Nuclear Delete in Survey Service (handles fields + IDs + subcollections)
                        await survey_service.delete_session(db, pid)
                        
                        # 3.2 Verification for the requested legacy path + Historial purge
                        legacy_ref = db.collection("mensajeria").document("whatsapp").collection("sesiones").document(pid)
                        
                        # NUCLEAR HISTORY PURGE (Subcollection Orphan Cleanup)
                        history_ref = legacy_ref.collection("historial")
                        for doc in history_ref.stream():
                            doc.reference.delete()
                            deleted_count += 1
                        
                        exists_after = legacy_ref.get().exists
                        logger.info(f"🔥 Hard Purge verification for {pid}. Exists now: {exists_after}")
                        
                        if not exists_after:
                            deleted_count += 1
                    except Exception as e: 
                        logger.error(f"❌ Error during hard purge for {pid}: {e}")

            # Always send confirmation
            confirm_msg = f"☢️ RESET COMPLETADO. Memoria limpia. ({deleted_count} registros purgados). Escribe 'Hola' para iniciar."
            await _send_whatsapp_message(user_phone, confirm_msg)
            return
        # --- FIN RESET NUCLEAR ---

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
            # Create if missing (ensure prospect exists)
            ms.create_prospect_if_missing(user_phone)
            # Update timestamp
            ms.update_last_interaction(user_phone)
            # Get data
            prospect_data = ms.get_prospect_data(user_phone)
            logger.info(f"👤 Prospect Data Loaded: {prospect_data.get('name', 'Unknown') if prospect_data else 'None'}")
            
            # Human Gatekeeper Check
            if prospect_data and prospect_data.get('human_help_requested', False):
                logger.info(f"🛑 Human Help Requested flag active for {user_phone}. Silencing bot.")
                return

            # LOAD HISTORY for Context (CONTEXT FIX)
            logger.info(f"📜 Loading chat history for {user_phone}...")
            current_history = await ms.get_chat_history(user_phone, limit=10)
            
            # GREETING BYPASS LOGIC (Time-Based)
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
                    if last_time.tzinfo is None:
                        last_time = last_time.replace(tzinfo=timezone.utc)
                        
                    delta = now - last_time
                    diff_seconds = delta.total_seconds()
                    
                    if diff_seconds < 7200:
                        skip_greeting = True
                        logger.info(f"⏳ Recent conversation detected ({int(diff_seconds)}s ago). Skipping greeting.")
        else:
            logger.warning("⚠️ Memory Service is NOT initialized. Skipping persistence.")

        # --- V16: CONTEXT SWITCHING & SURVEY INTERCEPTION (Orchestration) ---
        survey_pending_question = None
        is_answering_survey = False
        survey_just_triggered = False
        session = {}

        if msg_type == "text" and db:
            # 1. Check for active survey status (Transient Session)
            session = await _get_session(db, user_phone)
            status = session.get("status", "IDLE")
            
            # 2. Check for Persistent Survey State (Source of Truth for Context Switching)
            persistent_survey = None
            if memory_service_module.memory_service:
                persistent_survey = memory_service_module.memory_service.get_survey_state(user_phone)

            # 3. Decision Logic: Is there a survey active?
            active_survey_step = None
            
            if status.startswith("SURVEY_STEP_"):
                active_survey_step = status
                logger.info(f"📋 Survey active in SESSION for {user_phone}: {status}")
            elif persistent_survey and persistent_survey.get("is_active"):
                active_survey_step = persistent_survey.get("current_step")
                logger.info(f"📋 Survey active in PROSPECT for {user_phone}: {active_survey_step}")
                # Synchronize session if missing
                if not status.startswith("SURVEY_STEP_"):
                    status = active_survey_step
                    session = {
                        "status": status,
                        "answers": persistent_survey.get("collected_data", {}),
                        "retry_count": 0
                    }
                    await _get_session(db, user_phone) # Dummy read? No, we should update.
                    # Actually, we just populate the variables for the flow below
                    logger.info(f"🔄 Synchronized transient session from persistent state for {user_phone}")

            if active_survey_step:
                # Map technical step ID to the actual human question
                SURVEY_STEPS_MAP = {
                    "SURVEY_STEP_0_NAME": "¿Cuál es tu nombre completo?",
                    "SURVEY_STEP_1_AUTH": "¿Autorizas el tratamiento de tus datos personales para realizar tu estudio de crédito?",
                    "SURVEY_STEP_2_CITY": "¿En qué ciudad te encuentras ubicado?",
                    "SURVEY_STEP_3_LABOR": "3️⃣ ¿A qué te dedicas actualmente? (Tipo de contrato u ocupación)",
                    "SURVEY_STEP_4_INCOME": "4️⃣ ¿Cuáles son tus ingresos mensuales totales? (Escribe solo el número)",
                    "SURVEY_STEP_5_HISTORY": "5️⃣ ¿Cómo ha sido tu comportamiento con créditos anteriores? (Ej: Excelente, Reportado)",
                    "SURVEY_STEP_6_GAS": "6️⃣ ¿Tienes servicio de Gas Natural a tu nombre? (Responde Sí o No)",
                    "SURVEY_STEP_7_MOBILE": "7️⃣ ¿Tienes un plan de celular Postpago? (Responde Sí o No)"
                }
                survey_pending_question = SURVEY_STEPS_MAP.get(active_survey_step)

                
                if survey_pending_question:
                    logger.info(f"📋 Survey Active ({status}). Evaluating intent...")
                    intent_eval = cerebro_ia.evaluate_survey_intent(message_body, survey_pending_question)
                    
                    if intent_eval.get("is_answering_survey"):
                        logger.info("✅ Intent: Answering survey. Routing to SurveyService.")
                        is_answering_survey = True
                        # --- INTENT BRIDGE: Data Sanitization ---
                        # If the AI sanitized the user message (e.g. "minimo" -> "1300000"), we use that
                        sanitized = intent_eval.get("sanitized_value")
                        if sanitized and str(sanitized).lower() != "none" and str(sanitized) != message_body:
                            logger.info(f"🌉 Intent Bridge: Sanitizing input '{message_body}' -> '{sanitized}'")
                            message_body = str(sanitized)
                    else:
                        logger.info(f"🔄 Intent: Context Switch! Reasoning: {intent_eval.get('reasoning')}")
                        # We route to AI Brain, but we'll pass the question to re-ask it later
            
            # --- V17: DETERMINISTIC SURVEY TRIGGER (Init Logic) ---
            if status == "IDLE" and not active_survey_step:
                financial_keywords = ["brilla", "financiar", "crédito", "financiamiento", "estudio de crédito", "cuotas"]
                if any(k in message_body.lower() for k in financial_keywords):
                    logger.info(f"🎯 Deterministic Trigger! Financial keyword detected in '{message_body}'. Starting survey...")
                    is_answering_survey = True
                    survey_just_triggered = True
                    # Initialize session for SurveyService
                    status = "SURVEY_STEP_0_NAME"
                    session = {"status": status, "answers": {}, "retry_count": 0}
                    # Force response to first question
                    response_text = "¡Hola! Qué bueno tenerte por aquí. 🤩 Para empezar, ¿cuál es tu nombre completo?"
                    # Synchronize persistence
                    if memory_service_module.memory_service:
                        memory_service_module.memory_service.save_survey_state(user_phone, "financial_capture", status, {})
            # --------------------------------------------------------


        # --- END CONTEXT SWITCHING LOGIC ---

        # 3. Generar Respuesta (AI o Audio o Encuesta)
        if msg_type == "text":
            if is_answering_survey:
                if survey_just_triggered:
                    logger.info(f"⏩ Survey just triggered for {user_phone}. Skipping handle_survey_step execution for this turn.")
                else:
                    logger.info(f"📝 Executing survey step for {user_phone}...")
                    response_text = await survey_service.handle_survey_step(
                        db, user_phone, message_body, session, motor_financiero
                    )
            else:
                logger.info(f"🧠 Calling CerebroIA.pensar_respuesta... (Skip Greeting: {skip_greeting}, Pending: {survey_pending_question})")
                response_text = cerebro_ia.pensar_respuesta(
                    message_body, 
                    context=context, 
                    prospect_data=prospect_data,
                    history=current_history,
                    skip_greeting=skip_greeting,
                    pending_survey_question=survey_pending_question
                )

                # --- V17: AI-DRIVEN SURVEY TRIGGER (Flag check) ---
                if str(response_text).startswith("TRIGGER_SURVEY:"):
                    survey_id = str(response_text).split(":")[1]
                    logger.info(f"🎯 AI-Driven Trigger! Initiating survey '{survey_id}' for {user_phone}")
                    is_answering_survey = True
                    survey_just_triggered = True
                    # Re-route to SurveyService immediately
                    status = "SURVEY_STEP_0_NAME"
                    session = {"status": status, "answers": {}, "retry_count": 0}
                    # Force response to first question
                    response_text = "¡Hola! Qué bueno tenerte por aquí. 🤩 Para empezar, ¿cuál es tu nombre completo?"
                    # Synchronize persistence
                    if memory_service_module.memory_service:
                        memory_service_module.memory_service.save_survey_state(user_phone, "financial_capture", status, {})
                # ----------------------------------------------------

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
            if audio_bytes:
                response_text = await audio_service.process_audio(audio_bytes, mime_type)
            else:
                response_text = "No pude descargar el audio. 😢"
            
        if response_text:
            # Check for AI Handoff
            if response_text.startswith("HANDOFF_TRIGGERED"):
                if memory_service_module.memory_service:
                    memory_service_module.memory_service.set_human_help_status(user_phone, True)
                await _send_whatsapp_message(user_phone, "Entendido. Buscando un humano... 🔍")
                try:
                    from app.services.notification_service import notification_service
                    await notification_service.notify_human_handoff(user_phone, "ai_trigger")
                except ImportError: pass
            else:
                # --- NATIVE IMAGE INTEGRATION ---
                import re
                image_pattern = r'\[IMAGE:\s*(https?://[^\s\]]+)\]'
                images_found = re.findall(image_pattern, response_text)
                
                # Remove all image tags from the text
                cleaned_response_text = re.sub(image_pattern, '', response_text).strip()
                
                # If images found, send the first one natively
                if images_found:
                    image_url = images_found[0] # Take the first image
                    
                    if len(cleaned_response_text) < 1024:
                        # Strategy A: Caption (Max 1024 chars in Meta API)
                        logger.info(f"📸 Native Image Strategy A (Caption): text len={len(cleaned_response_text)}")
                        success = await _send_whatsapp_image(user_phone, image_url, caption=cleaned_response_text)
                        if not success:
                            logger.warning(f"⚠️ Failed to send image natively, falling back to text only.")
                            await _send_whatsapp_message(user_phone, cleaned_response_text)
                    else:
                        # Strategy B: Image then Text
                        logger.info(f"📸 Native Image Strategy B (Split): text len={len(cleaned_response_text)} > 1024")
                        await _send_whatsapp_image(user_phone, image_url, caption="")
                        await asyncio.sleep(1.5) # Hard-coded delay between Image and Text
                        await _send_whatsapp_message(user_phone, cleaned_response_text)
                        
                    response_text = cleaned_response_text # Update for history saving (hide tags from history)
                else:
                    await _send_whatsapp_message(user_phone, response_text)
                
                # Save Bot Response to History (PERSISTENCE FIX)
                if memory_service_module.memory_service:
                    await memory_service_module.memory_service.save_message(user_phone, "model", response_text)

                # Update Summary
                if msg_type == "text" and memory_service_module.memory_service:
                    try:
                        conversation = f"User: {message_body}\nBot: {response_text}"
                        summary_data = cerebro_ia.generate_summary(conversation)
                        await memory_service_module.memory_service.update_prospect_summary(
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

async def _send_whatsapp_image(to_phone: str, image_url: str, caption: str = "") -> bool:
    """Send WhatsApp image via Cloud API with optional caption."""
    try:
        phone_number_id = settings.phone_number_id
        if not phone_number_id or not settings.whatsapp_token:
            logger.error("Missing WhatsApp credentials")
            return False

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
            "type": "image",
            "image": {"link": image_url}
        }
        
        if caption:
            payload["image"]["caption"] = caption
            
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=headers, timeout=10.0)
            if resp.status_code not in [200, 201]:
                logger.error(f"Failed to send image: {resp.text}")
                return False
            return True
            
    except Exception as e:
        logger.error(f"Error sending image: {e}")
        return False

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
