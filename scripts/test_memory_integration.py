"""
Diagnostic Script - Test CRM Memory Integration
Tests if memory service can find Capitán Victoria's prospect data.
"""

import os
import sys
from google.cloud import firestore
from google.oauth2 import service_account

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.memory_service import MemoryService

def main():
    print("=" * 70)
    print("CRM MEMORY INTEGRATION - DIAGNOSTIC TEST")
    print("=" * 70)
    
    # Initialize Firestore
    print("\n1️⃣  Initializing Firestore...")
    try:
        db = firestore.Client(project="tiendalasmotos")
        print("✅ Firestore client initialized")
    except Exception as e:
        print(f"❌ Failed to initialize Firestore: {e}")
        return
    
    # Initialize Memory Service
    print("\n2️⃣  Initializing Memory Service...")
    try:
        memory_service = MemoryService(db)
        print("✅ Memory service initialized")
    except Exception as e:
        print(f"❌ Failed to initialize memory service: {e}")
        return
    
    # Test phone numbers
    test_phones = [
        "573192564288",  # Full format with country code
        "+573192564288", # With + prefix
        "3192564288",    # Short format (what should be in Firestore)
    ]
    
    print("\n3️⃣  Testing Prospect Data Retrieval...")
    print("-" * 70)
    
    for phone in test_phones:
        print(f"\n📞 Testing phone: {phone}")
        try:
            prospect_data = memory_service.get_prospect_data(phone)
            
            if prospect_data and prospect_data.get("exists"):
                print(f"   ✅ FOUND!")
                print(f"   - Name: {prospect_data.get('name')}")
                print(f"   - Moto Interest: {prospect_data.get('moto_interest')}")
                print(f"   - Has Summary: {prospect_data.get('summary') is not None}")
            else:
                print(f"   ❌ NOT FOUND")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
    
    # Check Firestore directly
    print("\n4️⃣  Checking Firestore Collection Directly...")
    print("-" * 70)
    
    try:
        prospectos_ref = db.collection("prospectos")
        
        # Try to find by celular field
        for test_celular in ["3192564288", "573192564288", "+573192564288"]:
            print(f"\n🔍 Querying WHERE celular == '{test_celular}'")
            query = prospectos_ref.where("celular", "==", test_celular).limit(5)
            docs = query.get()
            
            if docs:
                for doc in docs:
                    data = doc.to_dict()
                    print(f"   ✅ Found document ID: {doc.id}")
                    print(f"      - celular: {data.get('celular')}")
                    print(f"      - nombre: {data.get('nombre')}")
                    print(f"      - motoInteres: {data.get('motoInteres')}")
            else:
                print(f"   ❌ No documents found")
        
        # List all prospects
        print(f"\n📋 Listing ALL prospects in collection...")
        all_docs = prospectos_ref.limit(10).get()
        
        if all_docs:
            print(f"   Found {len(list(all_docs))} prospect(s):")
            for doc in prospectos_ref.limit(10).get():
                data = doc.to_dict()
                print(f"   - ID: {doc.id} | celular: {data.get('celular')} | nombre: {data.get('nombre')}")
        else:
            print(f"   ⚠️  Collection is EMPTY!")
            
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
    
    print("\n" + "=" * 70)
    print("DIAGNOSTIC TEST COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    main()
