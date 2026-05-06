"""
WhatsApp Service - Interface with Meta WhatsApp Graph API
==========================================================
Handles outgoing messages, media, and status updates (read receipts).
"""

import logging
import httpx
from typing import Optional, Dict, Any
from app.core.config import settings
from app.core.utils import PhoneNormalizer

logger = logging.getLogger(__name__)

class WhatsAppService:
    """
    Service to interact with the WhatsApp Business API.
    """
    
    def __init__(self):
        self.token = settings.whatsapp_token
        self.phone_number_id = settings.phone_number_id
        self.base_url = f"https://graph.facebook.com/{settings.whatsapp_api_version}/{self.phone_number_id}"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    async def send_text_message(self, to: str, text: str, reply_to_id: Optional[str] = None, phone_number_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Sends a text message to a WhatsApp user.
        """
        # 1. Normalización Atómica (Protocolo Meta)
        to = PhoneNormalizer.normalize(to).lstrip("+")
        
        target_id = phone_number_id or self.phone_number_id
        url = f"https://graph.facebook.com/{settings.whatsapp_api_version}/{target_id}/messages"
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
            logger.debug(f"📤 Enviando payload a Meta: {payload}")
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=self.headers, json=payload, timeout=10.0)
                if response.status_code >= 400:
                    logger.error(f"❌ Error Meta API ({response.status_code}): {response.text}")
                response.raise_for_status()
                data = response.json()
                logger.info(f"✅ Mensaje enviado a {to} | ID: {data.get('messages', [{}])[0].get('id')}")
                return data
        except httpx.HTTPStatusError as e:
            raw_response = e.response.text
            logger.error(f"❌ HTTP Error en send_text_message para Destino Final Normalizado: {to} ({e.response.status_code}): {raw_response}")
            raise RuntimeError(f"Meta API Error ({e.response.status_code}): {raw_response}") from e
        except Exception as e:
            logger.error(f"💥 Error crítico en send_text_message para {to}: {str(e)}")
            raise

    async def mark_as_read(self, msg_id: str, phone_number_id: Optional[str] = None) -> bool:
        """
        Marks a specific message as read (Blue check).
        """
        target_id = phone_number_id or self.phone_number_id
        url = f"https://graph.facebook.com/{settings.whatsapp_api_version}/{target_id}/messages"
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

    async def send_image_message(self, to: str, image_url: str, caption: Optional[str] = None, phone_number_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Sends an image message via URL.
        """
        # 1. Normalización Atómica (Protocolo Meta)
        to = PhoneNormalizer.normalize(to).lstrip("+")
        
        target_id = phone_number_id or self.phone_number_id
        url = f"https://graph.facebook.com/{settings.whatsapp_api_version}/{target_id}/messages"
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
            logger.debug(f"📤 Enviando imagen a Meta: {payload}")
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=self.headers, json=payload, timeout=10.0)
                if response.status_code >= 400:
                    logger.error(f"❌ Error Meta API Imagen ({response.status_code}): {response.text}")
                response.raise_for_status()
                data = response.json()
                logger.info(f"✅ Imagen enviada a {to}")
                return data
        except httpx.HTTPStatusError as e:
            raw_response = e.response.text
            logger.error(f"❌ HTTP Error en send_image_message para Destino Final Normalizado: {to} ({e.response.status_code}): {raw_response}")
            raise RuntimeError(f"Meta API Error ({e.response.status_code}): {raw_response}") from e
        except Exception as e:
            logger.error(f"💥 Error crítico en send_image_message para {to}: {str(e)}")
            raise

    async def send_template_message(
        self, 
        to_phone: str, 
        template_name: str, 
        *,
        language_code: str,
        components: list = None, 
        phone_number_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sends a WhatsApp template message (Meta API).
        """
        # 1. Normalización Atómica (Protocolo Meta)
        to_phone = PhoneNormalizer.normalize(to_phone).lstrip("+")
        
        target_id = phone_number_id or self.phone_number_id
        url = f"https://graph.facebook.com/{settings.whatsapp_api_version}/{target_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
            },
        }
        
        if components:
            # Lógica de auto-formateo del wrapper (Detectar strings planos vs JSON)
            if all(isinstance(c, str) or c is None for c in components):
                parameters = []
                for c in components:
                    safe_text = str(c).strip() if c else "tu consulta"
                    parameters.append({"type": "text", "text": safe_text})
                    
                payload["template"]["components"] = [
                    {
                        "type": "body",
                        "parameters": parameters
                    }
                ]
            else:
                payload["template"]["components"] = components

        try:
            logger.debug(f"📤 Enviando Template a Meta: {payload}")
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=self.headers, json=payload, timeout=15.0)
                if response.status_code >= 400:
                    logger.error(f"❌ Error Meta API Template ({response.status_code}): {response.text}")
                response.raise_for_status()
                data = response.json()
                logger.info(f"✅ Template '{template_name}' enviado a {to_phone}")
                return data
        except httpx.HTTPStatusError as e:
            raw_response = e.response.text
            logger.error(f"❌ HTTP Error en send_template_message para Destino Final Normalizado: {to_phone} ({e.response.status_code}): {raw_response}")
            raise RuntimeError(f"Meta API Error ({e.response.status_code}): {raw_response}") from e
        except Exception as e:
            logger.error(f"💥 Error crítico en send_template_message para Destino Final Normalizado: {to_phone}: {str(e)}")
            raise

# Singleton instance
whatsapp_service = WhatsAppService()