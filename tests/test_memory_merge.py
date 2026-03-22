import pytest
from unittest.mock import MagicMock
from app.services.memory_service import MemoryService

@pytest.fixture
def memory_service():
    # Mocking dependencies for MemoryService
    mock_db = MagicMock()
    return MemoryService(db=mock_db)

def test_merge_strategy_preserve_historic_valid(memory_service):
    """
    Test Rule: PRESERVE_IF_HISTORIC_VALID
    Incoming null/empty does NOT overwrite existing valid data.
    """
    current_data = {
        "nombre": "Juan Pablo",
        "ciudad": "Medellín",
        "forma_pago": "Crédito"
    }
    
    # AI extracts name but forgets city and payment method
    incoming_extracted = {
        "name": "Juan Pablo Garcés",
        "city": None,
        "payment_method": ""
    }
    
    merged = memory_service._merge_extracted_data(current_data, incoming_extracted)
    
    # 'nombre' should be updated
    assert merged["nombre"] == "Juan Pablo Garcés"
    # 'ciudad' and 'forma_pago' should NOT be in merged (preserving current Firestore values)
    assert "ciudad" not in merged
    assert "forma_pago" not in merged

def test_merge_strategy_latch_true_only(memory_service):
    """
    Test Rule: LATCH_TRUE_ONLY
    Boolean flags cannot transition from True to False.
    """
    current_data = {
        "habeas_data_accepted": True,
        "habeas_data_sent": True,
        "moto_confirmada": False
    }
    
    # AI accidentally sends False for accepted flags
    incoming_extracted = {
        "habeas_data_accepted": False,
        "habeas_data_sent": None, # None should be ignored or handled by latch
        "moto_confirmada": True
    }
    
    merged = memory_service._merge_extracted_data(current_data, incoming_extracted)
    
    # Latch should keep them True
    assert merged["habeas_data_accepted"] is True
    # moto_confirmada should upgrade to True
    assert merged["moto_confirmada"] is True

def test_merge_strategy_full_mapping(memory_service):
    """
    Tests that all keys in the field map are correctly handled.
    """
    current_data = {}
    incoming_extracted = {
        "name": "Test User",
        "city": "Bogotá",
        "moto_interest": "TVS Apache",
        "payment_method": "Contado",
        "ocupacion": "Ingeniero",
        "datacredito": "Aprobado",
        "vivienda": "Propia",
        "ingresos": "5M",
        "gastos": "2M",
        "moto_competidor": "Honda CB 125",
        "moto_auteco": "Pulsar NS 200"
    }
    
    merged = memory_service._merge_extracted_data(current_data, incoming_extracted)
    
    assert merged["nombre"] == "Test User"
    assert merged["ciudad"] == "Bogotá"
    assert merged["motoInteres"] == "TVS Apache"
    assert merged["forma_pago"] == "Contado"
    assert merged["ocupacion"] == "Ingeniero"
    assert merged["datacredito"] == "Aprobado"
    assert merged["moto_competidor"] == "Honda CB 125"

def test_is_valid_helper_logic(memory_service):
    """
    Tests the internal is_valid logic inside _merge_extracted_data.
    """
    # Using a dummy current/incoming to trigger the is_valid logic inside the loop
    current = {"nombre": "Existing"}
    
    # Null strings or actual None should not trigger update
    case_invalid = {"name": "null"}
    merged_invalid = memory_service._merge_extracted_data(current, case_invalid)
    assert "nombre" not in merged_invalid
    
    case_empty = {"name": "  "}
    merged_empty = memory_service._merge_extracted_data(current, case_empty)
    assert "nombre" not in merged_empty
    
    case_valid = {"name": "Juan"}
    merged_valid = memory_service._merge_extracted_data(current, case_valid)
    assert merged_valid["nombre"] == "Juan"
