import asyncio
from unittest.mock import MagicMock
from google.cloud import firestore

from app.services.memory_service import MemoryService

def test_survey_state_integration():
    print("🧪 Starting Survey State Integration Test...")
    
    # 1. Mock Memory Service
    mock_db = MagicMock()
    memory_service = MemoryService(mock_db)
    
    mock_collection = MagicMock()
    mock_doc = MagicMock()
    
    mock_db.collection.return_value = mock_collection
    mock_collection.document.return_value = mock_doc
    
    # Test Save Focus
    print("\n   Testing save_survey_state...")
    phone = "573001234567"
    survey_id = "test_survey"
    current_step = "step_1"
    data = {"hello": "world"}
    
    memory_service.save_survey_state(phone, survey_id, current_step, data)
    
    print("   ✅ save_survey_state executed without error")
    mock_doc.update.assert_called()
    
    # Test Get
    print("\n   Testing get_survey_state...")
    mock_snapshot = MagicMock()
    mock_snapshot.exists = True
    mock_snapshot.to_dict.return_value = {
        "celular": phone,
        "survey_state": {
            "survey_id": survey_id,
            "current_step": current_step,
            "collected_data": data
        }
    }
    mock_doc.get.return_value = mock_snapshot
    
    state = memory_service.get_survey_state(phone)
    print(f"   ✅ Retrieved survey state: {state}")
    assert state is not None
    assert state['survey_id'] == survey_id
    assert state['current_step'] == current_step
    
    # Test Clear
    print("\n   Testing clear_survey_state...")
    memory_service.clear_survey_state(phone)
    print("   ✅ clear_survey_state executed without error")
    
    last_call_args = mock_doc.update.call_args[0][0]
    assert "survey_state" in last_call_args
    assert last_call_args["survey_state"] == firestore.DELETE_FIELD
    
    print("\n🎉 All tests passed!")

if __name__ == "__main__":
    test_survey_state_integration()
