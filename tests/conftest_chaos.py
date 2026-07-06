import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from contextlib import asynccontextmanager
import time

@pytest.fixture
def slow_async_mock():
    """Factory to create an AsyncMock that sleeps before returning."""
    def _create_mock(return_value=None, delay=0.1):
        async def _mock(*args, **kwargs):
            await asyncio.sleep(delay)
            return return_value
        return AsyncMock(side_effect=_mock)
    return _create_mock

@pytest.fixture
def timed_assertion():
    """Context manager to assert that a block executes within a maximum time window."""
    @asynccontextmanager
    async def _assert_time(max_seconds: float):
        start = time.perf_counter()
        yield
        elapsed = time.perf_counter() - start
        assert elapsed < max_seconds, f"Execution took {elapsed:.2f}s, exceeding maximum of {max_seconds}s"
    return _assert_time

@pytest.fixture
def mock_firestore_with_latency():
    """Mock Firestore with configurable I/O latency."""
    def _create_mock(latency=0.1):
        db = MagicMock()
        async def _slow_get(*args, **kwargs):
            await asyncio.sleep(latency)
            doc = MagicMock()
            doc.exists = True
            doc.to_dict.return_value = {}
            return doc
            
        async def _slow_set(*args, **kwargs):
            await asyncio.sleep(latency)
            return True
            
        db.collection.return_value.document.return_value.get = AsyncMock(side_effect=_slow_get)
        db.collection.return_value.document.return_value.set = AsyncMock(side_effect=_slow_set)
        return db
    return _create_mock

@pytest.fixture
def mock_gemini_with_latency():
    """Mock Gemini AI Brain with configurable generation latency."""
    def _create_mock(latency=2.0, return_text="Respuesta generada"):
        cerebro = MagicMock()
        async def _slow_generate(*args, **kwargs):
            await asyncio.sleep(latency)
            return return_text
        cerebro.pensar_respuesta = AsyncMock(side_effect=_slow_generate)
        return cerebro
    return _create_mock

@pytest.fixture
def concurrent_webhook_factory():
    """Factory to generate multiple concurrent webhook payloads."""
    def _generate(count=5, phone_base="5730000000"):
        payloads = []
        for i in range(count):
            phone = f"{phone_base}{str(i).zfill(2)}"
            payloads.append({
                "object": "whatsapp_business_account",
                "entry": [{
                    "id": "123",
                    "changes": [{
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "123456", "phone_number_id": "999999"},
                            "messages": [{
                                "from": phone,
                                "id": f"wamid.{i}",
                                "timestamp": "1672531199",
                                "text": {"body": "Mensaje concurrente"},
                                "type": "text"
                            }]
                        },
                        "field": "messages"
                    }]
                }]
            })
        return payloads
    return _generate
