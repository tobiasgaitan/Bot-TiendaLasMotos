import sys
import os
import pytest
from unittest.mock import patch, MagicMock

# Ensure the app module is in the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.catalog_service import CatalogService
from google.cloud import firestore

@patch("google.cloud.firestore.Client")
def test_search(mock_firestore_client):
    print("--- TESTING CATALOG SERVICE ---")
    db = mock_firestore_client.return_value
    
    # Simulate return from query
    mock_collection = MagicMock()
    mock_dbDocs = MagicMock()
    mock_doc = MagicMock()
    mock_doc.to_dict.return_value = {"name": "TVS Raider 125", "brand": "TVS", "referencia": "Raider", "categories": ["Urbanas"]}
    
    db.collection.return_value = mock_collection
    
    catalog = CatalogService()
    catalog.initialize(db)
    
    print("\nExecuting search_items('Raider')...")
    results = catalog.search_items("Raider")
    
    if not results:
        print("No results returned.")
    else:
        for item in results:
            print(f"- Item: {item.get('name', 'Unknown')}")
            print(f"  Categories: {item.get('categories', [])}")
            print(f"  Tags: {item.get('search_tags', [])}")
            print(f"  Keywords: {item.get('keywords', [])}")
            print(f"  Category Aliases: {item.get('category_aliases', [])}")
            print("  ---")

@patch("google.cloud.firestore.Client")
def test_firestore_state(mock_firestore_client):
    print("\n--- TESTING FIRESTORE STATE ---")
    db = mock_firestore_client.return_value
    
    # Mock documents iterator
    mock_doc = MagicMock()
    mock_doc.id = "doc123"
    mock_doc.to_dict.return_value = {"nombre": "Raider", "marca": "TVS", "status": "active", "estado": "in_stock"}
    
    mock_collection = MagicMock()
    mock_document = MagicMock()
    mock_collection2 = MagicMock()
    db.collection.return_value = mock_collection
    mock_collection.document.return_value = mock_document
    mock_document.collection.return_value = mock_collection2
    mock_collection2.stream.return_value = [mock_doc]
    
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
            print(f"  Status: {data.get('status', 'NOT SET')}")
            print(f"  Stock: {data.get('estado', 'NOT SET')}")
            print("  ---")
            
    if not found_raider:
        print("No document for 'Raider' found in Firestore collection 'pagina/catalogo/items'.")

if __name__ == "__main__":
    test_search()
    test_firestore_state()
