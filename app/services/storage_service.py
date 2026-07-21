"""
Storage Service
Manages Google Cloud Storage for document uploads.
Provides infrastructure for future document handling (Cédula, Facturas).
"""

import logging
from typing import Optional

from google.cloud import storage
from google.oauth2 import service_account

from app.core.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """
    Service for managing Cloud Storage operations.
    
    Initializes Storage client and manages default bucket
    for document uploads (future use: Cédula, Facturas, etc.).
    """
    
    def __init__(self):
        """Initialize the storage service with empty state."""
        self._client: Optional[storage.Client] = None
        self._bucket: Optional[storage.Bucket] = None
    
    def initialize(self, credentials: service_account.Credentials) -> None:
        """
        Initialize the service with credentials and set up bucket.
        
        Args:
            credentials: Service account credentials from Secret Manager
        """
        try:
            logger.info("☁️  Initializing Cloud Storage client...")
            
            # Initialize Storage client with credentials
            self._client = storage.Client(
                project=settings.gcp_project_id,
                credentials=credentials
            )
            
            # Get or create default bucket
            self._setup_bucket()
            
            logger.info("✅ Cloud Storage initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Error initializing Cloud Storage: {str(e)}")
            raise
    
    def _setup_bucket(self) -> None:
        """
        Set up the default bucket for document storage.
        Creates the bucket if it doesn't exist.
        """
        try:
            bucket_name = settings.storage_bucket
            
            # Try to get existing bucket
            try:
                self._bucket = self._client.get_bucket(bucket_name)
                logger.info(f"✅ Using existing bucket: {bucket_name}")
            except Exception as e:
                logger.info(f"⚠️ [STORAGE] Bucket {bucket_name} not found or inaccessible, attempting creation: {e}")
                # Bucket doesn't exist, create it
                logger.info(f"📦 Creating new bucket: {bucket_name}")
                self._bucket = self._client.create_bucket(
                    bucket_name,
                    location="US"
                )
                logger.info(f"✅ Bucket created: {bucket_name}")
                
        except Exception as e:
            logger.error(f"❌ Error setting up bucket: {str(e)}")
            raise
    
    def upload_document(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str = "application/octet-stream"
    ) -> str:
        """
        Upload a document to Cloud Storage.
        
        Args:
            file_bytes: File content as bytes
            filename: Name for the uploaded file
            content_type: MIME type of the file
            
        Returns:
            Public URL of the uploaded file
            
        Note:
            This method is prepared for future use when implementing
            document upload functionality (Cédula, Facturas, etc.)
        """
        try:
            # Create blob with filename
            blob = self._bucket.blob(filename)
            
            # Upload file
            blob.upload_from_string(
                file_bytes,
                content_type=content_type
            )
            
            # Make blob publicly accessible (adjust permissions as needed)
            blob.make_public()
            
            logger.info(f"✅ Document uploaded: {filename}")
            
            return blob.public_url
            
        except Exception as e:
            logger.error(f"❌ Error uploading document: {str(e)}")
            raise
    
    def get_bucket_name(self) -> str:
        """
        Get the name of the default bucket.
        
        Returns:
            Bucket name
        """
        return self._bucket.name if self._bucket else settings.storage_bucket

    async def download_media(self, media_id: str) -> Optional[bytes]:
        """Download media from WhatsApp."""
        import httpx
        try:
            # WHY: single-source Graph API version (BOT-BUILD-REGRESSION-MULTIMODAL-01).
            # The previous hardcoded v25.0 claimed alignment with whatsapp_service.py,
            # but that service builds its URLs from settings.whatsapp_api_version.
            url = f"https://graph.facebook.com/{settings.whatsapp_api_version}/{media_id}"
            headers = {"Authorization": f"Bearer {settings.whatsapp_token}"}
            
            async with httpx.AsyncClient() as client:
                r1 = await client.get(url, headers=headers)
                r1.raise_for_status()
                media_url = r1.json().get("url")
                
                r2 = await client.get(media_url, headers=headers)
                r2.raise_for_status()
                return r2.content
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status in (401, 403):
                # Zero-Silent-Failures: credential rejection is FATAL and requires
                # WHATSAPP_TOKEN rotation. It must never be confused with a
                # transient network error.
                logger.critical(
                    f"🔥 [MEDIA-AUTH-FATAL] Meta rechazó la credencial de descarga "
                    f"(HTTP {status}) para media_id={media_id}. WHATSAPP_TOKEN expirado "
                    f"o inválido — se requiere rotación. Response: {e.response.text}"
                )
            else:
                logger.error(
                    f"❌ Error HTTP downloading media ({status}): {e.response.text}",
                    exc_info=True
                )
            return None
        except Exception as e:
            # Transient candidate (DNS, timeout, connection reset).
            logger.exception(f"❌ Error downloading media: {e}")
            return None


# Global service instance
storage_service = StorageService()
