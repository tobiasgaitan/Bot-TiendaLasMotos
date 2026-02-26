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

logger = logging.getLogger(__name__)

# ============================================================================
# SECURITY CONFIGURATION
# ============================================================================
# Simple API key authentication for admin operations
# TODO: Move to environment variable for production
ADMIN_API_KEY = "moto_master_2026"

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
        
        prospectos_ref = db.collection("prospectos")
        
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
            "celular": normalized_phone,
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
    
    if x_admin_api_key != ADMIN_API_KEY:
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

@router.post("/sync-prompts")
async def sync_prompts(
    x_admin_api_key: Optional[str] = Header(None, alias="X-Admin-API-Key")
):
    """
    Force synchronize the System Instruction from code to Firestore Config.
    This resolves branding issues where Firestore overrides code changes.
    """
    if not x_admin_api_key or x_admin_api_key != ADMIN_API_KEY:
        logger.warning("🔒 Unauthorized attempt to sync prompts")
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    try:
        from app.core.prompts import JUAN_PABLO_SYSTEM_INSTRUCTION
        db = firestore.Client()
        doc_ref = db.collection("configuracion").document("juan_pablo_personality")
        doc_ref.set({
            "system_instruction": JUAN_PABLO_SYSTEM_INSTRUCTION,
            "updated_at": firestore.SERVER_TIMESTAMP
        }, merge=True)
        
        logger.info("✅ Admin API: Successfully synchronized JUAN_PABLO_SYSTEM_INSTRUCTION to Firestore")
        return {"success": True, "message": "System Instruction synced to Firestore successfully."}
    except Exception as e:
        logger.error(f"❌ Admin API: Failed to sync prompts to Firestore: {str(e)}", exc_info=True)
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
        db.collection("prospectos").limit(1).get()
        firestore_available = True
    except Exception as e:
        logger.error(f"❌ Admin health check: Firestore unavailable: {str(e)}")
    
    return {
        "status": "healthy",
        "service": "Admin API",
        "firestore_available": firestore_available,
        "note": "Self-sufficient with lazy initialization"
    }
