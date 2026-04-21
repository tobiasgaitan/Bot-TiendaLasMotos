"""
Admin API Router
Provides administrative endpoints for managing bot behavior remotely.

DESIGN: Self-sufficient with lazy initialization.
Does NOT rely on global memory_service to avoid 503 errors during startup.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Header, Body
from pydantic import BaseModel
from google.cloud import firestore

from app.core.config import settings

logger = logging.getLogger(__name__)

# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class ResetHandoffRequest(BaseModel):
    """Request model for handoff reset endpoint."""
    phone: str
    status: bool
    
    class Config:
        json_schema_extra = {
            "example": {
                "phone": "573192564288",
                "status": False
            }
        }


class ResetHandoffResponse(BaseModel):
    """Response model for handoff reset endpoint."""
    success: bool
    message: str
    phone: str
    status: bool


class CampaignRequest(BaseModel):
    """Request model for mass campaign start."""
    template_a: str
    template_b: str
    language: str
    limit: int = 50

    class Config:
        json_schema_extra = {
            "example": {
                "template_a": "reactivacion_v1_a",
                "template_b": "reactivacion_v1_b",
                "language": "es_CO",
                "limit": 10
            }
        }


class CampaignResponse(BaseModel):
    """Response model for campaign status."""
    success: bool
    processed: int
    variants: dict
    errors: list = []


# ============================================================================
# ROUTER SETUP
# ============================================================================

router = APIRouter()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _set_human_help_status_direct(phone_number: str, status: bool) -> None:
    """
    Set the human_help_requested flag for a prospect in Firestore.
    
    This is a self-sufficient implementation that creates its own
    Firestore client and doesn't rely on global services.
    
    Args:
        phone_number: Phone number to update (e.g., "573192564288", "+573192564288", "3192564288")
        status: True to enable human handoff mode (bot muted), False to resume bot
    
    Raises:
        Exception: If Firestore operation fails
    """
    try:
        from app.core.utils import PhoneNormalizer
        
        # Initialize Firestore client (self-sufficient)
        db = firestore.Client()
        
        # Normalize input
        normalized_phone = PhoneNormalizer.normalize(phone_number)
        
        logger.info(
            f"🔧 Admin API: Setting human_help_requested={status} | "
            f"Input: {phone_number} | Normalizado (ID): {normalized_phone}"
        )
        
        prospectos_ref = db.collection(settings.firestore_collection)
        
        # ATTEMPT 1: Direct document ID lookup
        doc_ref = prospectos_ref.document(normalized_phone)
        doc = doc_ref.get()
        
        if doc.exists:
            doc_ref.update({
                "human_help_requested": status,
                "updated_at": firestore.SERVER_TIMESTAMP
            })
            logger.info(
                f"✅ Admin API: Updated human_help_requested={status} for {normalized_phone}"
            )
            return
        
        # Fallback: Query by field
        query = prospectos_ref.where("celular", "==", normalized_phone).limit(1)
        docs = query.get()
        
        if docs:
            docs[0].reference.update({
                "human_help_requested": status,
                "updated_at": firestore.SERVER_TIMESTAMP
            })
            logger.info(
                f"✅ Admin API: Updated human_help_requested={status} for {normalized_phone} (Legacy Query)"
            )
            return
        
        # No existing document found - create new one
        logger.warning(
            f"⚠️ Admin API: No existing prospect found for {phone_number}, creating new document"
        )
        
        # Use normalized phone as document ID
        new_doc_ref = prospectos_ref.document(normalized_phone)
        new_doc_ref.set({
            "celular": f"+57{normalized_phone}",
            "human_help_requested": status,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP
        })
        
        logger.info(
            f"✅ Admin API: Created new prospect with human_help_requested={status} for {normalized_phone}"
        )
    except Exception as e:
        logger.error(f"❌ Admin API: Error setting human_help_status: {str(e)}", exc_info=True)
        raise


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================

@router.post("/reset-handoff", response_model=ResetHandoffResponse)
async def reset_handoff(
    request: ResetHandoffRequest = Body(...),
    x_admin_api_key: Optional[str] = Header(None, alias="X-Admin-API-Key")
) -> ResetHandoffResponse:
    """
    Reset the human handoff flag for a specific user.
    
    This endpoint allows the Admin Panel to remotely control the bot's
    mute status for individual users. When status is set to False, the
    bot will resume responding to messages from that user.
    
    DESIGN: Self-sufficient with lazy Firestore initialization.
    Does NOT rely on global memory_service to avoid 503 errors.
    
    Args:
        request: Request body containing phone number and desired status
        x_admin_api_key: API key for authentication (header)
    
    Returns:
        Success response with updated status
        
    Raises:
        HTTPException: 401 if API key is missing or invalid
        HTTPException: 500 if Firestore operation fails
        
    Example:
        POST /api/admin/reset-handoff
        Headers: X-Admin-API-Key: moto_master_2026
        Body: {"phone": "573192564288", "status": false}
    """
    # ========================================================================
    # AUTHENTICATION
    # ========================================================================
    if not x_admin_api_key:
        logger.warning("🔒 Admin API call without API key")
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Provide X-Admin-API-Key header."
        )
    
    if x_admin_api_key != settings.admin_api_key:
        logger.warning(f"🔒 Admin API call with invalid API key: {x_admin_api_key[:10]}...")
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    
    # ========================================================================
    # EXECUTE HANDOFF RESET (SELF-SUFFICIENT)
    # ========================================================================
    try:
        logger.info(
            f"🔧 Admin API: Resetting handoff for {request.phone} | "
            f"Setting status to {request.status}"
        )
        
        # Initialize Firestore and update flag (self-sufficient)
        _set_human_help_status_direct(request.phone, request.status)
        
        # Prepare success response
        status_text = "muted (human mode)" if request.status else "active (bot responding)"
        message = f"Bot status for {request.phone} set to {status_text}"
        
        logger.info(f"✅ Admin API: {message}")
        
        return ResetHandoffResponse(
            success=True,
            message=message,
            phone=request.phone,
            status=request.status
        )
        
    except Exception as e:
        logger.error(
            f"❌ Admin API: Failed to reset handoff for {request.phone}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update handoff status: {str(e)}"
        )



@router.post("/refresh-config")
async def refresh_config(
    x_admin_api_key: Optional[str] = Header(None, alias="X-Admin-API-Key")
):
    """
    Force-reload the in-memory ConfigLoader cache from Firestore.

    SECURITY: Protected by X-Admin-API-Key header (same as all admin endpoints).
    
    WHY THIS EXISTS:
    ConfigLoader is a Singleton that caches all config (system_instruction,
    routing_rules, catalog_config) in memory at startup. In a horizontally
    scaled Cloud Run environment, warm instances keep stale config in memory
    even after the Firestore document is patched.
    
    Hitting this endpoint forces the running instance to drop its cache and
    re-read all configuration from Firestore, without requiring a full redeploy.

    USAGE (after running scripts/patch_prompt.py):
        curl -X POST https://<your-service-url>/api/admin/refresh-config \\
             -H "X-Admin-API-Key: moto_master_2026"

    Returns:
        200: Config reloaded successfully, with a summary of what was loaded.
        401: Invalid or missing API key.
        500: ConfigLoader unavailable or Firestore read failed.
    """
    # ========================================================================
    # AUTHENTICATION (fail-closed — reject all without valid key)
    # ========================================================================
    if not x_admin_api_key:
        logger.warning("🔒 Unauthorized refresh-config attempt: missing API key")
        raise HTTPException(status_code=401, detail="Missing API key. Provide X-Admin-API-Key header.")
    
    if x_admin_api_key != settings.admin_api_key:
        logger.warning(f"🔒 Unauthorized refresh-config attempt: invalid key")
        raise HTTPException(status_code=401, detail="Invalid API key")

    # ========================================================================
    # CACHE INVALIDATION
    # ========================================================================
    try:
        from app.core.config_loader import ConfigLoader

        # Retrieve the existing Singleton instance (no args = reuse existing)
        # If the Singleton was never initialized (edge case), this will raise —
        # which is correct: we can't refresh a cache that was never populated.
        config_loader = ConfigLoader()

        logger.info("🔄 Admin API: Force-refreshing ConfigLoader Singleton cache from Firestore...")
        config_loader.refresh()

        # Build a summary of what was reloaded for the operator
        personality = config_loader.get_juan_pablo_personality()
        instruction_preview = personality.get("system_instruction", "")[:120] + "..."

        logger.info("✅ Admin API: ConfigLoader cache successfully refreshed")

        return {
            "status": "success",
            "message": "ConfigLoader cache reloaded from Firestore. This instance is now serving the latest configuration.",
            "reloaded": {
                "model_version": personality.get("model_version"),
                "instruction_preview": instruction_preview,
            }
        }

    except Exception as e:
        logger.error(f"❌ Admin API: Failed to refresh ConfigLoader: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh config: {str(e)}"
        )


@router.post("/campaign/start", response_model=CampaignResponse)
async def start_campaign(
    request: CampaignRequest = Body(...),
    x_admin_api_key: Optional[str] = Header(None, alias="X-Admin-API-Key")
):
    """
    Orchestrator for Meta Template mass sending with A/B testing and 
    Greeting Bounce mitigation via synchronous ghost history injection.
    """
    # 1. AUTHENTICATION
    if not x_admin_api_key or x_admin_api_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        from app.services.whatsapp_service import whatsapp_service
        from app.services.memory_service import memory_service
        from app.core.utils import PhoneNormalizer

        db = firestore.AsyncClient() # Use AsyncClient for better performance in loops
        prospectos_ref = db.collection(settings.firestore_collection)
        
        # Query prospects with status 'PENDING'
        logger.info(f"Buscando prospectos en la colección {settings.firestore_collection} con estado PENDING")
        query = prospectos_ref.where("status", "==", "PENDING").limit(request.limit)
        docs = await query.get()
        
        processed_count = 0
        variants_count = {"a": 0, "b": 0}
        errors = []

        for i, doc in enumerate(docs):
            prospect_data = doc.to_dict()
            raw_phone = prospect_data.get("celular", "")
            to_phone = PhoneNormalizer.to_international(raw_phone or doc.id)
            
            if not to_phone:
                logger.error(f"❌ Documento {doc.id} no posee campo celular. Omitiendo.")
                continue
            
            # A/B Logic (50/50 split)
            variant = "a" if i % 2 == 0 else "b"
            template_to_use = request.template_a if variant == "a" else request.template_b
            
            # Mapping Variables
            prospect_name = prospect_data.get("nombre", "Cliente")
            moto_model = prospect_data.get("moto_interes", "la moto de tus sueños")
            
            # Componentes posicionales para la plantilla contactos_impulsa
            components = [prospect_name, moto_model]
            
            try:
                # [CRITICAL: GREETING BOUNCE FIX & PERSISTENCE FIRST] 
                # Synchronous injection of ghost history to skip greeting detector in whatsapp.py
                # This ensures that when the user replies, current_history > 1
                try:
                    await memory_service.save_message(
                        to_phone, 
                        "model", 
                        f"[SISTEMA: Campaña de Reactivación Enviada - Variante {variant.upper()}]",
                        blocking=True
                    )
                except Exception as db_err:
                    logger.error(f"❌ Error persisting campaign history for documento {doc.id} (to_phone: {to_phone}): {str(db_err)}")
                    errors.append({"doc_id": doc.id, "to_phone": to_phone, "error": f"Firestore Error: {str(db_err)}"})
                    continue

                # [TRANSPORT] Send Meta Template
                await whatsapp_service.send_template_message(
                    to_phone=to_phone, 
                    template_name=template_to_use,
                    components=components,
                    language_code=request.language
                )
                
                # [ARCH-BULK-META-010] Update Firestore Document.
                # WHY: El campo 'status' NO se actualiza aquí.
                # El prospecto permanece en 'PENDING' hasta recibir la primera
                # respuesta real del usuario. La transición PENDING→IN_PROGRESS
                # ocurre en _handle_message_background() (whatsapp.py) cuando
                # llega el webhook de tipo 'messages'.
                await doc.reference.update({
                    "ab_template_sent": f"variante_{variant}",
                    "template_timestamp": firestore.SERVER_TIMESTAMP
                })
                
                processed_count += 1
                variants_count[variant] += 1
                
            except Exception as e:
                logger.error(f"❌ Error processing prospect {doc.id} (to_phone: {to_phone}): {str(e)}")
                errors.append({"doc_id": doc.id, "to_phone": to_phone, "error": str(e)})

        return CampaignResponse(
            success=True,
            processed=processed_count,
            variants=variants_count,
            errors=errors
        )

    except Exception as e:
        logger.error(f"💥 Critical error in campaign orchestrator: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/health")
async def admin_health_check():
    """
    Health check endpoint for admin API.
    
    Returns:
        Status information about admin API availability
    """
    # Test Firestore connectivity
    firestore_available = False
    try:
        db = firestore.Client()
        # Quick test query
        db.collection(settings.firestore_collection).limit(1).get()
        firestore_available = True
    except Exception as e:
        logger.error(f"❌ Admin health check: Firestore unavailable: {str(e)}")
    
    return {
        "status": "healthy",
        "service": "Admin API",
        "firestore_available": firestore_available,
        "note": "Self-sufficient with lazy initialization",
        "audit_v702": "verified_campaign_orchestrator_physics"
    }
