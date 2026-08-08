import pytest
from unittest.mock import MagicMock, AsyncMock
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
    Test Rule: LATCH_TRUE_ONLY (v7.7.0 — Canonical Key: habeas_data_accepted)
    Boolean latch: once True, habeas_data_accepted must not revert to False.
    Verifies the canonical key 'habeas_data_accepted' used by MemoryService v7.7.0.
    """
    current_data = {
        "habeas_data_accepted": True,       # Canonical key (v7.7.0)
        "habeas_data_accepted_sent": True,
        "moto_confirmada": False
    }
    
    # AI accidentally sends False for accepted flags
    incoming_extracted = {
        "habeas_data_accepted": False,       # Canonical key — latch must prevent rollback
        "habeas_data_accepted_sent": None,
        "moto_confirmada": True
    }
    
    merged = memory_service._merge_extracted_data(current_data, incoming_extracted)
    
    # Latch must keep habeas_data_accepted True (canonical key)
    assert merged["habeas_data_accepted"] is True
    # 'moto_confirmada' should upgrade to True
    assert merged["moto_confirmada"] is True

def test_merge_strategy_pop_destructive(memory_service):
    """
    Verify that LATCH_TRUE_ONLY activates correctly when incoming habeas_data_accepted is True
    and current has no prior state (first acceptance).
    Uses canonical key 'habeas_data_accepted' as per MemoryService v7.7.0.
    """
    incoming = {
        "habeas_data_accepted": True,        # Canonical key (v7.7.0)
        "servicios_publicos": "gas_natural"
    }
    current = {}
    
    merged = memory_service._merge_extracted_data(current, incoming)
    
    # Canonical key must be present and True
    assert merged["habeas_data_accepted"] is True
    assert merged["servicios_publicos"] == "gas_natural"
    
    # No legacy aliases should bleed into the merged output
    assert "habeasData" not in merged
    assert "habeas_data" not in merged


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

def test_merge_strategy_spanish_keys_and_no_empty_strings(memory_service):
    """
    Mandatory test: Verifies presence of keys in Spanish and forbids empty strings or None silently.
    """
    current_data = {"fecha": "mock_timestamp"}
    incoming_data = {
        "nombre": "Tobias",
        "ciudad": "Bogotá",
        "forma_pago": "",
        "moto_interest": None,
        "null_key": "null",
        "none_key": "none"
    }
    merged = memory_service._merge_extracted_data(current_data, incoming_data)
    
    # Verify Spanish keys are accepted
    assert "nombre" in merged
    assert merged["nombre"] == "Tobias"
    assert "ciudad" in merged
    assert merged["ciudad"] == "Bogotá"
    
    # Verify empty strings and None are explicitly forbidden (not merged)
    assert "forma_pago" not in merged
    assert "moto_interest" not in merged
    
    # Verify sentinels like "null" or "none" are omitted
    assert "null_key" not in merged
    assert "none_key" not in merged

@pytest.mark.asyncio
async def test_generate_and_update_summary_anti_null_masking(caplog, memory_service):
    """
    [BOT-ARQ-ANTI-NULL-044] Aserción de contenido rígida.
    Verifica que la mutación o ausencia de llaves críticas (summary, extracted)
    fuerce la traza forense explícita en logger.warning antes de usar contingencia.
    """
    import logging
    
    # Mock AI brain to return mutated payload (missing 'extracted')
    mock_ai_brain = MagicMock()
    mock_ai_brain.generate_summary = AsyncMock(return_value={"summary": "test summary"})
    
    memory_service.update_prospect_summary = AsyncMock()

    with caplog.at_level(logging.WARNING):
        await memory_service.generate_and_update_summary(
            phone_number="1234567890",
            conversation_text="hello",
            ai_brain=mock_ai_brain
        )

    # Verificar que el log forense existe (Anti-Null Masking interceptado)
    log_messages = " ".join([r.message for r in caplog.records])
    assert "[ANTI-NULL-MASKING]" in log_messages, "❌ Fallo silencioso detectado. No se forzó la traza forense de advertencia."
    assert "Fallo de aserción rígida" in log_messages, "❌ Falta mensaje explícito en traza forense."

    # Verificar que update_prospect_summary igual fue llamado (contingencia funcionó)
    memory_service.update_prospect_summary.assert_called_once_with(
        "1234567890",
        "test summary",
        {},
        catalog_moto_hint=None,
    )
