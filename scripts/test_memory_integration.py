import os
import sys
import asyncio
from google.cloud import firestore

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.memory_service import MemoryService
from app.core.utils import PhoneNormalizer

async def main():
    print("=" * 70)
    print("CRM MEMORY INTEGRATION - DIAGNOSTIC TEST (ASYNC v9.0.0)")
    print("=" * 70)
    
    print("\n1️⃣  Initializing Firestore...")
    try:
        db = firestore.AsyncClient(project="tiendalasmotos")
        print("✅ Firestore client initialized")
    except Exception as e:
        print(f"❌ Failed to initialize Firestore: {e}")
        return
    
    print("\n2️⃣  Initializing Memory Service...")
    try:
        memory_service = MemoryService(db)
        print("✅ Memory service initialized")
    except Exception as e:
        print(f"❌ Failed to initialize memory service: {e}")
        return
    
    test_phones = ["573192564288", "+573192564288", "3192564288"]
    
    print("\n3️⃣  Testing Prospect Data Retrieval...")
    for phone in test_phones:
        print(f"\n📞 Testing phone: {phone}")
        try:
            prospect_data = await memory_service.get_prospect_data(phone)
            if prospect_data.get("exists") is False:
                print("   ❌ No existe en memoria local")
            else:
                print(f"   ✅ DATA: {prospect_data.get('nombre', 'Sin nombre')}")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")

    print("\n4️⃣  Checking Firestore Collection Directly...")
    for phone in test_phones:
        clean = PhoneNormalizer.normalize(phone)
        print(f"\n🔍 Querying direct doc: {clean}")
        doc = await db.collection("prospectos").document(clean).get()
        if doc.exists:
            print(f"   ✅ Found: {doc.to_dict().get('nombre')}")
        else:
            print("   ❌ Not found")

if __name__ == "__main__":
    asyncio.run(main())
