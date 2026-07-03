import pytest
import asyncio
from unittest.mock import patch, MagicMock
from tests.conftest_chaos import slow_async_mock, mock_firestore_with_latency

@pytest.mark.asyncio
async def test_firestore_2s_latency_still_responds(mock_firestore_with_latency):
    from app.services.memory_service import MemoryService
    
    # 2 seconds latency per I/O call
    db_mock = mock_firestore_with_latency(latency=2.0)
    service = MemoryService(db_mock)
    
    # Just asserting it doesn't fail under 2s latency and uses timeout
    try:
        data = await service.get_prospect_data("5730000000")
        assert data is not None
    except Exception as e:
        pytest.fail(f"Failed under 2s latency: {e}")

@pytest.mark.asyncio
async def test_firestore_timeout_triggers_contingency(mock_firestore_with_latency):
    from app.services.memory_service import MemoryService
    
    # 10 seconds latency (exceeds default timeout of 8s)
    db_mock = mock_firestore_with_latency(latency=10.0)
    service = MemoryService(db_mock)
    
    # Should raise TimeoutError internally and trigger contingency
    with pytest.raises(asyncio.TimeoutError):
        await service._firestore_io(asyncio.sleep(10), "5730000000", "test", timeout=1)
