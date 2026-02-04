"""
WhatsApp Webhook Router
Handles Meta WhatsApp webhook verification and message reception.
"""

import logging
from typing import Dict, Any

from fastapi import APIRouter, Request, Query, HTTPException

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["WhatsApp"])


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
async def receive_message(request: Request) -> Dict[str, str]:
    """
    WhatsApp message reception endpoint.
    
    Meta sends POST requests with message data to this endpoint.
    Phase 1: We just log the payload and return 200 OK.
    
    Args:
        request: FastAPI request object containing the webhook payload
        
    Returns:
        Success confirmation
    """
    try:
        # Parse the JSON payload
        payload = await request.json()
        
        logger.info("📨 WhatsApp message received")
        logger.info(f"Payload: {payload}")
        
        # Phase 1: Just log and acknowledge
        # Future phases will process the message and trigger bot logic
        
        return {"status": "received"}
        
    except Exception as e:
        logger.error(f"❌ Error processing webhook: {str(e)}")
        # Return 200 anyway to prevent Meta from retrying
        return {"status": "error", "message": str(e)}
