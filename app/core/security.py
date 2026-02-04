"""
Security module for credential management.
Retrieves Firebase credentials from Google Secret Manager.
CRITICAL: Never uses local JSON files - all credentials from Secret Manager.
"""

import json
import logging
from typing import Dict, Any

from google.cloud import secretmanager
from google.oauth2 import service_account

from app.core.config import settings

logger = logging.getLogger(__name__)


def get_firebase_credentials() -> Dict[str, Any]:
    """
    Retrieve Firebase credentials from Google Secret Manager.
    
    This function accesses the secret specified in settings.secret_name
    from Google Secret Manager and returns the credentials as a dictionary.
    
    Returns:
        Dict containing Firebase service account credentials
        
    Raises:
        Exception: If secret cannot be retrieved or parsed
        
    Security:
        - Uses Application Default Credentials (ADC) for Secret Manager access
        - Never stores credentials in files
        - Credentials are loaded into memory only
    """
    try:
        # Initialize Secret Manager client
        client = secretmanager.SecretManagerServiceClient()
        
        # Build the secret version path (using 'latest' version)
        secret_path = f"projects/{settings.gcp_project_id}/secrets/{settings.secret_name}/versions/latest"
        
        logger.info(f"Retrieving secret from: {secret_path}")
        
        # Access the secret
        response = client.access_secret_version(request={"name": secret_path})
        
        # Parse the secret payload as JSON
        credentials_json = response.payload.data.decode("UTF-8")
        credentials_dict = json.loads(credentials_json)
        
        logger.info("✅ Firebase credentials retrieved successfully from Secret Manager")
        
        return credentials_dict
        
    except Exception as e:
        logger.error(f"❌ Failed to retrieve Firebase credentials: {str(e)}")
        raise


def get_firebase_credentials_object() -> service_account.Credentials:
    """
    Get Firebase credentials as a Google Auth Credentials object.
    
    Returns:
        service_account.Credentials object for use with GCP clients
    """
    credentials_dict = get_firebase_credentials()
    
    credentials = service_account.Credentials.from_service_account_info(
        credentials_dict,
        scopes=[
            "https://www.googleapis.com/auth/cloud-platform",
            "https://www.googleapis.com/auth/datastore",
        ]
    )
    
    return credentials
