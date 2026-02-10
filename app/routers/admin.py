"""
Admin API Router
Provides administrative endpoints for managing bot behavior remotely.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Header, Body
from pydantic import BaseModel

# Import memory service from global scope
from app.services.memory_service import memory_service

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
    
    Args:
        request: Request body containing phone number and desired status
        x_admin_api_key: API key for authentication (header)
    
    Returns:
        Success response with updated status
        
    Raises:
        HTTPException: 401 if API key is missing or invalid
        HTTPException: 503 if memory service is unavailable
        HTTPException: 500 if update operation fails
        
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
    # VALIDATION
    # ========================================================================
    if not memory_service:
        logger.error("❌ Memory service not available")
        raise HTTPException(
            status_code=503,
            detail="Memory service not available. Bot may be starting up."
        )
    
    # ========================================================================
    # EXECUTE HANDOFF RESET
    # ========================================================================
    try:
        logger.info(
            f"🔧 Admin API: Resetting handoff for {request.phone} | "
            f"Setting status to {request.status}"
        )
        
        # Call memory service to update the flag
        memory_service.set_human_help_status(request.phone, request.status)
        
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


@router.get("/health")
async def admin_health_check():
    """
    Health check endpoint for admin API.
    
    Returns:
        Status information about admin API availability
    """
    return {
        "status": "healthy",
        "service": "Admin API",
        "memory_service_available": memory_service is not None
    }
