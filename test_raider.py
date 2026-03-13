import asyncio
import sys
import os

# Ensure the app module is in the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.catalog_service import CatalogService
from google.cloud import firestore

def test_search():
    print("--- TESTING CATALOG SERVICE ---")
    db = firestore.Client(project="tiendalasmotos")
    catalog = CatalogService()
    catalog.initialize(db)
    
    print("\nExecuting search_items('Raider')...")
    results = catalog.search_items("Raider")
    
    if not results:
        print("No results returned.")
    else:
        for r in results:
            item = r['item']
            score = r['score']
            print(f"- Item: {item.get('name', 'Unknown')} | Score: {score}")
            print(f"  Categories: {item.get('categories', [])}")
            print(f"  Tags: {item.get('search_tags', [])}")
            print(f"  Keywords: {item.get('keywords', [])}")
            print(f"  Category Aliases: {item.get('category_aliases', [])}")

def test_firestore_state():
    print("\n--- TESTING FIRESTORE STATE ---")
    db = firestore.Client(project="tiendalasmotos")
    docs = db.collection("pagina").document("catalogo").collection("items").stream()
    
    found_raider = False
    for doc in docs:
        data = doc.to_dict()
        ref_val = data.get("referencia") or data.get("nombre") or data.get("title") or doc.id
        brand = data.get("marca", "") or data.get("brand", "")
        name = f"{brand} {ref_val}".strip() if brand else str(ref_val).strip()
        
        if "raider" in name.lower() or "raider" in str(ref_val).lower() or "raider" in doc.id.lower():
            found_raider = True
            print(f"FOUND RAIDER DOCUMENT:")
            print(f"  ID: {doc.id}")
            print(f"  Name: {name}")
            print(f"  Status: {data.get('status', 'NOT SET (Assumed Active/Inactive?)')}")
            print(f"  Stock: {data.get('estado', 'NOT SET')}")
            print("  ---")
            
    if not found_raider:
        print("No document for 'Raider' found in Firestore collection 'pagina/catalogo/items'.")

if __name__ == "__main__":
    test_search()
    test_firestore_state()
