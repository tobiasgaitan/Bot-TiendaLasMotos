import pytest
from unittest.mock import MagicMock, patch
import sys
import os

# Asegurar que el path del proyecto esté disponible
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@pytest.fixture(autouse=True)
def mock_env_vars():
    """Mocks de variables de entorno para evitar fallos de configuración."""
    with patch.dict(os.environ, {"GOOGLE_APPLICATION_CREDENTIALS": "/tmp/fake-key.json"}):
        yield

@pytest.fixture
def mock_prospect_data():
    """Fixture de datos de prospecto para pruebas de anclaje CRM."""
    return {
        "exists": True,
        "nombre": "Juan Perez",
        "moto_interes": "TVS APACHE 160",
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
