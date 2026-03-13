import os
from google.cloud import firestore
from app.services.catalog_service import CatalogService

def test_queries():
    db = firestore.Client()
    catalog = CatalogService(db)
    catalog.load_catalog()

    queries = ["crédito", "Raider a crédito", "motos street", "motos"]
    for q in queries:
        print(f"\n--- Searching for: '{q}' ---")
        results = catalog.search_items(q)
        for r in results:
            print(f"- {r['name']} (Score: {r.get('score', 'N/A')})")

if __name__ == "__main__":
    test_queries()
