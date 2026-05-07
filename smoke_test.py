import asyncio
from app.services.memory_service import MemoryService
from google.cloud import firestore

async def run_test():
    db = firestore.AsyncClient(project="tiendalasmotos")
    ms = MemoryService(db)
    # The normalizer is used in memory service somewhere, let's see how it formats
    phone = "573001234567"
    data = await ms.get_prospect_data(phone)
    print(f"Tested phone {phone}, prospect data: {data}")

if __name__ == "__main__":
    asyncio.run(run_test())
