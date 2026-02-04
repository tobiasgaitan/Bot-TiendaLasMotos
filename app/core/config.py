"""
Application configuration using Pydantic Settings.
Loads environment variables with sensible defaults for Cloud Run deployment.
"""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Attributes:
        gcp_project_id: Google Cloud Project ID
        secret_name: Name of the secret in Secret Manager containing Firebase credentials
        storage_bucket: Default Cloud Storage bucket for document uploads
        webhook_verify_token: Token for WhatsApp webhook verification
        whatsapp_token: WhatsApp Cloud API access token
        phone_number_id: WhatsApp Phone Number ID from Meta Business
        port: Server port (default 8080 for Cloud Run)
    """
    
    # Google Cloud Platform
    gcp_project_id: str = Field(default="tiendalasmotos", alias="GCP_PROJECT_ID")
    secret_name: str = Field(default="FIREBASE_CREDENTIALS", alias="SECRET_NAME")
    storage_bucket: str = Field(default="tiendalasmotos-documents", alias="STORAGE_BUCKET")
    
    # WhatsApp Configuration
    webhook_verify_token: str = Field(default="motos2026", alias="WEBHOOK_VERIFY_TOKEN")
    whatsapp_token: str = Field(default="", alias="WHATSAPP_TOKEN")
    phone_number_id: str = Field(default="", alias="PHONE_NUMBER_ID")
    
    # Server Configuration
    port: int = Field(default=8080, alias="PORT")
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        populate_by_name = True  # Allow both field name and alias


# Global settings instance
settings = Settings()
