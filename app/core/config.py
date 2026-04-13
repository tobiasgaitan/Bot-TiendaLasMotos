"""
Application configuration using direct os.getenv for Cloud Run compatibility.
Includes both WhatsApp and Google Cloud Platform configuration.
"""

import os
from typing import Optional


class Settings:
    """
    Application settings loaded directly from environment variables using os.getenv.
    
    This approach ensures maximum compatibility with Cloud Run and other deployment environments.
    Includes both WhatsApp API configuration and Google Cloud Platform settings.
    """
    
    def __init__(self):
        """Initialize settings by reading environment variables."""
        
        # Google Cloud Platform Configuration
        self.gcp_project_id: str = os.getenv("GOOGLE_CLOUD_PROJECT", "tiendalasmotos")
        self.secret_name: str = os.getenv("FIREBASE_SECRET_NAME", "FIREBASE_CREDENTIALS")
        self.storage_bucket: str = os.getenv("STORAGE_BUCKET", "tiendalasmotos-documents")
        
        # Admin API Key from Secret Manager
        self.admin_api_key: str = os.getenv("ADMIN_API_KEY", "moto_master_2026")
        
        # WhatsApp Configuration - CRITICAL for message sending
        self.whatsapp_token: str = os.getenv("WHATSAPP_TOKEN", "EAATOsIH213wBROFiZB7TTPjcemFtNUiDuRbo2mV17MokAlz5ue2hH791CmATXDAjCZBATZCFkcxTuZCf3AINebYEb2ZBQuZC8zSLgTlsbnoaZC3K9EbKbZA6wchpVR5QcBtjtTdQWRheaUE5MXz6sNDWfaCDYsQwaHiuxFhjv3ZBgFPa8adbgsi2PYfI0FF7wbAZDZD")
        self.phone_number_id: str = os.getenv("PHONE_NUMBER_ID", "1021779847693778")
        self.webhook_verify_token: str = os.getenv("WEBHOOK_VERIFY_TOKEN", "motos2026")
        
        # Server Configuration
        self.port: int = int(os.getenv("PORT", "8080"))
        
        # Log configuration status (DO NOT log actual tokens)
        self._log_config_status()
    
    def _log_config_status(self) -> None:
        """Log configuration status without exposing sensitive values."""
        print("=" * 60)
        print("🔧 CONFIGURATION LOADED")
        print("=" * 60)
        
        # Google Cloud Platform
        print(f"GCP Project ID: {self.gcp_project_id}")
        print(f"Secret Name: {self.secret_name}")
        print(f"Storage Bucket: {self.storage_bucket}")
        
        # WhatsApp Configuration
        print(f"Webhook Verify Token: {'✅ SET' if self.webhook_verify_token else '❌ MISSING'}")
        print(f"WhatsApp Token: {'✅ FOUND' if self.whatsapp_token else '❌ MISSING'}")
        print(f"Phone Number ID: {'✅ FOUND' if self.phone_number_id else '❌ MISSING'}")
        
        # Server
        print(f"Port: {self.port}")
        print(f"Admin API Key: {'✅ SECURE' if self.admin_api_key != 'moto_master_2026' else '⚠️ DEFAULT/INSECURE'}")
        print("=" * 60)
        
        # Critical warnings for WhatsApp
        if not self.whatsapp_token:
            print("⚠️  WARNING: WHATSAPP_TOKEN is not set!")
            print("   Set it with: gcloud run services update ... --set-env-vars='WHATSAPP_TOKEN=xxx'")
        
        if not self.phone_number_id:
            print("⚠️  WARNING: PHONE_NUMBER_ID is not set!")
            print("   Set it with: gcloud run services update ... --set-env-vars='PHONE_NUMBER_ID=xxx'")
        
        print()


# Global settings instance
settings = Settings()
