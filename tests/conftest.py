import pytest
from unittest.mock import MagicMock, patch
import sys
import os

pytest_plugins = ["tests.conftest_chaos"]

# Asegurar que el path del proyecto esté disponible
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@pytest.fixture(autouse=True)
def mock_env_vars():
    """Mocks de variables de entorno para evitar fallos de configuración.
    
    WHY (BOT-INFRA-RECOVERY-PARAM-197): El fixture original no inyectaba las 4 credenciales
    críticas validadas por Settings()._validate_config(). Esto creaba un falso positivo: los
    tests pasaban en CI/CD porque la suite importaba 'settings' como singleton ya inicializado
    desde el .env local, nunca verificando el RuntimeError de arranque con vars ausentes.
    """
    with patch.dict(os.environ, {
        "GOOGLE_APPLICATION_CREDENTIALS": "/tmp/fake-key.json",
        # [Incidente H-A · HA-2] Las variables de modo de pruebas y el mínimo de
        # catálogo forzado a 0 fueron erradicados del arnés global: el guard es
        # estricto y los tests lo satisfacen vía fixtures dinámicos
        # (dynamic_catalog / catalog_guard_ready).
        # Credenciales críticas — requeridas por Settings()._validate_config()
        # Valores de prueba seguros, nunca tokens reales de producción.
        "WHATSAPP_TOKEN": "TEST_WHATSAPP_TOKEN_PLACEHOLDER_197",
        "PHONE_NUMBER_ID": "1234567890",
        "ADMIN_API_KEY": "test_admin_key_not_a_real_secret_197",
        "WEBHOOK_VERIFY_TOKEN": "test_verify_token_197",
        "WHATSAPP_APP_SECRET": "test_app_secret_197",
    }):
        yield


@pytest.fixture
def mock_prospect_data():
    """Fixture de datos de prospecto para pruebas de anclaje CRM."""
    return {
        "exists": True,
        "nombre": "Juan Perez",
        "moto_interest": "TVS APACHE 160",
        "ciudad": "Bogotá",
        "forma_pago": "Crédito"
    }

@pytest.fixture
def cerebro_mock():
    """Instancia de CerebroIA con el SDK desactivado para tests lógicos."""
    # Forzamos SDK_AVAILABLE = False importando y parcheando antes de instanciar
    with patch('app.services.ai_brain.SDK_AVAILABLE', False):
        from app.services.ai_brain import CerebroIA
        cerebro = CerebroIA()
        # Inyectar atributos que normalmente se setean solo si SDK_AVAILABLE es True
        cerebro.client = MagicMock()
        cerebro._model_id = "gemini-2.0-flash" 
        cerebro.privacy_policy_url = "https://tiendalasmotos.com/politica-de-privacidad"
        return cerebro

@pytest.fixture
def dynamic_catalog():
    """Catálogo dinámico de 60 ítems (tests/factories.py) inyectado en el singleton real.

    WHY (Incidente H-A · HA-3): sustituye los mocks ad-hoc `[MagicMock()] * N` y los
    literales de precio del arnés. Determinista (seed fija) y restaurado en teardown.
    """
    from tests.factories import install_dynamic_catalog, restore_catalog
    items, token = install_dynamic_catalog(60)
    yield items
    restore_catalog(token)


@pytest.fixture
def catalog_guard_ready(dynamic_catalog, monkeypatch):
    """Satisface el STARTUP-GUARD estricto para tests que ejercitan webhook/task-processor
    vía TestClient: catálogo dinámico instalado (60 ítems) + app.state.catalog_ready=True
    + settings.min_catalog_items=60. Restaura app.state en teardown.

    WHY (Incidente H-A · HA-2): tras la erradicación del bypass de modo de pruebas
    (04-03a), el guard es incondicional — este fixture es la forma aprobada de satisfacerlo.
    """
    from app.main import app
    from app.routers import whatsapp as whatsapp_router

    had_flag = hasattr(app.state, "catalog_ready")
    previous_flag = getattr(app.state, "catalog_ready", None)
    app.state.catalog_ready = True
    monkeypatch.setattr(whatsapp_router.settings, "min_catalog_items", 60)
    yield dynamic_catalog
    if had_flag:
        app.state.catalog_ready = previous_flag
    else:
        delattr(app.state, "catalog_ready")

class AsyncStreamMock:
    """
    Mock estandarizado para simular firestore.Query.stream().
    Implementa el protocolo de iteración asíncrona (__aiter__ y __anext__).
    """
    def __init__(self, items):
        self.items = items
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.items):
            raise StopAsyncIteration
        item = self.items[self.index]
        self.index += 1
        return item

def test_config_service_routing_dynamic_partners():
    """
    [BOT-ARQ-FS-066] Certifica que ConfigService.load_configurations hidrata
    _partners_config iterando sobre financial_config/general/financieras, 
    y que get_partners_config() no retorna None ni un diccionario vacío.
    """
    from app.services.config_service import ConfigService
    
    class MockDoc:
        def __init__(self, id, data):
            self.id = id
            self._data = data
        def to_dict(self):
            return self._data
            
    mock_docs = [
        MockDoc("banco_bogota", {"link_url": "https://bogota.com"}),
        MockDoc("brilla", {"link": "https://brilla.com"}),
        MockDoc("crediorbe", {"url": "https://crediorbe.com"})
    ]
    
    mock_db = MagicMock()
    mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value.get.return_value.exists = True
    mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value.get.return_value.to_dict.return_value = {"tasa_nmv_banco": 1.5}
    mock_db.collection.return_value.document.return_value.collection.return_value.stream.return_value = mock_docs
    
    service = ConfigService()
    service.initialize(mock_db)
    
    partners = service.get_partners_config()
    
    assert partners is not None, "get_partners_config() retornó None"
    assert len(partners) > 0, "get_partners_config() retornó un diccionario vacío"
    assert partners.get("link_banco_bogota") == "https://bogota.com", "Fallo mapeo link_url"
    assert partners.get("link_brilla") == "https://brilla.com", "Fallo mapeo link"
    assert partners.get("link_crediorbe") == "https://crediorbe.com", "Fallo mapeo url"

