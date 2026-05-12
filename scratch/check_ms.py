import asyncio
from app.services.memory_service import MemoryService
from unittest.mock import AsyncMock

async def test_methods():
    ms = MemoryService(AsyncMock())
    print("Methods in MemoryService:")
    for method in dir(ms):
        if not method.startswith("__"):
            print(f" - {method}")

if __name__ == "__main__":
    asyncio.run(test_methods())
