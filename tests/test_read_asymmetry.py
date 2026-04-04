import pytest
from unittest.mock import MagicMock, patch
from app.services.memory_service import MemoryService
from google.cloud import firestore

@pytest.fixture
def memory_service():
    mock_db = MagicMock()
    return MemoryService(db=mock_db)

def test_template_sanitization_initialization(memory_service):
    """
    Test Rule: TEMPLATE_SANITIZATION (v6.9.4)
    Verify that create_prospect_if_missing uses canonical keys and NO legacy keys.
    """
    mock_doc = MagicMock()
    mock_doc.exists = False
    memory_service._db.collection().document().get.return_value = mock_doc
    
    phone = "573001234567"
    memory_service.create_prospect_if_missing(phone)
    
    # Check what was sent to .set()
    args, kwargs = memory_service._db.collection().document().set.call_args
    sent_data = args[0]
    
    assert "habeasData" in sent_data
    assert "serviciosPublicos" in sent_data
    assert "habeas_data_accepted" not in sent_data
    assert sent_data["habeasData"] is False
    assert sent_data["serviciosPublicos"] is None

def test_reverse_mapping_retrieval(memory_service):
    """
    Test Rule: REVERSE_MAPPING (v6.9.4)
    Verify that reading canonical Firestore keys returns legacy keys for Gemini.
    """
    mock_doc = MagicMock()
    mock_doc.exists = True
    # Simulate Firestore document with ONLY canonical keys
    mock_doc.to_dict.return_value = {
        "habeasData": True,
        "serviciosPublicos": "Brilla",
        "nombre": "Test User"
    }
    
    # Mock _find_prospect_ref to return a ref that returns our mock_doc
    mock_ref = MagicMock()
    mock_ref.get.return_value = mock_doc
    memory_service._find_prospect_ref = MagicMock(return_value=mock_ref)
    
    result = memory_service._get_prospect_data_sync("123")
    
    # Verify the AI-facing dictionary has legacy keys populated from canonical ones
    assert result["habeas_data_accepted"] is True
    assert result["servicios_publicos"] == "Brilla"
    assert "habeasData" not in result # Should be cleaned for AI output

def test_collision_neutralization_priority(memory_service):
    """
    Test Rule: COLLISION_NEUTRALIZATION (v6.9.4)
    If both legacy and canonical keys exist, canonical must prevail.
    """
    mock_doc = MagicMock()
    mock_doc.exists = True
    # Simulate a document in a "bleeding" state
    mock_doc.to_dict.return_value = {
        "habeasData": True,             # Canonical says accepted
        "habeas_data_accepted": False,   # Legacy says rejected (STALE)
        "serviciosPublicos": "Crediorbe",
        "servicios_publicos": None
    }
    
    mock_ref = MagicMock()
    mock_ref.get.return_value = mock_doc
    memory_service._find_prospect_ref = MagicMock(return_value=mock_ref)
    
    result = memory_service._get_prospect_data_sync("123")
    
    # Verify that the canonical value (True) won over the legacy one (False)
    assert result["habeas_data_accepted"] is True
    assert result["servicios_publicos"] == "Crediorbe"
