import pytest
from fastapi.testclient import TestClient
from app.main import app

def test_health_check_with_uninitialized_state():
    """
    [BOT-BACKEND-BUGFIX-CONTAINER-CRASH-188]
    Verify that the /health endpoint does not raise AttributeError and returns HTTP 200
    when app.state.config_loader is missing or uninitialized.
    
    WHY status="starting": When catalog_ready is False (uninitialized state), the health
    endpoint reports "starting" to signal that background initialization is in progress.
    This is the correct behavior for the TCP startup probe — it always returns 200.
    """
    # Temporarily remove config_loader and catalog_ready if they exist on app.state
    had_config_loader = hasattr(app.state, "config_loader")
    original_config_loader = getattr(app.state, "config_loader", None)
    had_catalog_ready = hasattr(app.state, "catalog_ready")
    original_catalog_ready = getattr(app.state, "catalog_ready", None)
    
    if had_config_loader:
        delattr(app.state, "config_loader")
    if had_catalog_ready:
        delattr(app.state, "catalog_ready")
        
    try:
        client = TestClient(app)
        response = client.get("/health")
        
        assert response.status_code == 200
        json_data = response.json()
        # WHY "starting": catalog_ready is not set, so the endpoint reports degraded state
        assert json_data["status"] == "starting"
        assert json_data["catalog_ready"] is False
        assert json_data["service"] == "Auteco Las Motos Backend"
        assert json_data["v6_config"] is None
        
    finally:
        # Restore original state
        if had_config_loader:
            app.state.config_loader = original_config_loader
        if had_catalog_ready:
            app.state.catalog_ready = original_catalog_ready

def test_health_check_with_initialized_state():
    """
    [BOT-BACKEND-BUGFIX-CONTAINER-CRASH-188]
    Verify that the /health endpoint returns "healthy" and the correct structure
    when app.state.config_loader is present AND catalog_ready is True.
    """
    class DummyConfigLoader:
        def get_juan_pablo_personality(self):
            return {"name": "Juan Pablo Test", "model_version": "gemini-2.0-flash-test"}
        def get_routing_rules(self):
            return {"financial_keywords": ["credit", "finance"]}
        def get_catalog_config(self):
            return {"items": [{"id": "moto1"}]}
            
    had_config_loader = hasattr(app.state, "config_loader")
    original_config_loader = getattr(app.state, "config_loader", None)
    had_catalog_ready = hasattr(app.state, "catalog_ready")
    original_catalog_ready = getattr(app.state, "catalog_ready", None)
    
    app.state.config_loader = DummyConfigLoader()
    app.state.catalog_ready = True
    
    try:
        client = TestClient(app)
        response = client.get("/health")
        
        assert response.status_code == 200
        json_data = response.json()
        assert json_data["status"] == "healthy"
        assert json_data["catalog_ready"] is True
        assert json_data["v6_config"] is not None
        assert json_data["v6_config"]["juan_pablo_model"] == "gemini-2.0-flash-test"
        assert json_data["v6_config"]["routing_keywords_loaded"] == 2
        assert json_data["v6_config"]["catalog_config_items"] == 1
        
    finally:
        if had_config_loader:
            app.state.config_loader = original_config_loader
        else:
            delattr(app.state, "config_loader")
        if had_catalog_ready:
            app.state.catalog_ready = original_catalog_ready
        else:
            delattr(app.state, "catalog_ready")
