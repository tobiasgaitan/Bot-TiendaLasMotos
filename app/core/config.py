"""
Application configuration using direct os.getenv for Cloud Run compatibility.
Includes both WhatsApp and Google Cloud Platform configuration.
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Load local environment variables from .env if present
load_dotenv()


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
        self.firestore_collection: str = os.getenv("FIRESTORE_COLLECTION", "prospectos")
        
        # Admin API Key from Secret Manager
        self.admin_api_key: str = os.getenv("ADMIN_API_KEY")
        
        # WhatsApp Configuration - CRITICAL for message sending
        self.whatsapp_token: str = os.getenv("WHATSAPP_TOKEN")
        self.phone_number_id: str = os.getenv("PHONE_NUMBER_ID")
        self.webhook_verify_token: str = os.getenv("WEBHOOK_VERIFY_TOKEN")
        self.whatsapp_app_secret: str = os.getenv("WHATSAPP_APP_SECRET", "***REMOVED***")
        
        # Cloud Tasks Configuration (BOT-ARCH-CLOUDTASKS-098)
        # Fallback to local synchronous background tasks if not set (for local dev)
        self.cloud_tasks_queue_path: Optional[str] = os.getenv("CLOUD_TASKS_QUEUE_PATH")
        self.task_processor_url: Optional[str] = os.getenv("TASK_PROCESSOR_URL")
        
        # Validate critical settings
        self._validate_config()

        # Server Configuration
        self.port: int = int(os.getenv("PORT", "8080"))

        # Firestore I/O Timeout (BOT-INFRA-33)
        # WHY: Previene el congelamiento del orquestador de webhooks ante degradación de red GCP.
        # El valor de 5s es el umbral de detección: p99 normal de Firestore es <1s.
        # Configurable vía Cloud Run: --set-env-vars='DB_TIMEOUT=10'
        self.db_timeout: int = int(os.getenv("DB_TIMEOUT", "5"))
        self.min_catalog_items: int = int(os.getenv("MIN_CATALOG_ITEMS", "60"))
        
        # WhatsApp API Version Override
        self.whatsapp_api_version: str = os.getenv("WHATSAPP_API_VERSION", "v21.0")
        
        # Langfuse Observability Configuration
        # WHY: Optional variables — app boots normally without them.
        # Langfuse client in ai_brain.py checks LANGFUSE_AVAILABLE before activating.
        self.langfuse_public_key: Optional[str] = os.getenv("LANGFUSE_PUBLIC_KEY")
        self.langfuse_secret_key: Optional[str] = os.getenv("LANGFUSE_SECRET_KEY")
        self.langfuse_host: str = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        
        # Log configuration status (DO NOT log actual tokens)
        self._log_config_status()
    
    def _validate_config(self) -> None:
        """Ensure critical configuration variables are present and secure."""
        critical_vars = {
            "WHATSAPP_TOKEN": self.whatsapp_token,
            "PHONE_NUMBER_ID": self.phone_number_id,
            "ADMIN_API_KEY": self.admin_api_key,
            "WEBHOOK_VERIFY_TOKEN": self.webhook_verify_token
        }
        
        for name, value in critical_vars.items():
            if not value or value in ["moto_master_2026", "motos2026"]:
                raise RuntimeError(f"❌ CRITICAL CONFIGURATION ERROR: {name} is missing or insecure.")

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
        print(f"WhatsApp App Secret: {'✅ SET' if self.whatsapp_app_secret else '❌ MISSING'}")
        print(f"WhatsApp API Version: {self.whatsapp_api_version}")
        
        # Server
        print(f"Port: {self.port}")
        print(f"Admin API Key: {'✅ SECURE' if self.admin_api_key != 'moto_master_2026' else '⚠️ DEFAULT/INSECURE'}")
        
        # Cloud Tasks
        print(f"Cloud Tasks Queue: {'✅ ' + self.cloud_tasks_queue_path if self.cloud_tasks_queue_path else '⚠️ NOT SET (Using local fallback)'}")
        print(f"Task Processor URL: {'✅ ' + self.task_processor_url if self.task_processor_url else '⚠️ NOT SET (Using local fallback)'}")
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

VERSION = "9.8.7"
