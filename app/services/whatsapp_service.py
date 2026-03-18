"""
WhatsApp Service - Interface with Meta WhatsApp Graph API
==========================================================
Handles outgoing messages, media, and status updates (read receipts).
"""

import logging
import httpx
from typing import Optional, Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)

class WhatsAppService:
    """
    Service to interact with the WhatsApp Business API.
    """
    
    def __init__(self):
        self.token = settings.whatsapp_token
        self.phone_number_id = settings.phone_number_id
        self.base_url = f"https://graph.facebook.com/v18.0/{self.phone_number_id}"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    async def send_text_message(self, to: str, text: str, reply_to_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Sends a text message to a WhatsApp user.
        """
        url = f"{self.base_url}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": True, "body": text},
        }
        
        if reply_to_id:
            payload["context"] = {"message_id": reply_to_id}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=self.headers, json=payload, timeout=10.0)
                response.raise_for_status()
                data = response.json()
                logger.info(f"📤 Text message sent to {to} | Message ID: {data.get('messages', [{}])[0].get('id')}")
                return data
        except Exception as e:
            logger.error(f"❌ Error sending text message to {to}: {e}")
            raise

    async def mark_as_read(self, msg_id: str) -> bool:
        """
        Marks a specific message as read (Blue check).
        """
        url = f"{self.base_url}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": msg_id,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=self.headers, json=payload, timeout=10.0)
                response.raise_for_status()
                logger.debug(f"👁️ Message {msg_id} marked as read")
                return True
        except Exception as e:
            logger.error(f"❌ Error marking message {msg_id} as read: {e}")
            return False

    async def send_image_message(self, to: str, image_url: str, caption: Optional[str] = None) -> Dict[str, Any]:
        """
        Sends an image message via URL.
        """
        url = f"{self.base_url}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "image",
            "image": {"link": image_url},
        }
        
        if caption:
            payload["image"]["caption"] = caption

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=self.headers, json=payload, timeout=10.0)
                response.raise_for_status()
                data = response.json()
                logger.info(f"📸 Image message sent to {to}")
                return data
        except Exception as e:
            logger.error(f"❌ Error sending image message to {to}: {e}")
            raise

# Singleton instance
whatsapp_service = WhatsAppService()
