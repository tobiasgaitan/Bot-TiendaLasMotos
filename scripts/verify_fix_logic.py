import sys
import os
import logging
from unittest.mock import MagicMock, patch

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock google.cloud.firestore before importing services that depend on it
sys.modules["google.cloud"] = MagicMock()
sys.modules["google.cloud.firestore"] = MagicMock()

from app.services.memory_service import MemoryService
from app.core.utils import PhoneNormalizer

# Setup logging
logging.basicConfig(level=logging.INFO)

def test_memory_service_integration():
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
