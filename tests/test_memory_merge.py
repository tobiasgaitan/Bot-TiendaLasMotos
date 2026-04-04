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
        "nombre": "Juan Pablo Garcés",
        "ciudad": None,
        "forma_pago": ""
    }
    
    merged = memory_service._merge_extracted_data(current_data, incoming_extracted)
    
    assert merged["nombre"] == "Juan Pablo Garcés"
    # city and payment_method should NOT be in merged (preserving current Firestore values)
    assert "ciudad" not in merged
    assert "forma_pago" not in merged

def test_merge_strategy_latch_true_only(memory_service):
    """
    Test Rule: LATCH_TRUE_ONLY (v6.9.3)
    Boolean flags cannot transition from True to False.
    Verify transition to canonical keys (habeasData).
    """
    current_data = {
        "habeasData": True,
        "habeas_data_sent": True,
        "moto_confirmada": False
    }
    
    # AI accidentally sends False for accepted flags
    incoming_extracted = {
        "habeas_data_accepted": False,
        "habeas_data_sent": None,
        "moto_confirmada": True
    }
    
    merged = memory_service._merge_extracted_data(current_data, incoming_extracted)
    
    # Latch should keep them True in the canonical field
    assert merged["habeasData"] is True
    # 'habeas_data_accepted' must be POPPED (Destructive Mutation)
    assert "habeas_data_accepted" not in merged
    # 'moto_confirmada' should upgrade to True
    assert merged["moto_confirmada"] is True

def test_merge_strategy_pop_destructive(memory_service):
    """
    Verify that ALL mapped keys are popped from the incoming dict to prevent bleeding.
    """
    incoming = {
        "habeas_data_accepted": True,
        "servicios_publicos": "gas_natural"
    }
    current = {}
    
    merged = memory_service._merge_extracted_data(current, incoming)
    
    # Check canonical keys exist
    assert merged["habeasData"] is True
    assert merged["serviciosPublicos"] == "gas_natural"
    
    # Check legacy/source keys are gone from result
    assert "habeas_data_accepted" not in merged
    assert "servicios_publicos" not in merged


def test_merge_strategy_full_mapping_spanish(memory_service):
    """
    Tests that all keys are correctly handled using target nomenclature.
    """
    current_data = {}
    incoming_extracted = {
        "nombre": "Test User",
        "ciudad": "Bogotá",
        "moto_interest": "TVS Apache",
        "forma_pago": "Contado",
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
    assert merged["moto_interest"] == "TVS Apache"
    assert merged["forma_pago"] == "Contado"
    assert merged["ocupacion"] == "Ingeniero"
    assert merged["datacredito"] == "Aprobado"
    assert merged["moto_competidor"] == "Honda CB 125"

def test_is_valid_helper_logic(memory_service):
    """
    Tests the internal is_valid logic inside _merge_extracted_data.
    """
    current = {"nombre": "Existing"}
    
    case_invalid = {"nombre": "null"}
    merged_invalid = memory_service._merge_extracted_data(current, case_invalid)
    assert "nombre" not in merged_invalid
    
    case_empty = {"nombre": "  "}
    merged_empty = memory_service._merge_extracted_data(current, case_empty)
    assert "nombre" not in merged_empty
    
    case_valid = {"nombre": "Juan"}
    merged_valid = memory_service._merge_extracted_data(current, case_valid)
    assert merged_valid["nombre"] == "Juan"

