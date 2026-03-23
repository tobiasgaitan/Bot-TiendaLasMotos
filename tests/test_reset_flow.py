import pytest
from unittest.mock import MagicMock
from app.services.memory_service import MemoryService

@pytest.fixture
def memory_service():
    mock_db = MagicMock()
    return MemoryService(db=mock_db)

def test_create_prospect_initializes_habeas_data_false(memory_service):
    """
    Test que verifica que create_prospect_if_missing inicializa explícitamente Habeas Data en False.
    """
    # Mock doc.get().exists para simular que no existe
    mock_doc = MagicMock()
    mock_doc.get.return_value.exists = False
    
    # Configuramos el mock del DB para devolver nuestro mock_doc
    memory_service._db.collection.return_value.document.return_value = mock_doc
    
    # Ejecutamos la creación
    memory_service.create_prospect_if_missing("3227303760")
    
    # Verificamos los datos enviados a set()
    args, _ = mock_doc.set.call_args
    data = args[0]
    
    assert data["habeas_data_accepted"] is False, "habeas_data_accepted debe ser False al crear un prospecto"
    assert data["habeas_data_sent"] is False, "habeas_data_sent debe ser False al crear un prospecto"
    assert data["celular"] == "3227303760"

def test_merge_after_reset_does_not_latch_true(memory_service):
    """
    Test que verifica que si el dato actual es False (post-reset), la IA no lo autocompleta como True.
    """
    current_data = {
        "habeas_data_accepted": False, # Estado explícito tras reset
        "habeas_data_sent": False
    }
    
    incoming_extracted = {
        "habeas_data_accepted": False
    }
    
    merged = memory_service._merge_extracted_data(current_data, incoming_extracted)
    
    # Debe permanecer en False porque existing_val era False (no se activa el latch)
    assert merged["habeas_data_accepted"] is False

def test_merge_still_latches_true_if_already_true(memory_service):
    """
    Test de regresión: El latch debe seguir funcionando si el valor ya era True.
    """
    current_data = {
        "habeas_data_accepted": True
    }
    incoming_extracted = {
        "habeas_data_accepted": False
    }
    merged = memory_service._merge_extracted_data(current_data, incoming_extracted)
    assert merged["habeas_data_accepted"] is True, "El latch debe mantener True si el valor existente era True"
