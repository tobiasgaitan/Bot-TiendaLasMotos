"""
Application configuration using Pydantic Settings.
Loads environment variables with sensible defaults for Cloud Run deployment.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Attributes:
        gcp_project_id: Google Cloud Project ID
        secret_name: Name of the secret in Secret Manager containing Firebase credentials
        storage_bucket: Default Cloud Storage bucket for document uploads
        webhook_verify_token: Token for WhatsApp webhook verification
        port: Server port (default 8080 for Cloud Run)
    """
    
    gcp_project_id: str = "tiendalasmotos"
    secret_name: str = "FIREBASE_CREDENTIALS"
    storage_bucket: str = "tiendalasmotos-documents"
    webhook_verify_token: str = "motos2026"
    whatsapp_phone_number_id: str = ""  # Set via environment variable
    whatsapp_access_token: str = ""  # Set via environment variable
    port: int = 8080
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
