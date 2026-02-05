"""
Notification Service
Handles admin notifications for human handoff requests via Email and WhatsApp.
"""

import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Service for sending admin notifications when human handoff is triggered.
    
    Supports two notification channels:
    1. Email (via SMTP) - fails gracefully if credentials missing
    2. WhatsApp (via WhatsApp Cloud API) - uses existing infrastructure
    """
    
    def __init__(self):
        """Initialize notification service with environment configuration."""
        self.admin_whatsapp = os.getenv("ADMIN_WHATSAPP")
        self.admin_email = os.getenv("ADMIN_EMAIL")
        
        # SMTP Configuration (optional)
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        
        logger.info(f"📧 NotificationService initialized | Email: {bool(self.admin_email)} | WhatsApp: {bool(self.admin_whatsapp)}")
    
    async def send_email_alert(self, subject: str, body: str) -> bool:
        """
        Send email alert to admin.
        
        Uses SMTP to send email notifications. Fails gracefully if SMTP credentials
        are not configured (logs warning instead of raising exception).
        
        Args:
            subject: Email subject line
            body: Email body content (plain text)
            
        Returns:
            True if email sent successfully, False otherwise
            
        Security:
            - Uses environment variables for credentials (no hardcoded secrets)
            - Fails closed: returns False on any error
        """
        if not self.admin_email:
            logger.warning("⚠️  ADMIN_EMAIL not configured, skipping email alert")
            return False
        
        if not self.smtp_user or not self.smtp_password:
            logger.warning("⚠️  SMTP credentials not configured, skipping email alert")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.smtp_user
            msg['To'] = self.admin_email
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send via SMTP
            logger.info(f"📧 Sending email to {self.admin_email}")
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"✅ Email alert sent successfully to {self.admin_email}")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"❌ SMTP authentication failed: {str(e)}")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"❌ SMTP error sending email: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error sending email: {str(e)}")
            return False
    
    async def send_whatsapp_alert(self, message: str) -> bool:
        """
        Send WhatsApp alert to admin number.
        
        Uses the existing WhatsApp Cloud API infrastructure to send notifications
        to the configured admin WhatsApp number.
        
        Args:
            message: Alert message to send
            
        Returns:
            True if message sent successfully, False otherwise
            
        Security:
            - Uses existing WhatsApp token from settings
            - Validates admin number is configured
            - Fails closed: returns False on any error
        """
        if not self.admin_whatsapp:
            logger.warning("⚠️  ADMIN_WHATSAPP not configured, skipping WhatsApp alert")
            return False
        
        if not settings.whatsapp_token or not settings.phone_number_id:
            logger.error("❌ WhatsApp credentials not configured")
            return False
        
        try:
            url = f"https://graph.facebook.com/v18.0/{settings.phone_number_id}/messages"
            headers = {
                "Authorization": f"Bearer {settings.whatsapp_token}",
                "Content-Type": "application/json"
            }
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": self.admin_whatsapp,
                "type": "text",
                "text": {"body": message}
            }
            
            logger.info(f"📱 Sending WhatsApp alert to {self.admin_whatsapp}")
            
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
            
            logger.info(f"✅ WhatsApp alert sent successfully to {self.admin_whatsapp}")
            return True
            
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ WhatsApp API error: {e.response.status_code} - {e.response.text}")
            return False
        except httpx.TimeoutException as e:
            logger.error(f"⏱️  WhatsApp alert timeout: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error sending WhatsApp alert: {str(e)}")
            return False
    
    async def notify_human_handoff(self, user_phone: str, reason: str) -> None:
        """
        Send notifications to admin when human handoff is triggered.
        
        Sends both email and WhatsApp alerts to notify admin that a user
        has requested human assistance or the AI has escalated the conversation.
        
        Args:
            user_phone: Phone number of the user requesting handoff
            reason: Reason for handoff (e.g., "user_request", "complex_query")
            
        Business Logic:
            - Attempts both notification channels independently
            - Logs results but doesn't fail if notifications fail
            - This ensures the handoff process completes even if notifications fail
        """
        logger.info(f"🚨 Human handoff triggered for {user_phone} | Reason: {reason}")
        
        # Format notification messages
        email_subject = f"🚨 Human Handoff Request - {user_phone}"
        email_body = f"""
Human Handoff Alert - Tienda Las Motos Bot

User Phone: {user_phone}
Reason: {reason}
Time: {self._get_current_time()}

A user has requested human assistance or the AI has escalated the conversation.
Please contact the user as soon as possible.

Session Status: PAUSED (bot will not respond until session is resumed)
        """.strip()
        
        whatsapp_message = f"""
🚨 *HANDOFF ALERT*

Usuario: {user_phone}
Razón: {reason}

El bot ha pausado la sesión. Por favor contacta al usuario.
        """.strip()
        
        # Send notifications (independent attempts)
        email_sent = await self.send_email_alert(email_subject, email_body)
        whatsapp_sent = await self.send_whatsapp_alert(whatsapp_message)
        
        # Log results
        if email_sent and whatsapp_sent:
            logger.info("✅ All notifications sent successfully")
        elif email_sent or whatsapp_sent:
            logger.warning("⚠️  Partial notification success (check logs above)")
        else:
            logger.error("❌ All notifications failed (check configuration)")
    
    def _get_current_time(self) -> str:
        """Get current time in Colombia timezone for logging."""
        from datetime import datetime, timezone, timedelta
        
        # Colombia is UTC-5
        colombia_tz = timezone(timedelta(hours=-5))
        now = datetime.now(colombia_tz)
        return now.strftime("%Y-%m-%d %H:%M:%S %Z")


# Singleton instance
notification_service = NotificationService()
