import os
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import HTTPException, BackgroundTasks
from fastapi.testclient import TestClient

from app.main import app, lifespan
from app.routers.whatsapp import webhook_handler, task_processor
from app.services.catalog_service import catalog_service


@pytest.mark.asyncio
async def test_webhook_handler_rejects_with_503_if_catalog_not_fully_loaded():
    """
    Test that the webhook handler rejects incoming requests with an HTTP 503
    if the catalog is not fully loaded.
    """
    mock_request = MagicMock()
    # Mock request body
    async def mock_body():
        return b'{"object": "whatsapp_business_account", "entry": []}'
    mock_request.body = mock_body
    mock_request.headers = {}
    
    # Mock settings.min_catalog_items to a high value, and mock catalog to be empty (0 items)
    with patch("app.routers.whatsapp.settings") as mock_settings, \
         patch.object(catalog_service, "get_all_items", return_value=[]), \
         patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock) as mock_ensure:
         
        mock_settings.min_catalog_items = 60
        mock_settings.whatsapp_app_secret = None  # Skip signature verification
        
        background_tasks = BackgroundTasks()
        
        with pytest.raises(HTTPException) as exc_info:
            await webhook_handler(mock_request, background_tasks)
            
        assert exc_info.value.status_code == 503
        assert "Catalog not fully loaded" in exc_info.value.detail


@pytest.mark.asyncio
async def test_task_processor_rejects_with_503_if_catalog_not_fully_loaded():
    """
    Test that the task processor rejects incoming tasks with an HTTP 503
    if the catalog is not fully loaded.
    """
    mock_request = MagicMock()
    async def mock_json():
        return {"object": "whatsapp_business_account", "entry": []}
    mock_request.json = mock_json
    mock_request.headers = {"X-Task-Token": "secret_token"}
    
    background_tasks = BackgroundTasks()
    
    with patch("app.routers.whatsapp.settings") as mock_settings, \
         patch.object(catalog_service, "get_all_items", return_value=[]), \
         patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock) as mock_ensure:
         
        mock_settings.min_catalog_items = 60
        mock_settings.webhook_verify_token = "secret_token"
        
        with pytest.raises(HTTPException) as exc_info:
            await task_processor(mock_request, background_tasks)
            
        assert exc_info.value.status_code == 503
        assert "Catalog not fully loaded" in exc_info.value.detail


@pytest.mark.asyncio
async def test_startup_lifespan_timeout_keeps_catalog_ready_false():
    """
    Test that the lifespan startup keeps catalog_ready as False if the database sync
    exceeds settings.db_timeout.
    """
    # Force settings.db_timeout to be short for the test (e.g. 0.05s)
    with patch("app.main.settings") as mock_settings, \
         patch("app.main.get_firebase_credentials_object") as mock_creds, \
         patch("app.main.firestore") as mock_firestore, \
         patch("app.main.config_service") as mock_config_service, \
         patch("app.main.ConfigLoader") as mock_config_loader, \
         patch("app.main.FinanceConfigLoader") as mock_finance_config_loader, \
         patch("app.main.storage_service") as mock_storage_service:
         
        mock_settings.db_timeout = 0.05
        mock_settings.gcp_project_id = "test-project"
        mock_creds.return_value = MagicMock()
        
        # Simulate high latency in config_service initialization (inside to_thread)
        def slow_init(*args, **kwargs):
            import time
            time.sleep(0.5)  # 0.5s > 0.05s timeout
            
        mock_config_service.initialize.side_effect = slow_init
        
        with patch.dict(os.environ, {"TEST_MODE": "false"}):
            async with lifespan(app):
                # The lifespan completes immediately and unblocks the port.
                # Now we wait for the background task to finish.
                await app.state.startup_task
                # Ensure catalog_ready is still False since it timed out
                assert app.state.catalog_ready is False


@pytest.mark.asyncio
async def test_startup_lifespan_catalog_size_check_fails_in_production():
    """
    Test that the lifespan startup sets catalog_ready to False if the catalog has
    fewer items than min_catalog_items when NOT in TEST_MODE.
    """
    with patch("app.main.settings") as mock_settings, \
         patch("app.main.get_firebase_credentials_object") as mock_creds, \
         patch("app.main.firestore") as mock_firestore, \
         patch("app.main.ConfigLoader") as mock_config_loader, \
         patch("app.main.config_service") as mock_config_service, \
         patch("app.main.FinanceConfigLoader") as mock_finance_config_loader, \
         patch("app.main.storage_service") as mock_storage_service, \
         patch.object(catalog_service, "get_all_items", return_value=[]):
         
        mock_settings.db_timeout = 5
        mock_settings.min_catalog_items = 60
        mock_settings.gcp_project_id = "test-project"
        
        with patch.dict(os.environ, {"TEST_MODE": "false"}):
            async with lifespan(app):
                await app.state.startup_task
                assert app.state.catalog_ready is False


@pytest.mark.asyncio
async def test_startup_lifespan_successful_initialization_sets_catalog_ready_true():
    """
    Test that a successful initialization sets catalog_ready to True.
    """
    with patch("app.main.settings") as mock_settings, \
         patch("app.main.get_firebase_credentials_object") as mock_creds, \
         patch("app.main.firestore") as mock_firestore, \
         patch("app.main.ConfigLoader") as mock_config_loader, \
         patch("app.main.config_service") as mock_config_service, \
         patch("app.main.FinanceConfigLoader") as mock_finance_config_loader, \
         patch("app.main.storage_service") as mock_storage_service, \
         patch.object(catalog_service, "get_all_items", return_value=[MagicMock()] * 60):
         
        mock_settings.db_timeout = 5
        mock_settings.min_catalog_items = 60
        mock_settings.gcp_project_id = "test-project"
        
        with patch.dict(os.environ, {"TEST_MODE": "false"}):
            async with lifespan(app):
                await app.state.startup_task
                assert app.state.catalog_ready is True
