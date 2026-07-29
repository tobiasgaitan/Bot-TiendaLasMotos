import sys
import os
import logging
from unittest.mock import MagicMock, patch

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# [H-ARNÉS-7 / M4-PLAN-ARNÉS-7-002] Import-time PURO: el mock de sys.modules
# (google.cloud / google.cloud.firestore) y los imports que protegía se
# movieron VERBATIM dentro de test_memory_service_integration() vía patch.dict
# (patrón M4-003, scripts/test_v25_audio.py). Importar este módulo ya no
# envenena sys.modules del proceso. Sentinels de runtime:
MemoryService = None
PhoneNormalizer = None

# Setup logging
logging.basicConfig(level=logging.INFO)

def test_memory_service_integration():
    global MemoryService, PhoneNormalizer
    # Mock google.cloud.firestore before importing services that depend on it
    with patch.dict(sys.modules, {"google.cloud": MagicMock(),
                                  "google.cloud.firestore": MagicMock()}):
        from app.services.memory_service import MemoryService
        from app.core.utils import PhoneNormalizer

    print("🧪 STARTING MEMORY SERVICE VERIFICATION 🧪")
    
    # Mock DB client
    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_document = MagicMock()
    
    # Setup chain: db.collection("prospectos").document(ID)
    mock_db.collection.return_value = mock_collection
    mock_collection.document.return_value = mock_document
    mock_document.get.return_value.exists = False # Simulate new user
    
    # Initialize Service
    service = MemoryService(mock_db)
    
    # Test Input
    raw_input = "+57 300 123 4567"
    expected_id = "3001234567"
    
    print(f"🔹 Input Phone: '{raw_input}'")
    print(f"🔹 Expected ID: '{expected_id}'")
    
    # Execute
    service.get_prospect_data(raw_input)
    
    # Verify
    mock_db.collection.assert_called_with("prospectos")
    
    # CHECK THE CRITICAL PART: Did we call document() with the NORMALIZED ID?
    # We retrieve the arguments called on document()
    call_args = mock_collection.document.call_args
    actual_id = call_args[0][0]
    
    print(f"🔹 Actual ID used in Firestore: '{actual_id}'")
    
    if actual_id == expected_id:
        print("✅ SUCCESS: MemoryService is using the normalized ID!")
    else:
        print(f"❌ FAILURE: MemoryService used '{actual_id}' instead of '{expected_id}'")
        sys.exit(1)

if __name__ == "__main__":
    test_memory_service_integration()
