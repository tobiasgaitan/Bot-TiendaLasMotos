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
    [BOT-BACKEND-BUGFIX-CONTAINER-CRASH-188]
    Test that the lifespan startup keeps catalog_ready as False if the background
    initialization exceeds the timeout.
    
    WHY: The deferred init pattern runs _run_deferred_initialization as an
    asyncio.create_task(). We mock it to simulate a timeout scenario.
    """
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
    [BOT-BACKEND-BUGFIX-CONTAINER-CRASH-188]
    [BOT-INFRA-BUGFIX-HEALTH-PORT-BINDING-192]
    Test that the background initialization sets catalog_ready to True even if the catalog has
    fewer items than min_catalog_items when NOT in TEST_MODE, because size validation is decoupled.
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
                assert app.state.catalog_ready is True


@pytest.mark.asyncio
async def test_startup_lifespan_successful_initialization_sets_catalog_ready_true():
    """
    [BOT-BACKEND-BUGFIX-CONTAINER-CRASH-188]
    Test that a successful background initialization sets catalog_ready to True.
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


@pytest.mark.asyncio
async def test_deferred_init_port_available_before_hydration():
    """
    [BOT-BACKEND-BUGFIX-CONTAINER-CRASH-188]
    [BOT-BACKEND-BUGFIX-LIFESPAN-DELAY-190]
    Test that the lifespan handler yields IMMEDIATELY (allowing Uvicorn to bind port 8080)
    and that the application of FastAPI is completely responsive on /health returning 'starting'
    immediately while the heavy initialization sleeps in the background.
    """
    import time
    import app.main as main_module
    
    with patch("app.main.settings") as mock_settings, \
         patch("app.main.get_firebase_credentials_object") as mock_creds, \
         patch("app.main.firestore") as mock_firestore, \
         patch("app.main.ConfigLoader") as mock_config_loader, \
         patch("app.main.config_service") as mock_config_service, \
         patch("app.main.FinanceConfigLoader") as mock_finance_config_loader, \
         patch("app.main.storage_service") as mock_storage_service, \
         patch.object(catalog_service, "get_all_items", return_value=[MagicMock()] * 60), \
         patch.object(main_module, "TEST_MODE", False):
         
        mock_settings.db_timeout = 5
        mock_settings.gcp_project_id = "test-project"
        mock_settings.min_catalog_items = 60
        mock_creds.return_value = MagicMock()
        
        # Keep slow_init to simulate network hydration time
        def slow_init(*args, **kwargs):
            import time
            time.sleep(0.5)
        mock_config_service.initialize.side_effect = slow_init
        
        start_time = time.monotonic()
        with TestClient(app) as client:
            elapsed = time.monotonic() - start_time
            # The lifespan must yield and allow Uvicorn/TestClient to bind in less than 0.5s
            assert elapsed < 0.5, (
                f"Lifespan took {elapsed:.2f}s to yield — port 8080 would be blocked. "
                f"Expected < 0.5s for immediate yield."
            )
            
            # Verify the application is fully responsive immediately
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json()["status"] == "starting"
            assert response.json()["catalog_ready"] is False
            
            # Clean up/Wait for the background task to complete by polling catalog_ready
            start_wait = time.monotonic()
            while not app.state.catalog_ready and time.monotonic() - start_wait < 5:
                await asyncio.sleep(0.1)
                
            # After background task completes, it should be healthy
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json()["status"] == "healthy"
            assert response.json()["catalog_ready"] is True


@pytest.mark.asyncio
async def test_health_returns_starting_immediately_when_catalog_empty_before_hydration():
    """
    [BOT-INFRA-BUGFIX-HEALTH-PORT-BINDING-192]
    Test that GET /health returns HTTP 200 OK and "status": "starting"
    immediately when the catalog has 0 items before background hydration is complete.
    """
    import time
    import app.main as main_module
    
    with patch("app.main.settings") as mock_settings, \
         patch("app.main.get_firebase_credentials_object") as mock_creds, \
         patch("app.main.firestore") as mock_firestore, \
         patch("app.main.ConfigLoader") as mock_config_loader, \
         patch("app.main.config_service") as mock_config_service, \
         patch("app.main.FinanceConfigLoader") as mock_finance_config_loader, \
         patch("app.main.storage_service") as mock_storage_service, \
         patch.object(catalog_service, "get_all_items", return_value=[]), \
         patch.object(main_module, "TEST_MODE", False):
         
        mock_settings.db_timeout = 5
        mock_settings.gcp_project_id = "test-project"
        mock_settings.min_catalog_items = 60
        mock_creds.return_value = MagicMock()
        
        # Keep slow_init to simulate network hydration time
        def slow_init(*args, **kwargs):
            import time
            time.sleep(0.5)
        mock_config_service.initialize.side_effect = slow_init
        
        start_time = time.monotonic()
        with TestClient(app) as client:
            elapsed = time.monotonic() - start_time
            # Ensure lifespan yields immediately
            assert elapsed < 0.5
            
            # Verify the application is fully responsive immediately on /health
            # returning HTTP 200 and "status": "starting" even when catalog has 0 items.
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json()["status"] == "starting"
            assert response.json()["catalog_ready"] is False
            
            # Clean up/Wait for the background task to complete by polling catalog_ready
            start_wait = time.monotonic()
            while not app.state.catalog_ready and time.monotonic() - start_wait < 5:
                await asyncio.sleep(0.1)
                
            # After background task completes, it should be healthy (even with 0 items since size check is decoupled)
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json()["status"] == "healthy"
            assert response.json()["catalog_ready"] is True


def test_main_module_import_time():
    """
    Test that app.main imports in less than 1.0 second.
    """
    import sys
    import time
    
    # If app.main is already imported, remove it from sys.modules to force a full re-import
    if "app.main" in sys.modules:
        del sys.modules["app.main"]
        
    t0 = time.time()
    import app.main
    elapsed = time.time() - t0
    
    print(f"\nImport time: {elapsed:.4f}s")
    assert elapsed < 1.0, f"app.main import took too long: {elapsed:.4f}s"


def test_health_endpoint_never_returns_503_during_hydration():
    """
    [BOT-INFRA-BUGFIX-HEALTH-PORT-BINDING-192]
    Test that the health endpoint never returns HTTP 503 during hydration
    even if the in-memory state is dehydrated (0 items).
    """
    had_catalog_ready = hasattr(app.state, "catalog_ready")
    original_catalog_ready = getattr(app.state, "catalog_ready", None)
    
    # Force catalog_ready to False (simulating early hydration state)
    app.state.catalog_ready = False
    
    try:
        with patch.object(catalog_service, "get_all_items", return_value=[]):
            client = TestClient(app)
            response = client.get("/health")
            
            assert response.status_code == 200
            json_data = response.json()
            assert json_data["status"] == "starting"
            assert json_data["detail"] == "Catalog initialization in progress"
            assert json_data["catalog_ready"] is False
    finally:
        if had_catalog_ready:
            app.state.catalog_ready = original_catalog_ready
        else:
            delattr(app.state, "catalog_ready")
