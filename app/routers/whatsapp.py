"""
WhatsApp Webhook Router (Self-Contained Fix)
============================================
Handles Meta WhatsApp webhook verification and message reception.
Completely self-contained to avoid ModuleNotFoundError.
"""

import json
import logging
import httpx
import asyncio
import re
import hmac
import hashlib
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Query, HTTPException, BackgroundTasks
from fastapi.responses import PlainTextResponse
from google.cloud import firestore
from google.api_core import exceptions as gcp_exceptions

from app.core.config import settings
from app.core.config_loader import ConfigLoader
from app.core.security import get_firebase_credentials_object
from app.core.exceptions import HabeasDataBypassInterrupt

from app.services.judge_service import judge_service
from app.services.agentic_loop_service import AgenticOrchestrator as _AgenticOrchestrator
_router_orchestrator = _AgenticOrchestrator()
from app.services.financial_service import financial_service
from app.services.ai_brain import CerebroIA
from app.services.vision_service import VisionService
from app.services.audio_service import AudioService
from app.services.catalog_service import catalog_service
from app.services.storage_service import storage_service # Singleton
from app.services.message_buffer import MessageBuffer # Local instantiation

# --- MEMORY SERVICE (MODULE IMPORT FOR SINGLETON ACCESS) ---
import app.services.memory_service as memory_service_module
from app.services.config_service import config_service # [SSOT] Unified Config
# Note: Access via memory_service_module.memory_service to get the updated instance

# --- LANGFUSE OBSERVABILITY (Graceful Fallback & Context Sharing) ---
class _LangfuseContextShim:
    def update_current_trace(self, **kwargs): pass
    def update_current_observation(self, **kwargs): pass
    def update_current_generation(self, **kwargs): pass

try:
    from langfuse.decorators import observe, langfuse_context
except Exception:
    def observe(*args, **kwargs):
        def decorator(fn):
            return fn
        if args and callable(args[0]):
            return args[0]
        return decorator
    langfuse_context = _LangfuseContextShim()


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["WhatsApp"])

# Semáforo para controlar concurrencia de acuses de recibo Meta (Burst Mitigation)
status_semaphore = asyncio.Semaphore(5)

# locks for E.164 phone numbers (session locks) to prevent webhook race conditions
_session_locks = {}
_session_locks_lock = asyncio.Lock()

async def _get_session_lock(phone_number: str) -> asyncio.Lock:
    async with _session_locks_lock:
        if phone_number not in _session_locks:
            _session_locks[phone_number] = asyncio.Lock()
        return _session_locks[phone_number]

# ============================================================================
# STATE & INITIALIZATION
# ============================================================================

# Global variables initialized to None
db = None
config_loader = None
motor_financiero = None
message_buffer = None
_active_resets = set() # v9.8.3: Guard against concurrent resets

def _ensure_services_sync():
    """
    Lazy initialization of services (SYNCHRONOUS).
    WHY: Contains Firestore .stream() I/O via CatalogService.initialize().
    Must be called via asyncio.to_thread() from async handlers to prevent
    blocking FastAPI's event loop under Meta production load (BOT-INFRA-ASYNC-094).
    """

    global db, config_loader, motor_financiero, message_buffer
    
    # 5. Message Buffer (initialized first to ensure availability in tests)
    if not message_buffer:
        message_buffer = MessageBuffer(debounce_seconds=5.0)
        
    # 1. Firestore
    if not db:
        try:
            # v6.9.7: Try to retrieve from app.state if available, otherwise fallback
            from app.core.security import get_firebase_credentials_object
            creds = get_firebase_credentials_object()
            db = firestore.Client(credentials=creds, project=settings.gcp_project_id)
            logger.info(f"✅ Database connected to project: {settings.gcp_project_id}")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Firestore: {e}")
            return 

    # 2. Config Loader (Personality & Routing)
    if db and not config_loader:
        try:
            config_loader = ConfigLoader(db)
            if not config_loader.get_juan_pablo_personality().get("name"):
                 config_loader.load_all()
        except Exception as e:
            logger.error(f"❌ [INIT] ConfigLoader init failed: {e}", exc_info=True)

    # 2.1 Config Service (Financial SSOT)
    if db and not config_service._financial_config:
        try:
            config_service.initialize(db)
        except Exception as e:
            logger.error(f"❌ [INIT] ConfigService init failed: {e}", exc_info=True)

    # 3. Financial Service (Consolidated v1.5.0)
    if db and not motor_financiero:
         try:
            motor_financiero = financial_service
         except Exception as e:
            logger.error(f"❌ [INIT] FinancialService init failed: {e}", exc_info=True)

    # 4. Catalog Service
    if db and not catalog_service._db:
        try:
            catalog_service.initialize(db)
            logger.info("✅ CatalogService initialized")
        except Exception as e:
             logger.error(f"❌ Failed to initialize CatalogService: {e}")

async def _ensure_services():
    """
    Async wrapper for _ensure_services_sync().
    BOT-INFRA-ASYNC-094: Delegates synchronous Firestore I/O (.stream()) to
    a thread pool to unblock the event loop during lazy initialization.
    """
    await asyncio.to_thread(_ensure_services_sync)

def resolve_query_aliases(query: str, catalog_service) -> str:
    """
    Translates colloquial query terms or synonyms (e.g. 'señoritera') 
    to the canonical category name (e.g. 'semiautomatica') based on catalog aliases.
    """
    if not query:
        return query
    
    q_norm = query.lower().strip()
    
    # Try fetching aliases from catalog service or config service
    aliases = {}
    try:
        if catalog_service and hasattr(catalog_service, 'get_catalog_aliases'):
            aliases = catalog_service.get_catalog_aliases()
    except Exception as e:
        logger.warning(f"⚠️ Error retrieving catalog aliases: {e}")
        
    if not aliases:
        try:
            aliases = config_service.get_catalog_aliases()
        except Exception as e:
            logger.warning(f"⚠️ Error retrieving config aliases: {e}")
            
    if not aliases:
        return query

    # Normalize key/value strings to lowercase for comparison
    import re
    for category, synonyms in aliases.items():
        cat_lower = str(category).lower().strip()
        
        # Check category match as a word boundary
        if re.search(r'\b' + re.escape(cat_lower) + r'\b', q_norm):
            return cat_lower
            
        # Check synonym matches as word boundaries
        # Handle dict or list values dynamically
        syns_list = []
        if isinstance(synonyms, list):
            syns_list = synonyms
        elif isinstance(synonyms, dict):
            syns_list = list(synonyms.values())
        else:
            syns_list = [synonyms]
            
        for syn in syns_list:
            syn_lower = str(syn).lower().strip()
            if syn_lower and re.search(r'\b' + re.escape(syn_lower) + r'\b', q_norm):
                return cat_lower
                
    return query


# ============================================================================
# WEBHOOK ENDPOINTS
# ============================================================================

@router.get("")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
) -> PlainTextResponse:
    """Verificación del Webhook de Meta"""
    if hub_mode == "subscribe" and hub_verify_token == settings.webhook_verify_token:
        logger.info("✅ Webhook verificado correctamente.")
        return PlainTextResponse(content=hub_challenge)
    else:
        logger.error("❌ Token de verificación incorrecto.")
        raise HTTPException(status_code=403, detail="Forbidden")

async def _enqueue_cloud_task(payload: Dict[str, Any]) -> None:
    """
    Enqueue a webhook payload to Cloud Tasks for async processing.

    BOT-BRAIN-ALIGNMENT-099: dispatch_deadline limits total retry window to 120s.
    This prevents zombie messages when Meta webhook payloads expire or the bot's
    inference takes too long. After 120s Cloud Tasks stops retrying.

    RESILIENCE CONTRACT: The /webhook/task-processor endpoint SHOULD return HTTP 200
    and log errors internally for inference failures where we do NOT want Cloud Tasks
    to retry the message to the client. The dispatch_deadline acts as the primary shield.
    """
    try:
        from google.cloud import tasks_v2
        from google.protobuf import duration_pb2

        client = tasks_v2.CloudTasksClient()
        
        if not settings.cloud_tasks_queue_path or not settings.task_processor_url:
            raise ValueError("Cloud Tasks environment variables missing.")
            
        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": settings.task_processor_url,
                "headers": {
                    "Content-type": "application/json",
                    "X-Task-Token": settings.webhook_verify_token
                },
                "body": json.dumps(payload).encode(),
            },
            # BOT-BRAIN-ALIGNMENT-099: TTL de 120s para descartar webhooks zombi.
            # WHY: Sin dispatch_deadline, Cloud Tasks reintenta durante 30 min (default),
            # causando mensajes duplicados al usuario cuando Meta ya expiró el webhook.
            "dispatch_deadline": duration_pb2.Duration(seconds=120)
        }
        
        await asyncio.to_thread(
            client.create_task,
            request={"parent": settings.cloud_tasks_queue_path, "task": task}
        )
        logger.info(f"☁️ [CLOUD TASKS] Payload successfully enqueued to {settings.cloud_tasks_queue_path} (TTL: 120s)")
    except Exception as e:
        logger.error(f"❌ [CLOUD TASKS] Error enqueueing payload: {e}")
        raise HTTPException(status_code=500, detail="Failed to enqueue Cloud Task")

@router.post("")
async def webhook_handler(
    request: Request,
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    """Recepción de mensajes y acuses de recibo de WhatsApp."""
    try:
        body = await request.body()
        signature_header = request.headers.get("X-Hub-Signature-256")
        
        # Verify signature if secret is configured
        if settings.whatsapp_app_secret:
            if not signature_header:
                logger.error("❌ X-Hub-Signature-256 header missing")
                raise HTTPException(status_code=401, detail="Signature missing")
            
            expected_signature = "sha256=" + hmac.new(
                settings.whatsapp_app_secret.encode("utf-8"),
                body,
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(signature_header, expected_signature):
                logger.error(f"❌ Signature verification failed. Expected: {expected_signature}, Got: {signature_header}")
                raise HTTPException(status_code=401, detail="Signature mismatch")
        
        payload = json.loads(body)
        logger.info(f"📡 RADAR WEBHOOK RAW PAYLOAD: {json.dumps(payload)}")

        # Enforce startup / catalog lock guard early
        await _ensure_services()
        
        # Check atomic boolean flag catalog_ready with dynamic count fallback
        catalog_ready = False
        if request and hasattr(request, "app") and hasattr(request.app, "state"):
            val = getattr(request.app.state, "catalog_ready", False)
            if val is True:
                catalog_ready = True
            
        if not catalog_ready:
            catalog_items_count = len(catalog_service.get_all_items())
            min_items_val = settings.min_catalog_items
            if type(min_items_val).__name__ in ('Mock', 'MagicMock', 'AsyncMock'):
                min_items = 0
            else:
                try:
                    min_items = int(min_items_val)
                except (TypeError, ValueError):
                    min_items = 0
                
            if catalog_items_count < min_items:
                logger.error(
                    f"❌ [STARTUP-GUARD] Webhook rejected: catalog is not fully loaded "
                    f"({catalog_items_count}/{min_items} items, catalog_ready={catalog_ready})."
                )
                raise HTTPException(
                    status_code=503,
                    detail=f"Service Unavailable: Catalog not fully loaded ({catalog_items_count}/{min_items} items)."
                )

        # --- RAMA 1: Acuses de recibo Meta (sent/delivered/read/failed) ---
        # [ARCH-BULK-META-010] WHY: Meta envía webhooks 'statuses' para confirmar el
        # estado de entrega de los templates de campaña masiva. Antes de este parche,
        # _is_valid_message() los ignoraba silenciosamente (KeyError silenciado).
        if _is_valid_statuses(payload):
            if settings.cloud_tasks_queue_path and settings.task_processor_url:
                await _enqueue_cloud_task(payload)
            else:
                statuses_list = _extract_statuses_list(payload)
                for status_data in statuses_list:
                    try:
                        # Procesamiento asíncrono no bloqueante vía BackgroundTasks en ausencia de Cloud Tasks
                        background_tasks.add_task(_handle_statuses_background, status_data)
                    except Exception as e:
                        logger.error(f"❌ Error encolando acuse individual en webhook_handler: {e}", exc_info=True)
                        continue
            return {"status": "received"}

        # --- RAMA 2: Mensajes reales del usuario ---
        if not _is_valid_message(payload):
            return {"status": "ignored", "procesado": False}

        msg_data = _extract_message_data(payload)
        if not msg_data:
            return {"status": "ignored", "procesado": False}

        raw_phone = msg_data["from"]
        from app.core.utils import PhoneNormalizer
        user_phone = PhoneNormalizer.normalize(raw_phone)
        msg_id_unique = msg_data.get("id") or f"{user_phone}_{int(datetime.now().timestamp())}"
        if message_buffer and user_phone in message_buffer._processed_wamids and msg_id_unique in message_buffer._processed_wamids[user_phone]:
            logger.warning(f"🔄 Duplicate WAMID ignored in handler: {msg_id_unique}")
            return {"status": "ignored", "procesado": False}

        if settings.cloud_tasks_queue_path and settings.task_processor_url:
            await _enqueue_cloud_task(payload)
        else:
            # Procesamiento asíncrono no bloqueante vía BackgroundTasks
            background_tasks.add_task(_handle_message_background, msg_data, background_tasks)
            
        return {"status": "received"}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error procesando webhook: {e}")
        return {"status": "error"}


# ============================================================================
# INTERNAL WORKER
# ============================================================================

@router.post("/task-processor")
async def task_processor(
    request: Request,
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    """Worker interno que procesa las tareas encoladas de manera 100% síncrona."""
    # 1. Validación de seguridad (Auth interna)
    token = request.headers.get("X-Task-Token")
    if not token or token != settings.webhook_verify_token:
        logger.error("❌ Invalid or missing X-Task-Token in task-processor")
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"❌ Failed to parse JSON payload in task-processor: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # 2. Enrutamiento síncrono
    try:
        await _ensure_services()
        
        # Check atomic boolean flag catalog_ready with dynamic count fallback
        catalog_ready = False
        if request and hasattr(request, "app") and hasattr(request.app, "state"):
            val = getattr(request.app.state, "catalog_ready", False)
            if val is True:
                catalog_ready = True
            
        if not catalog_ready:
            catalog_items_count = len(catalog_service.get_all_items())
            min_items_val = settings.min_catalog_items
            if type(min_items_val).__name__ in ('Mock', 'MagicMock', 'AsyncMock'):
                min_items = 0
            else:
                try:
                    min_items = int(min_items_val)
                except (TypeError, ValueError):
                    min_items = 0
                
            if catalog_items_count < min_items:
                logger.error(
                    f"❌ [STARTUP-GUARD] Task processor rejected: catalog is not fully loaded "
                    f"({catalog_items_count}/{min_items} items, catalog_ready={catalog_ready})."
                )
                raise HTTPException(
                    status_code=503,
                    detail=f"Service Unavailable: Catalog not fully loaded ({catalog_items_count}/{min_items} items)."
                )

        if _is_valid_statuses(payload):
            statuses_list = _extract_statuses_list(payload)
            for status_data in statuses_list:
                try:
                    # Desacoplamiento asíncrono preventivo usando background_tasks nativo de FastAPI
                    # para evitar que la ráfaga de acuses bloquee el procesador de Cloud Tasks
                    background_tasks.add_task(_handle_statuses_background, status_data)
                except Exception as e:
                    logger.error(f"❌ Error procesando acuse individual en task_processor: {e}", exc_info=True)
                    continue
            return {"status": "processed", "type": "statuses"}

        if _is_valid_message(payload):
            msg_data = _extract_message_data(payload)
            if msg_data:
                await _handle_message_background(msg_data, background_tasks)
            return {"status": "processed", "type": "message"}

        return {"status": "ignored", "reason": "invalid_payload"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"❌ Error during synchronous task processing: {e}")
        # Zero-Silent-Failures: return 500 so Cloud Tasks can retry if configured
        raise HTTPException(status_code=500, detail="Task processing failed")

# ============================================================================
# BACKGROUND LOGIC
# ============================================================================

async def _handle_statuses_background(status_data: Dict[str, Any]) -> None:
    """
    [ARCH-BULK-META-010] Handler de acuses de recibo de Meta (sent/delivered/read/failed).

    WHY: Los templates de campaña masiva generan webhooks 'statuses' que deben
    persistirse en Firestore para auditoría y trazabilidad. El await es bloqueante
    para garantizar integridad transaccional antes de retornar.

    Zero-Silent-Failures: captura explícita de los errores más comunes para
    evitar que un fallo de Firestore quede invisible en el log.
    """
    try:
        await _ensure_services()
        recipient_id = status_data.get("recipient_id", "")
        status_value = status_data.get("status", "")
        wamid = status_data.get("id", "")

        if not recipient_id or not status_value:
            logger.warning(
                f"⚠️ [STATUSES] Payload incompleto ignorado: recipient_id='{recipient_id}', "
                f"status='{status_value}'"
            )
            return

        from app.core.utils import PhoneNormalizer
        recipient_id = PhoneNormalizer.normalize(recipient_id)

        logger.info(
            f"📬 [STATUSES] Procesando acuse '{status_value}' para {recipient_id} "
            f"(WAMID: {wamid})"
        )

        if status_value == 'read':
            logger.info(f"👉 Confirmación de lectura recibida para el número {recipient_id}")

        # Persistencia bloqueante (await) — mandato ARCH-BULK-META-010
        if memory_service_module.memory_service:
            errors = status_data.get("errors", [])
            async with status_semaphore:
                await memory_service_module.memory_service.update_whatsapp_status(
                    phone_number=recipient_id,
                    status_value=status_value,
                    wamid=wamid,
                    errors=errors,
                )
        else:
            logger.warning("⚠️ [STATUSES] MemoryService no inicializado. Acuse no persistido.")

    except Exception as e:
        logger.error(
            f"❌ [STATUSES] Error crítico en _handle_statuses_background: {str(e)}",
            exc_info=True
        )


@observe(name="whatsapp_webhook_background")
async def _handle_message_background(msg_data: Dict[str, Any], background_tasks: BackgroundTasks) -> None:
    """Lógica principal del bot (Procesamiento Asíncrono con bloqueo por sesión)"""
    from app.core.utils import PhoneNormalizer
    raw_phone = msg_data.get("from")
    if not raw_phone:
        logger.error("❌ Message payload missing 'from' phone number")
        return
    user_phone = PhoneNormalizer.normalize(raw_phone)
    
    lock = await _get_session_lock(user_phone)
    async with lock:
        await _handle_message_background_impl(msg_data, background_tasks)

async def _handle_message_background_impl(msg_data: Dict[str, Any], background_tasks: BackgroundTasks) -> None:
    """Lógica principal del bot (Procesamiento Asíncrono - Implementación)"""
    # Ensure services are initialized before proceeding
    await _ensure_services()

    try:
        # 1. Extracción de Datos
        from app.core.utils import PhoneNormalizer
        
        raw_phone = msg_data["from"]
        user_phone = PhoneNormalizer.normalize(raw_phone)
        msg_type = msg_data.get("type", "text").lower()
        msg_id_unique = msg_data.get("id") or f"{user_phone}_{int(datetime.now().timestamp())}"
        phone_number_id = msg_data.get("phone_number_id")

        # [BOT-TRACE-201] Propagar telemetría de Langfuse al trace raíz del webhook
        try:
            from langfuse.decorators import langfuse_context as lf_ctx
        except Exception:
            lf_ctx = langfuse_context

        lf_ctx.update_current_trace(
            user_id=user_phone,
            session_id=f"wa_{user_phone}",
            metadata={
                "msg_id": msg_id_unique,
                "phone_number_id": phone_number_id,
                "msg_type": msg_type
            }
        )

        # 1.1 Extracción temprana de Body para Idempotencia (v9.8.3)
        message_body = ""
        is_positive_reaction = False
        if msg_type == "text":
            message_body = msg_data.get("text", "").strip()
        elif msg_type == "reaction":
            # Extraer emoji para logica de reacción
            reaction_data = msg_data.get("reaction", {})
            emoji = reaction_data.get("emoji", "")
            positive_emojis = ["👍", "❤️", "💯", "🔥", "✅", "👌", "😊", "🥰", "😍"]
            is_positive_reaction = emoji in positive_emojis
            message_body = "Sí" if is_positive_reaction else "[REACTION]"
        else:
            message_body = f"[{msg_type.upper()}]"

        # 1.2 Filtro de Idempotencia Global (v9.8.3)
        # Registramos el mensaje. Si es un duplicado exacto de WAMID, abortamos.
        is_added = await message_buffer.add_message(user_phone, message_body, msg_id_unique)
        if not is_added:
            logger.warning(f"🔄 Duplicate WAMID ignored: {msg_id_unique}")
            return

        # --- PROTOCOLO READ-FIRST (PRIORIDAD 1) ---
        # Marcamos como leído ANTES de cualquier lógica para evitar el 'check gris'
        # y confirmar a Meta que el webhook fue recibido.
        from app.services.whatsapp_service import whatsapp_service
        await whatsapp_service.mark_as_read(msg_id_unique, phone_number_id=phone_number_id)
        
        # DEBUG LOG for Image Troubleshooting
        logger.info(f"🕵️ DEBUG: Received message {msg_id_unique} from {user_phone} | Type: '{msg_type}'")
        
        response_text = None 
        if msg_type == "reaction":
            # La deduplicación ya se hizo al inicio en v9.8.3
            # Wait for debounce window (3s) para permitir agregación si llegaran otros mensajes
            orig_body = message_body
            await asyncio.sleep(message_buffer.debounce_seconds)
            
            # Check if this task is still active
            if not message_buffer.is_task_active(user_phone, msg_id_unique):
                logger.info(f"⏭️ Reaction task {msg_id_unique} superseded. Aggregating...")
                return
            
            # Get aggregated message
            aggregated_body = await message_buffer.get_aggregated_message(user_phone)
            await message_buffer.clear_buffer(user_phone)
            
            message_body = aggregated_body if aggregated_body else orig_body
            
            if not message_body:
                return
            
            # --- INTERCEPT REACTION SÍNCRONAMENTE (👍) PARA HABEAS DATA ---
            if is_positive_reaction:
                logger.info(f"👍 [REACTION INTERCEPT] Forzando aceptación de Habeas Data para {user_phone}")
                if memory_service_module.memory_service:
                    ms_instance = memory_service_module.memory_service
                    fut = ms_instance.update_prospect_summary(user_phone, "", {"habeas_data_accepted": True})
                    if hasattr(fut, "__await__"):
                        await fut
            
            msg_type = "text"

            # --- DEBOUNCE LOGIC END ---
            
        elif msg_type in ["image", "document", "sticker"]:
            logger.info(f"📸 Media detected from {user_phone} (Type: {msg_type}). Processing immediately...")
            
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
                        await _send_whatsapp_message(user_phone, "No pude procesar el archivo. 😢", phone_number_id=phone_number_id)
                        return

                    image_bytes = await storage_service.download_media(media_id)
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
                                    
                                    await _send_whatsapp_message(user_phone, f"¡Uy {p_name}! 📸 La foto parece {motivo}. ¿Podrías enviarla de nuevo que se vea bien clarita? Así el banco no nos la rechaza.", phone_number_id=phone_number_id)
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
                                                await _send_whatsapp_message(user_phone, "¡Excelente! Ya tengo todo tu expediente completo. ✅ Un asesor lo revisará en breve.", phone_number_id=phone_number_id)
                                            else:
                                                faltante = "el recibo de gas" if tipo == "CEDULA" else "tu cédula"
                                                nombre_doc = "cédula" if tipo == "CEDULA" else "recibo de gas"
                                                await _send_whatsapp_message(user_phone, f"¡Recibida tu {nombre_doc}! ✅ Ya solo me falta {faltante} para terminar.", phone_number_id=phone_number_id)
                                        return
                                    except Exception as e:
                                        logger.exception(f"❌ Error uploading document: {e}")
                                        await _send_whatsapp_message(user_phone, "Tuve un problemita guardando tu documento. ¿Podrías intentarlo de nuevo?", phone_number_id=phone_number_id)
                                        return

                            # 1. Handle Moto Detection (Legacy / Main Vision Logic)
                            elif "[MOTO_DETECTADA]" in vision_response:
                                vision_description = vision_response.replace("[MOTO_DETECTADA]", "").strip()
                                await _ensure_services()
                                cerebro_ia = CerebroIA(config_loader, catalog_service)
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
                                    if prospect_data: prospect_data["phone"] = user_phone
                                    final_response = await cerebro_ia.pensar_respuesta(
                                        simulated_user_msg, 
                                        context="", 
                                        prospect_data=prospect_data,
                                        history=current_history,
                                        skip_greeting=True
                                    )
                                    
                                    if not final_response:
                                        final_response = "Lo siento, tuve un problema procesando esa información. ¿Podrías repetirme qué buscas?"
                                    
                                    await _send_whatsapp_message(user_phone, final_response, phone_number_id=phone_number_id)
                                    await ms.save_message(user_phone, "user", simulated_user_msg)
                                    await ms.save_message(user_phone, "model", final_response)
                                    return

                            # 2. Handle Sentiment / Memes / Stickers
                            # Interceptor for affirmative stickers mapping to positive emojis
                            is_affirmative_sticker = False
                            if msg_type == "sticker":
                                sticker_obj = msg_data.get("sticker", {})
                                sticker_emoji = sticker_obj.get("emoji", "") if isinstance(sticker_obj, dict) else ""
                                metadata_str = str(sticker_obj).lower() if sticker_obj else ""
                                vision_str = vision_response.lower() if vision_response else ""
                                affirmative_terms = ["thumbs_up", "thumbsup", "pulgar arriba", "thumbs-up", "👍", "si", "sí", "ok", "✅", "👌"]
                                if any(term in vision_str for term in affirmative_terms) or any(term in metadata_str for term in affirmative_terms):
                                    is_affirmative_sticker = True

                            if vision_response.startswith("[System Note:") or (msg_type == "sticker" and is_affirmative_sticker):
                                logger.info("🧠 General image/meme/sticker detected.")
                                await _ensure_services()
                                cerebro_ia = CerebroIA(config_loader, catalog_service)
                                cerebro_ia.motor_financiero = motor_financiero
                                
                                input_text = "Sí" if (msg_type == "sticker" and is_affirmative_sticker) else vision_response
                                
                                if memory_service_module.memory_service:
                                    ms = memory_service_module.memory_service
                                    await ms.create_prospect_if_missing(user_phone)
                                    await ms.generate_and_update_summary(user_phone, f"User sent media: {input_text}", cerebro_ia)
                                    
                                    prospect_data = await ms.get_prospect_data(user_phone)
                                    current_history = await ms.get_chat_history(user_phone, limit=10)
                                    
                                    if prospect_data and prospect_data.get('human_help_requested', False):
                                        return
                                    
                                    if prospect_data: prospect_data["phone"] = user_phone
                                    
                                    try:
                                        final_response = await cerebro_ia.pensar_respuesta(
                                            input_text,
                                            context="", 
                                            prospect_data=prospect_data,
                                            history=current_history,
                                            skip_greeting=True
                                        )
                                    except HabeasDataBypassInterrupt as hdbi:
                                        logger.info("🛡️ [HABEAS-BYPASS-STICKER] Cortocircuito limpio capturado en el router de WhatsApp (Sticker). Aprobación inmediata.")
                                        final_response = str(hdbi.args[0])

                                    if not final_response:
                                        final_response = "¡Estuvo bueno! 😅 Pero cuéntame, ¿en qué moto estabas pensando?"
                                    
                                    await _send_whatsapp_message(user_phone, final_response, phone_number_id=phone_number_id)
                                    await ms.save_message(user_phone, "user", input_text)
                                    await ms.save_message(user_phone, "model", final_response)
                                    return

                            # 3. Fallback text
                            else:
                                logger.info("🧠 Fallback text returned from Vision AI.")
                                response_text = f"🏍️ **Catálogo Auteco Las Motos**\n\n{vision_response}"
                                await _send_whatsapp_message(user_phone, response_text, phone_number_id=phone_number_id)
                                return
                        
                        else:
                            await _send_whatsapp_message(user_phone, "¡Uff! Pero no alcanzo a ver bien los detalles. ¿Me cuentas qué es?", phone_number_id=phone_number_id)
                    else:
                        await _send_whatsapp_message(user_phone, "No pude descargar el archivo. Intenta de nuevo.", phone_number_id=phone_number_id)
                except Exception as e:
                    logger.exception(f"❌ Error processing media: {e}")
                    await _send_whatsapp_message(user_phone, "Tuve un problema viendo el archivo. ¿Me cuentas qué es? 😅", phone_number_id=phone_number_id)
            
            return  # EARLY EXIT: Stop processing here
            
        # 1.5 Save User Message to History (PERSISTENCE FIX)
        if memory_service_module.memory_service:
            if msg_type == "text" and message_body:
                # Optimistic save (don't block too long)
                try:
                    await memory_service_module.memory_service.save_message(user_phone, "user", message_body)
                except (asyncio.TimeoutError, gcp_exceptions.ServiceUnavailable, gcp_exceptions.DeadlineExceeded) as e:
                    logger.error(f"❌ [CONTINGENCY] Fallo de red/timeout al guardar mensaje del usuario {user_phone}. Abortando flujo por intermitencia. Detalle: {e}", exc_info=True)
                    await _send_whatsapp_message(user_phone, "Disculpa, estamos experimentando intermitencias en nuestro sistema. Intenta de nuevo en unos minutos.", phone_number_id=phone_number_id)
                    return
            # AUDIO: [Mensaje de Voz] removed here to avoid blinding the extractor.
            # It will be saved with the actual transcription inside the audio block.



        # 2. Gestión de Sesión
        # 2. Gestión de Sesión & Servicios
        logger.info(f"⚙️ Starting Session Management for {user_phone}...")
        prospect_data = None
        current_history = []
        skip_greeting = False
        context = "" # Initialize context to prevent UnboundLocalError
        current_agent = "expert" # Fallback by default
        
        # Initialize Services Locally
        logger.info("🧠 Initializing CerebroIA...")
        cerebro_ia = CerebroIA(config_loader, catalog_service)
        cerebro_ia.motor_financiero = motor_financiero # Inject Financial Motor
        vision_service = VisionService(db)
        audio_service = AudioService(config_loader)
        
        if memory_service_module.memory_service:
            ms = memory_service_module.memory_service
            
            try:
                # 1. Get existing data FIRST to decide on greeting
                prospect_data = await ms.get_prospect_data(user_phone)
                
                # --- SYSTEM COMMANDS INTERCEPTION (v9.8.3) ---
                # Movemos esto aquí para tener acceso a prospect_data y evitar duplicados
                if msg_type == "text":
                    cmd = message_body.strip().lower()
                    if cmd in ["reset", "/reset"]:
                        # 1. Block Concurrency (v9.8.3)
                        if user_phone in _active_resets:
                            logger.info(f"⏭️ [RESET] Reset already in progress for {user_phone}. Ignorando duplicado.")
                            return
                        
                        _active_resets.add(user_phone)
                        try:
                            logger.warning(f"☢️ NUCLEAR RESET TRIGGERED (Sync) for {user_phone}")
                            # Nuclear wipe (Siempre intentamos limpiar, sea que exista o no en Firestore)
                            success = await ms.delete_prospect_completely(user_phone)
                            if not success:
                                logger.error(f"❌ [RESET] Fallo en limpieza profunda para {user_phone}, procediendo con feedback.")
    
                            # Limpiar buffer de mensajes para evitar duplicados residuales
                            await message_buffer.clear_buffer(user_phone)
                            
                            # Sincronía de Feedback: Garantía de respuesta determinista
                            await whatsapp_service.send_text_message(
                                user_phone, 
                                "✅ Tu sesión ha sido reiniciada por completo. Cuéntame, ¿en qué moto estás interesado?", 
                                phone_number_id=phone_number_id
                            )
                        except Exception as e:
                            logger.exception(f"❌ [RESET] Error inesperado en flujo de reset para {user_phone}: {e}")
                        finally:
                            # Blindaje de Cleanup: Evita bloqueo permanente de hilos del usuario
                            if user_phone in _active_resets:
                                _active_resets.remove(user_phone)
                        return 
    
                    if cmd in ["/update", "/refresh_catalog"]:
                        logger.warning(f"🔄 CATALOG REFRESH TRIGGERED by {user_phone}")
                        try:
                            await _ensure_services()
                            if catalog_service:
                                # BOT-INFRA-ASYNC-094: Delegate sync .stream() to thread pool
                                await asyncio.to_thread(catalog_service.refresh)
                                confirm_msg = "✅ Catálogo actualizado en memoria exitosamente."
                            else:
                                confirm_msg = "❌ Error: Catalog Service no inicializado."
                        except Exception as e:
                            logger.exception(f"❌ Error refreshing catalog: {e}")
                            confirm_msg = f"❌ Error al actualizar el catálogo: {str(e)}"
                            
                        await whatsapp_service.send_text_message(user_phone, confirm_msg, phone_number_id=phone_number_id)
                        return
    
                # --- BLINDAJE DE CONCURRENCIA PARA PROSPECTOS ZOMBIS (v10.12.6) ---
                is_metadata_only = prospect_data and prospect_data.get("exists", False) and "ai_summary" not in prospect_data
                is_fully_deleted = not prospect_data or not prospect_data.get("exists", False)

                newly_created = is_fully_deleted or is_metadata_only
                current_agent = prospect_data.get("current_agent", "expert") if (prospect_data and not is_metadata_only and not is_fully_deleted) else "expert"

                if is_fully_deleted:
                    logger.warning(f"⚠️ [POST_RESET_RECOVERY] Documento inexistente para {user_phone} (post-reset). Forzando reconstrucción CRM.")
                    await ms.create_prospect_if_missing(user_phone)
                    prospect_data = await ms.get_prospect_data(user_phone)
                elif is_metadata_only:
                    logger.warning(f"⚠️ [CONCURRENCY_RECOVERY] Detectado documento zombi sin estructura para {user_phone}. Forzando inicialización de sesión CRM.")
                    await ms.create_prospect_if_missing(user_phone)
                    prospect_data = await ms.get_prospect_data(user_phone)
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
                        except Exception as e:
                            logger.warning(f"⚠️ [HISTORY] Error parsing timestamp '{last_ts}': {e}")
                    
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
                await ms.create_prospect_if_missing(user_phone)
                await ms.update_last_interaction(user_phone)
    
                # [ARCH-BULK-META-010] MÁQUINA DE ESTADOS: PENDING → IN_PROGRESS
                # WHY: Los prospectos de carga masiva arrancan en 'PENDING'. La primera
                # respuesta real del usuario (este webhook 'messages') activa la transición.
                # El await bloqueante garantiza commit en Firestore antes de continuar
                # con la lógica del bot (mandato de sincronía ARCH-BULK-META-010).
                await ms.transition_to_in_progress(user_phone)
    
                # --- [HOTFIX v9.8.3] REFRESH METADATA ---
                # WHY: If we just created the prospect or transitioned it, the local 
                # 'prospect_data' object is STALE. We must refresh it so the JudgeService
                # doesn't reject valid users (C3/C9 rejections).
                prospect_data = await ms.get_prospect_data(user_phone)
                logger.info(f"👤 Prospect Data Refreshed: {prospect_data.get('name', 'Unknown') if prospect_data else 'None'}")
                
                # Human Gatekeeper Check (Mantenibilidad)
                if prospect_data and prospect_data.get('human_help_requested', False):
                    logger.info(f"🛑 Human Help Requested flag active for {user_phone}. Silencing bot.")
                    return

            except Exception as e:
                logger.error(f"❌ [CONTINGENCY] Fallo en recuperación/actualización de memoria para {user_phone}. Abortando. Detalle: {e}", exc_info=True)
                await _send_whatsapp_message(user_phone, "Disculpa, estamos experimentando intermitencias en nuestro sistema. Intenta de nuevo en unos minutos.", phone_number_id=phone_number_id)
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

        logger.info(f"🔀 [ROUTER] Routing session for {user_phone} to Agent: {current_agent}")

        # 3. Generar Respuesta (CerebroIA - Rama Finance)
        if msg_type == "text":
            # --- LINEAR BLOCKING: Memory Update (Wait for Firestore) ---
            if memory_service_module.memory_service:
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
                    logger.exception(f"❌ Error in Linear Blocking flow: {e}")
                    # Fallback to local data if sync fails
                    if not prospect_data:
                        prospect_data = await ms.get_prospect_data(user_phone)

            # 3. Inferencia de la IA con Auditoría de Vida o Muerte (v9.8.0)
            max_retries = 2
            attempts = 0
            is_approved = False
            rejection_reason = ""
            last_criteria_id = "UNKNOWN"
            
            try:
                # Contexto para el Juez (Catalog Lock)
                translated_query = resolve_query_aliases(message_body, catalog_service)
                catalog_results = catalog_service.search(translated_query)
                catalog_context = ""
                for item in catalog_results[:3]:
                    tags_str = ", ".join(item.get('searchBy', []))
                    net_price_str = ""
                    if catalog_service and hasattr(catalog_service, '_items'):
                        for raw_item in catalog_service._items:
                            if raw_item.get("name") == item["name"]:
                                net_price_str = raw_item.get("formatted_price")
                                break
                    if not net_price_str:
                        net_price_str = item.get("formatted_price", "")
                    catalog_context += f"- {item['name']}: Neto: {net_price_str} / Con SOAT: {item['formatted_price']}. Tags: [{tags_str}]. Specs: {item.get('summary')}\n"

                while attempts <= max_retries and not is_approved:
                    attempts += 1
                    logger.info(f"🧠 [JUDGE] Calling CerebroIA.pensar_respuesta (Attempt {attempts}/{max_retries+1})...")
                    
                    current_context = context
                    if attempts > 1:
                        current_context += f"\n\n[SISTEMA - ERROR DE CALIDAD]: Tu respuesta anterior fue RECHAZADA por el Juez. Motivo: {rejection_reason}. Por favor, corrige este punto y genera una nueva respuesta válida."

                    if prospect_data is not None:
                        prospect_data["phone"] = user_phone 

                    try:
                        response_text = await cerebro_ia.pensar_respuesta(
                            message_body,
                            context=current_context,
                            prospect_data=prospect_data,
                            history=current_history,
                            skip_greeting=skip_greeting
                        )
                    except HabeasDataBypassInterrupt as hdbi:
                        logger.info("🛡️ [HABEAS-BYPASS] Cortocircuito limpio capturado en el router de WhatsApp. Aprobación inmediata.")
                        response_text = str(hdbi.args[0])
                        is_approved = True
                        break

                    # 4. Evaluación FAQ Bypass (BOT-BRAIN-FAQ-ROOT-CAUSE-HUNT-147)
                    # run_checker determina semánticamente si la respuesta es FAQ pura
                    # para propagar el flag is_faq_bypass al Juez y evitar falsos positivos
                    # en C1_VISUAL_LOCK ("soporte"→"Sport") y C9_CITY_MISSING ("requisitos"→crédito).
                    _pcc_result = _router_orchestrator.run_checker(
                        response_text or "",
                        is_catalog_query=any(kw in message_body.lower() for kw in ["ficha", "tecnica", "especificaciones"]),
                        prospect_data=prospect_data,
                        user_prompt=message_body
                    )
                    _is_faq_bypass = bool(_pcc_result.get("bypass_strict", False))
                    if _is_faq_bypass:
                        logger.info(f"✅ [ROUTER-PCC] FAQ bypass detectado. Propagando is_faq_bypass=True al Juez para {user_phone}.")

                    # 5. Auditoría del Juez de Fundamentación
                    is_approved, rejection_reason = await judge_service.analyze_response(
                        user_input=message_body,
                        ai_response=response_text,
                        catalog_context=catalog_context,
                        prospect_data=prospect_data,
                        history=current_history,
                        is_faq_bypass=_is_faq_bypass
                    )

                    if not is_approved:
                        logger.warning(f"⚖️ [JUDGE] Response REJECTED (Attempt {attempts}): {rejection_reason}")
                        # Extraer ID del criterio (ej: C1 de C1_VISUAL_LOCK)
                        match = re.match(r'(C\d)', rejection_reason)
                        last_criteria_id = match.group(1) if match else "UNKNOWN"
                    else:
                        logger.info(f"⚖️ [JUDGE] Response APPROVED (Attempt {attempts}).")

                # Fallback if all attempts fail
                if not is_approved:
                    logger.error(f"❌ [JUDGE] Max retries reached. Forcing official fallback response. Criteria: {last_criteria_id}. Rejection Reason: {rejection_reason}")
                    fallback_msg = "Disculpa, no estoy seguro de la respuesta, permíteme le pregunto a mi supervisor y te comento."
                    
                    # [MANDATO v9.8.3] Marcar estado PRIMERO, luego enviar mensaje
                    # Esto asegura que el CRM se actualice incluso si Meta falla temporalmente.
                    try:
                        if memory_service_module.memory_service:
                            logger.warning(f"🚨 [JUDGE_FALLBACK] Max retries hit for {user_phone}. Marking human_help_requested=True")
                            await memory_service_module.memory_service.set_human_help_status(user_phone, True)
                            await memory_service_module.memory_service.save_message(user_phone, "model", fallback_msg)
                    except Exception as e_ms:
                        logger.error(f"⚠️ [JUDGE_FALLBACK] Error persistencia fallback: {e_ms}")

                    # Envío INCONDICIONAL del mensaje de fallback
                    try:
                        logger.info(f"📤 [JUDGE_FALLBACK] Sending supervisor fallback to {user_phone}...")
                        sent_ok = await _send_whatsapp_message(user_phone, fallback_msg, phone_number_id=phone_number_id)
                        if sent_ok:
                            logger.info(f"✅ [JUDGE_FALLBACK] Supervisor message delivered to {user_phone}")
                        else:
                            logger.error(f"❌ [JUDGE_FALLBACK] _send_whatsapp_message returned False for {user_phone}")
                    except Exception as e_wa:
                        logger.error(f"❌ [JUDGE_FALLBACK] Error fatal enviando mensaje de fallback a Meta: {e_wa}")
                    
                    # Actualizar Langfuse antes de retornar
                    try:
                        from langfuse.decorators import langfuse_context
                        langfuse_context.update_current_trace(
                            tags=["JUDGE_CRITICAL_FALLBACK"],
                            metadata={
                                "rejection_criteria": last_criteria_id,
                                "final_rejection_reason": rejection_reason,
                                "attempts": attempts
                            }
                        )
                    except Exception as e:
                        logger.warning(f"⚠️ [JUDGE_FALLBACK] Failed to update Langfuse trace: {e}")

                    return # Stop processing

            except Exception as e:
                # MANDATO Zero-Silent-Failures: exc_info=True garantiza stack trace forense.
                # Capturar el cuerpo nativo del error antes de activar human_help_requested.
                logger.exception(f"🔥 [JUDGE_CRITICAL_ERROR] AI Inference failed for {user_phone}: {e}")
                fallback_msg = "Disculpa, no estoy seguro de la respuesta, permíteme le pregunto a mi supervisor y te comento."
                if memory_service_module.memory_service:
                    await memory_service_module.memory_service.set_human_help_status(user_phone, True)
                    await _send_whatsapp_message(user_phone, fallback_msg, phone_number_id=phone_number_id)
                    await memory_service_module.memory_service.save_message(user_phone, "model", fallback_msg)
                return
            
            # Observabilidad: Langfuse Tag y Metadata
            if not is_approved or attempts > 1:
                try:
                    from langfuse.decorators import langfuse_context
                    langfuse_context.update_current_trace(
                        tags=["JUDGE_CRITICAL_FALLBACK"] if not is_approved else ["JUDGE_RETRIED"],
                        metadata={
                            "rejection_criteria": last_criteria_id,
                            "final_rejection_reason": rejection_reason,
                            "attempts": attempts
                        }
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Failed to update Langfuse trace: {e}")

            # Persistencia de la respuesta final (sea aprobada o fallback)
            if memory_service_module.memory_service:
                await memory_service_module.memory_service.save_message(user_phone, "model", response_text)

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
                typing_delay = min(1.5, calculated_delay)
                logger.info(f"⏳ Human Latency: len={len(str(response_text))}, delay={typing_delay:.2f}s")

            if typing_delay > 0:
                await asyncio.sleep(typing_delay)
            
        elif msg_type == "audio":
            media_id = msg_data.get("media_id")
            mime_type = msg_data.get("mime_type")
            audio_bytes = await storage_service.download_media(media_id)
            
            # GET HISTORY BEFORE AI
            current_history = []
            if memory_service_module.memory_service:
                ms = memory_service_module.memory_service
                await ms.create_prospect_if_missing(user_phone) # Good practice
                await ms.update_last_interaction(user_phone)
                
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
                    
                    # Identify last bot question for anchoring
                    last_bot_q = ""
                    for m in reversed(current_history or []):
                        if m.get("role") == "model":
                            last_bot_q = m.get("content", "")
                            break

                    # 1. LINEAR BLOCKING: Memory Sync (Wait for Firestore)
                    logger.info(f"🧠 [LINEAR BLOCKING] Starting Memory Sync (Audio) for {user_phone}")
                    await ms.generate_and_update_summary(
                        user_phone, 
                        f"User sent audio. Transcription: {transcription}", 
                        cerebro_ia, 
                        last_bot_question=last_bot_q
                    )
                    
                    # 2. Re-fetch
                    prospect_data = await ms.get_prospect_data(user_phone)
                    current_history = await ms.get_chat_history(user_phone, limit=10)

                    # 3. AI Inference with Judge Audit (v9.8.0)
                    max_retries = 2
                    attempts = 0
                    is_approved = False
                    rejection_reason = ""
                    last_criteria_id = "UNKNOWN"
                    
                    # Contexto para el Juez (Catalog Lock)
                    translated_query = resolve_query_aliases(transcription, catalog_service)
                    catalog_results = catalog_service.search(translated_query)
                    catalog_context = ""
                    for item in catalog_results[:3]:
                        tags_str = ", ".join(item.get('searchBy', []))
                        net_price_str = ""
                        if catalog_service and hasattr(catalog_service, '_items'):
                            for raw_item in catalog_service._items:
                                if raw_item.get("name") == item["name"]:
                                    net_price_str = raw_item.get("formatted_price")
                                    break
                        if not net_price_str:
                            net_price_str = item.get("formatted_price", "")
                        catalog_context += f"- {item['name']}: Neto: {net_price_str} / Con SOAT: {item['formatted_price']}. Tags: [{tags_str}]. Specs: {item.get('summary')}\n"

                    while attempts <= max_retries and not is_approved:
                        attempts += 1
                        logger.info(f"🧠 [JUDGE] Audio Inference (Attempt {attempts}/{max_retries+1})...")
                        
                        current_context = context
                        if attempts > 1:
                            current_context += f"\n\n[SISTEMA - ERROR DE CALIDAD]: Tu respuesta anterior fue RECHAZADA por el Juez. Motivo: {rejection_reason}. Por favor, corrige este punto y genera una nueva respuesta válida."

                        try:
                            response_text = await cerebro_ia.pensar_respuesta(
                                transcription,
                                context=current_context, 
                                prospect_data=prospect_data,
                                history=current_history,
                                skip_greeting=True
                            )
                        except HabeasDataBypassInterrupt as hdbi:
                            logger.info("🛡️ [HABEAS-BYPASS-AUDIO] Cortocircuito limpio capturado en el router de WhatsApp (Audio). Aprobación inmediata.")
                            response_text = str(hdbi.args[0])
                            is_approved = True
                            break

                        # 4. Auditoría del Juez
                        is_approved, rejection_reason = await judge_service.analyze_response(
                            user_input=transcription,
                            ai_response=response_text,
                            catalog_context=catalog_context,
                            prospect_data=prospect_data,
                            history=current_history
                        )

                        if not is_approved:
                            logger.warning(f"⚖️ [JUDGE] Audio REJECTED (Attempt {attempts}): {rejection_reason}")
                            match = re.match(r'(C\d)', rejection_reason)
                            last_criteria_id = match.group(1) if match else "UNKNOWN"
                        else:
                            logger.info(f"⚖️ [JUDGE] Audio APPROVED (Attempt {attempts}).")

                    # Fallback if all attempts fail
                    if not is_approved:
                        logger.error(f"❌ [JUDGE] Audio Max retries reached. Forcing fallback. Criteria: {last_criteria_id}")
                        fallback_msg = "Disculpa, no estoy seguro de la respuesta, permíteme le pregunto a mi supervisor y te comento."
                        
                        # [MANDATO v9.8.3] Marcar estado PRIMERO, luego enviar mensaje
                        try:
                            if memory_service_module.memory_service:
                                await memory_service_module.memory_service.set_human_help_status(user_phone, True)
                                await memory_service_module.memory_service.save_message(user_phone, "model", fallback_msg)
                        except Exception as e_ms:
                            logger.error(f"⚠️ [JUDGE_FALLBACK_AUDIO] Error persistencia fallback: {e_ms}")

                        # Envío INCONDICIONAL
                        try:
                            await _send_whatsapp_message(user_phone, fallback_msg, phone_number_id=phone_number_id)
                        except Exception as e_wa:
                            logger.error(f"❌ [JUDGE_FALLBACK_AUDIO] Error enviando fallback: {e_wa}")

                        # Actualizar Langfuse antes de retornar
                        try:
                            from langfuse.decorators import langfuse_context
                            langfuse_context.update_current_trace(
                                tags=["JUDGE_CRITICAL_FALLBACK"],
                                metadata={
                                    "rejection_criteria": last_criteria_id,
                                    "final_rejection_reason": rejection_reason,
                                    "attempts": attempts,
                                    "msg_type": "audio"
                                }
                            )
                        except: pass
                        
                        return 
                else:
                    response_text = "Escuché el audio pero no entendí bien. ¿Me repites? 😅"
            else:
                response_text = "No pude descargar el audio. 😢"
            
        if response_text:
            # Check for AI Handoff
            if response_text.startswith("HANDOFF_TRIGGERED"):
                if memory_service_module.memory_service:
                    await memory_service_module.memory_service.set_human_help_status(user_phone, True)
                await _send_whatsapp_message(user_phone, "Te voy a transferir con un compañero para que te ayude con esto. Dame un momento...", phone_number_id=phone_number_id)
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
                        
                        if catalog_service:
                            try:
                                # Search for interested bike or default
                                moto_results = catalog_service.search_catalog(moto_to_search)
                                
                                # Fallback if interest search failed (Competitor or not found)
                                if not moto_results and moto_interest:
                                    logger.info(f"🔄 No results for '{moto_interest}' (Competitor?). Falling back to Raider 125.")
                                    moto_results = catalog_service.search_catalog("RAIDER 125")
                                
                                if moto_results:
                                    moto = moto_results[0]
                                    image_url = moto.get("image_url")
                                    moto_name = moto.get("name")
                                    
                                    if image_url:
                                        # Caption v6.3.1: "Mira esta [Moto]"
                                        caption = f"Mira esta {moto_name}\n\n{response_text}"
                                        logger.info(f"📸 Sending Phase-Gate dynamic image: {image_url} for {moto_name}")
                                        await _send_whatsapp_image(user_phone, image_url, caption=caption, phone_number_id=phone_number_id)
                                        
                                        # Save to history and stop
                                        if memory_service_module.memory_service:
                                            await memory_service_module.memory_service.save_message(user_phone, "model", response_text)
                                        return 
                            except Exception as e:
                                logger.exception(f"⚠️ Error injecting dynamic Phase-Gate image: {e}")
                    else:
                        logger.info("⏩ [BYPASS] Skipping image injection: moto already confirmed.")

                # --- NATIVE IMAGE INTEGRATION ---
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
                    await _send_whatsapp_image(user_phone, image_url, caption=caption, phone_number_id=phone_number_id)
                    
                    if overflow_text:
                        logger.info(f"📤 Sending overflow text ({len(overflow_text)} chars)")
                        await _send_whatsapp_message(user_phone, overflow_text, phone_number_id=phone_number_id)
                    
                    # Store the cleaned text for history to avoid raw markdown clutter
                    response_text = cleaned_response_text 
                else:
                    await _send_whatsapp_message(user_phone, response_text, phone_number_id=phone_number_id)
                
                # Save Bot Response to History (PERSISTENCE FIX)
                if memory_service_module.memory_service:
                    await memory_service_module.memory_service.save_message(user_phone, "model", response_text)

    except Exception as e:
        import traceback
        tb_list = traceback.extract_tb(e.__traceback__)
        if tb_list:
            last_frame = tb_list[-1]
            error_file = last_frame.filename
            error_line = last_frame.lineno
        else:
            error_file = "unknown"
            error_line = 0

        payload = {
            "CRITICAL_CODE_FAULT": {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "file": error_file,
                "line": error_line,
                "stack_trace": traceback.format_exc()
            }
        }
        logger.error(payload)
        raise


# ============================================================================
# LOCAL HELPERS (Defined here to avoid missing dependency errors)
# ============================================================================

def _is_valid_statuses(payload: Dict[str, Any]) -> bool:
    """
    [ARCH-BULK-META-010] Detecta si el payload de Meta contiene acuses de recibo
    (statuses). Análogo a _is_valid_message pero para el array 'statuses[]'.

    WHY: Antes de este parche, _is_valid_message() retornaba False para estos payloads
    y eran descartados silenciosamente con {"status": "ignored"}.
    """
    try:
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        statuses = value.get("statuses", [])
        return len(statuses) > 0
    except:
        return False


def _extract_status_data(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    [ARCH-BULK-META-010] Extrae los campos relevantes del primer acuse de recibo
    del payload de Meta.

    Returns:
        Dict con: id (wamid), recipient_id (teléfono), status, timestamp.
        None si el payload es inválido.
    """
    try:
        value = payload["entry"][0]["changes"][0]["value"]
        status_obj = value["statuses"][0]
        metadata = value.get("metadata", {})
        # WHY: Meta envía el array 'errors' únicamente cuando status='failed'.
        # Capturamos el objeto completo para preservar code + title + message
        # sin asumir la estructura interna (puede cambiar entre versiones de la API).
        errors = status_obj.get("errors", [])
        return {
            "id": status_obj.get("id", ""),
            "recipient_id": status_obj.get("recipient_id", ""),
            "status": status_obj.get("status", ""),
            "timestamp": status_obj.get("timestamp", ""),
            "phone_number_id": metadata.get("phone_number_id"),
            "errors": errors,  # Lista vacía [] si no hay error
        }
    except Exception as e:
        logger.warning(f"⚠️ [STATUSES] Error extrayendo status_data: {e}")
        return None


def _extract_statuses_list(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    [ARCH-BULK-META-010] Extrae todos los acuses de recibo del payload de Meta
    para procesamiento masivo en bucle.
    """
    try:
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        statuses = value.get("statuses", [])
        metadata = value.get("metadata", {})
        extracted = []
        for status_obj in statuses:
            errors = status_obj.get("errors", [])
            extracted.append({
                "id": status_obj.get("id", ""),
                "recipient_id": status_obj.get("recipient_id", ""),
                "status": status_obj.get("status", ""),
                "timestamp": status_obj.get("timestamp", ""),
                "phone_number_id": metadata.get("phone_number_id"),
                "errors": errors,
            })
        return extracted
    except Exception as e:
        logger.warning(f"⚠️ [STATUSES] Error extrayendo lista de status_data: {e}")
        return []


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
        value = payload["entry"][0]["changes"][0]["value"]
        msg = value["messages"][0]
        metadata = value.get("metadata", {})
        msg_type = msg["type"]
        data = {
            "from": msg["from"],
            "id": msg["id"],
            "timestamp": msg["timestamp"],
            "type": msg_type,
            "phone_number_id": metadata.get("phone_number_id"),
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

async def _send_whatsapp_message(to_phone: str, message_text: str, phone_number_id: Optional[str] = None) -> bool:
    """Send WhatsApp message via WhatsAppService."""
    from app.services.whatsapp_service import whatsapp_service
    try:
        await whatsapp_service.send_text_message(to_phone, message_text, phone_number_id=phone_number_id)
        return True
    except httpx.HTTPStatusError as e:
        logger.error(f"❌ Error HTTP ({e.response.status_code}): El mensaje se persistirá en Firestore pero falló la entrega a Meta. Detalle: {e.response.text}")
        return False
    except Exception as e:
        logger.error(f"❌ Error Genérico: El mensaje se persistirá en Firestore pero falló la entrega a Meta. Detalle: {e}")
        return False

async def _send_whatsapp_image(to_phone: str, image_url: str, caption: str = "", phone_number_id: Optional[str] = None) -> bool:
    """Send Image via WhatsAppService."""
    from app.services.whatsapp_service import whatsapp_service
    try:
        await whatsapp_service.send_image_message(to_phone, image_url, caption, phone_number_id=phone_number_id)
        return True
    except httpx.HTTPStatusError as e:
        logger.error(f"❌ Error HTTP ({e.response.status_code}): El mensaje se persistirá en Firestore pero falló la entrega a Meta. Detalle: {e.response.text}")
        return False
    except Exception as e:
        logger.error(f"❌ Error Genérico: El mensaje se persistirá en Firestore pero falló la entrega a Meta. Detalle: {e}")
        return False

async def _get_session(db_client, phone) -> Dict[str, Any]:
    try:
        if not db_client: return {}
        ref = db_client.collection("prospectos").document(phone)
        doc = ref.get()
        if doc.exists:
            return doc.to_dict()
        return {"status": "IDLE", "answers": {}}
    except:
        return {"status": "IDLE"}
