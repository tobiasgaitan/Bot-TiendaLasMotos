"""
Tests for environment variable precedence in Settings class (specifically MIN_CATALOG_ITEMS).
[BOT-INFRA-CONFIG-112]
"""

import os
from unittest.mock import patch
import pytest


def test_min_catalog_items_precedence():
    """Test that MIN_CATALOG_ITEMS environment variable takes precedence."""
    # Clean up environment variables
    with patch.dict(os.environ, clear=True):
        # 1. Test GCP Console Injection: If set in environment before load_dotenv()
        os.environ["MIN_CATALOG_ITEMS"] = "80"
        
        # Mock load_dotenv to set MIN_CATALOG_ITEMS = 60 (simulating local .env load)
        def mock_load_dotenv(*args, **kwargs):
            # simulate dotenv load but environment should NOT overwrite if we read before
            os.environ["MIN_CATALOG_ITEMS"] = "60"
            os.environ["GOOGLE_CLOUD_PROJECT"] = "test-project"
            os.environ["FIREBASE_SECRET_NAME"] = "test-secret"
            os.environ["STORAGE_BUCKET"] = "test-bucket"
            os.environ["FIRESTORE_COLLECTION"] = "test-collection"
            os.environ["ADMIN_API_KEY"] = "secure_key_123"
            os.environ["WHATSAPP_TOKEN"] = "token_123"
            os.environ["PHONE_NUMBER_ID"] = "phone_123"
            os.environ["WEBHOOK_VERIFY_TOKEN"] = "verify_123"
            return True

        with patch("app.core.config.load_dotenv", side_effect=mock_load_dotenv):
            from app.core.config import Settings
            # Instantiate Settings class
            settings_inst = Settings()
            # The value should be 80 because it was read before load_dotenv() loaded "60"
            assert settings_inst.min_catalog_items == 80


def test_min_catalog_items_fallback():
    """Test that MIN_CATALOG_ITEMS falls back to dotenv if not set in GCP environment."""
    with patch.dict(os.environ, clear=True):
        # 2. Test fallback: If not set in environment initially, load_dotenv sets it to 60
        def mock_load_dotenv(*args, **kwargs):
            os.environ["MIN_CATALOG_ITEMS"] = "60"
            os.environ["GOOGLE_CLOUD_PROJECT"] = "test-project"
            os.environ["FIREBASE_SECRET_NAME"] = "test-secret"
            os.environ["STORAGE_BUCKET"] = "test-bucket"
            os.environ["FIRESTORE_COLLECTION"] = "test-collection"
            os.environ["ADMIN_API_KEY"] = "secure_key_123"
            os.environ["WHATSAPP_TOKEN"] = "token_123"
            os.environ["PHONE_NUMBER_ID"] = "phone_123"
            os.environ["WEBHOOK_VERIFY_TOKEN"] = "verify_123"
            return True

        with patch("app.core.config.load_dotenv", side_effect=mock_load_dotenv):
            from app.core.config import Settings
            settings_inst = Settings()
            # The value should be 60 because it was not in the environment before, but dotenv loaded it
            assert settings_inst.min_catalog_items == 60


def test_min_catalog_items_default():
    """Test that MIN_CATALOG_ITEMS falls back to the uniform default 40 when not set anywhere.

    [Incidente H-A · HA-2] El default ya NO depende del contexto de ejecución:
    la detección de pytest (que degradaba el mínimo a 0) fue erradicada de config.py.
    """
    with patch.dict(os.environ, clear=True):
        # Absolute default: if neither environment nor dotenv sets it, the value is 40
        # in EVERY context (producción, CI y pytest por igual).
        def mock_load_dotenv(*args, **kwargs):
            # Set other critical vars to pass validation
            os.environ["GOOGLE_CLOUD_PROJECT"] = "test-project"
            os.environ["FIREBASE_SECRET_NAME"] = "test-secret"
            os.environ["STORAGE_BUCKET"] = "test-bucket"
            os.environ["FIRESTORE_COLLECTION"] = "test-collection"
            os.environ["ADMIN_API_KEY"] = "secure_key_123"
            os.environ["WHATSAPP_TOKEN"] = "token_123"
            os.environ["PHONE_NUMBER_ID"] = "phone_123"
            os.environ["WEBHOOK_VERIFY_TOKEN"] = "verify_123"
            return True

        with patch("app.core.config.load_dotenv", side_effect=mock_load_dotenv):
            from app.core.config import Settings

            settings_inst = Settings()
            assert settings_inst.min_catalog_items == 40
