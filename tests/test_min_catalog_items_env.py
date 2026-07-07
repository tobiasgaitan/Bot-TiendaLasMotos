"""
Tests for environment variable precedence in Settings class (specifically MIN_CATALOG_ITEMS).
[BOT-INFRA-CONFIG-112]
"""

import os
import sys
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
    """Test that MIN_CATALOG_ITEMS falls back to default 40 (or 0 if under pytest) if not set anywhere."""
    with patch.dict(os.environ, clear=True):
        # 3. Test absolute default: if neither environment nor dotenv sets it, default is 0 for pytest, 40 otherwise
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
            
            # Since we are running under pytest, this should be 0 by default
            settings_inst = Settings()
            assert settings_inst.min_catalog_items == 0
            
            # Test without pytest in sys.modules
            modified_modules = sys.modules.copy()
            if "pytest" in modified_modules:
                del modified_modules["pytest"]
            with patch("sys.modules", new=modified_modules):
                settings_inst_no_pytest = Settings()
                assert settings_inst_no_pytest.min_catalog_items == 40
