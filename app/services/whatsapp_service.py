"""
WhatsApp Service - Interface with Meta WhatsApp Graph API
=========================================================
Handles outgoing messages, media, and status updates (read receipts).

[BOT-BUILD-205] Added payload validation, sanitization, and truncation
to prevent Graph API rejections due to malformed payloads or length violations.
"""

import logging
import httpx
import re
from typing import Optional, Dict, Any
from app.core.config import settings
from app.core.utils import PhoneNormalizer

logger = logging.getLogger(__name__)

# [BOT-BUILD-205] WhatsApp API limits
MAX_TEXT_BODY_LENGTH = 4096
MAX_IMAGE_CAPTION_LENGTH = 1024

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
    
    @staticmethod
    def _sanitize_text(text: str) -> str:
        """
        [BOT-BUILD-205] Sanitize text by removing control characters and
        normalizing whitespace to prevent JSON serialization issues.
        """
        if not text:
            return text
        # Remove control characters (except newlines and tabs)
        sanitized = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]', '', text)
        # Normalize multiple spaces to single space (preserve newlines)
        sanitized = re.sub(r' +', ' ', sanitized)
        return sanitized.strip()
    
    @staticmethod
    def _truncate_text(text: str, max_length: int) -> str:
        """
        [BOT-BUILD-205] Truncate text to max_length, breaking at last space
        to avoid cutting words. Adds ellipsis indicator if truncated.
        """
        if not text or len(text) <= max_length:
            return text
        
        # Find last space within limit
        truncated = text[:max_length]
        last_space = truncated.rfind(' ')
        
        if last_space > max_length * 0.8:  # Only break at space if reasonable
            truncated = truncated[:last_space]
        else:
            truncated = truncated.rstrip()
        
        # Add ellipsis indicator
        if len(truncated) < len(text):
            truncated = truncated.rstrip('.,;:!?') + '...'
        
        logger.warning(
            f"⚠️ [PAYLOAD TRUNCATION] Text truncated from {len(text)} to {len(truncated)} chars"
        )
        return truncated

    async def send_text_message(self, to: str, text: str, reply_to_id: Optional[str] = None, phone_number_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Sends a text message to a WhatsApp user.
        
        [BOT-BUILD-205] Added payload validation, sanitization, and truncation.
        """
        # 1. Normalización Atómica (Protocolo Meta)
        to = PhoneNormalizer.normalize(to).lstrip("+")
        
        # [BOT-BUILD-205] Sanitize and validate text
        text = self._sanitize_text(text)
        if len(text) > MAX_TEXT_BODY_LENGTH:
            text = self._truncate_text(text, MAX_TEXT_BODY_LENGTH)
        
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

        # [BOT-BUILD-205] Validate payload structure before sending
        try:
            import json
            json.dumps(payload)  # Verify JSON serializable
        except (TypeError, ValueError) as e:
            logger.exception(f"💥 [PAYLOAD VALIDATION] Payload is not JSON serializable: {e}")
            raise ValueError(f"Invalid payload structure: {e}") from e

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
            logger.exception(f"💥 Error crítico en send_text_message para {to}: {str(e)}")
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
        
        [BOT-BUILD-205] Added caption validation, sanitization, and truncation.
        """
        # 1. Normalización Atómica (Protocolo Meta)
        to = PhoneNormalizer.normalize(to).lstrip("+")
        
        # [BOT-BUILD-205] Sanitize and validate caption
        if caption:
            caption = self._sanitize_text(caption)
            if len(caption) > MAX_IMAGE_CAPTION_LENGTH:
                caption = self._truncate_text(caption, MAX_IMAGE_CAPTION_LENGTH)
        
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

        # [BOT-BUILD-205] Validate payload structure before sending
        try:
            import json
            json.dumps(payload)  # Verify JSON serializable
        except (TypeError, ValueError) as e:
            logger.exception(f"💥 [PAYLOAD VALIDATION] Image payload is not JSON serializable: {e}")
            raise ValueError(f"Invalid payload structure: {e}") from e

        try:
            logger.info(f"📤 [META-PAYLOAD] phone_number_id={target_id} payload={payload}")
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=self.headers, json=payload, timeout=10.0)
                if response.status_code >= 400:
                    logger.error(f"❌ Error Meta API Imagen ({response.status_code}): {response.text}")
                response.raise_for_status()
                data = response.json()
                wamid = (data.get("messages") or [{}])[0].get("id") if isinstance(data, dict) else None
                logger.info(f"✅ [META-PAYLOAD] Imagen enviada a {to} wamid={wamid}")
                return data
        except httpx.HTTPStatusError as e:
            raw_response = e.response.text
            logger.error(f"❌ HTTP Error en send_image_message para Destino Final Normalizado: {to} ({e.response.status_code}): {raw_response}")
            raise RuntimeError(f"Meta API Error ({e.response.status_code}): {raw_response}") from e
        except Exception as e:
            logger.exception(f"💥 Error crítico en send_image_message para {to}: {str(e)}")
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
        
        # Payload Sanity: Conditionally omit 'components' key if there are no dynamic variables
        final_components = []
        if components:
            if all(isinstance(c, (str, type(None))) for c in components):
                parameters = []
                for c in components:
                    if c is not None:
                        safe_text = str(c).strip()
                        if safe_text:
                            parameters.append({"type": "text", "text": safe_text})
                if parameters:
                    final_components = [
                        {
                            "type": "body",
                            "parameters": parameters
                        }
                    ]
            else:
                for comp in components:
                    if isinstance(comp, dict):
                        params = comp.get("parameters", [])
                        valid_params = []
                        for p in params:
                            if isinstance(p, dict):
                                text_val = p.get("text")
                                if text_val is not None:
                                    safe_text = str(text_val).strip()
                                    if safe_text:
                                        valid_params.append({"type": p.get("type", "text"), "text": safe_text})
                            elif isinstance(p, str):
                                safe_text = str(p).strip()
                                if safe_text:
                                    valid_params.append({"type": "text", "text": safe_text})
                        if valid_params:
                            final_components.append({
                                "type": comp.get("type", "body"),
                                "parameters": valid_params
                            })
        
        if final_components:
            payload["template"]["components"] = final_components

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