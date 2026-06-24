import pytest
from fastapi.testclient import TestClient
from app.main import app

def test_health_check_with_uninitialized_state():
    """
    Verify that the /health endpoint does not raise AttributeError and returns a 200 HTTP code
    when app.state.config_loader is missing or uninitialized.
    """
    # Temporarily remove config_loader if it exists on app.state
    had_config_loader = hasattr(app.state, "config_loader")
    original_config_loader = getattr(app.state, "config_loader", None)
    
    if had_config_loader:
        delattr(app.state, "config_loader")
        
    try:
        client = TestClient(app)
        response = client.get("/health")
        
        assert response.status_code == 200
        json_data = response.json()
        assert json_data["status"] == "healthy"
        assert json_data["service"] == "Auteco Las Motos Backend"
        assert json_data["v6_config"] is None
        
    finally:
        # Restore original config_loader if it existed
        if had_config_loader:
            app.state.config_loader = original_config_loader

def test_health_check_with_initialized_state():
    """
    Verify that the /health endpoint returns the correct structure when app.state.config_loader is present.
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
    
    app.state.config_loader = DummyConfigLoader()
    
    try:
        client = TestClient(app)
        response = client.get("/health")
        
        assert response.status_code == 200
        json_data = response.json()
        assert json_data["status"] == "healthy"
        assert json_data["v6_config"] is not None
        assert json_data["v6_config"]["juan_pablo_model"] == "gemini-2.0-flash-test"
        assert json_data["v6_config"]["routing_keywords_loaded"] == 2
        assert json_data["v6_config"]["catalog_config_items"] == 1
        
    finally:
        if had_config_loader:
            app.state.config_loader = original_config_loader
        else:
            delattr(app.state, "config_loader")
