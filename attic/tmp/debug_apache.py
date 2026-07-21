import sys
import os
from google.cloud import firestore

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def debug_apache():
    db = firestore.Client()
    items_ref = db.collection("pagina").document("catalogo").collection("items")
    
    # Buscar Apache 160
    docs = items_ref.where("name", "==", "APACHE 160 CARBURADA ABS").get()
    
    if not docs:
        # Try finding by ID
        print("🔍 Searching by ID apache_160_carburada_abs...")
        docs = [items_ref.document("apache_160_carburada_abs").get()]
        
    for doc in docs:
        if not doc.exists: continue
        data = doc.to_dict()
        print(f"\n--- DEBUG: {data.get('name')} (ID: {doc.id}) ---")
        print(f"Raíz 'cc': {data.get('cc')} (Tipo: {type(data.get('cc'))})")
        print(f"Raíz 'cilindraje': {data.get('cilindraje')} (Tipo: {type(data.get('cilindraje'))})")
        
        specs = data.get("fichatecnica") or data.get("ficha_tecnica") or {}
        if isinstance(specs, dict):
            print(f"Specs keys: {list(specs.keys())}")
            for k, v in specs.items():
                if "cilindra" in k.lower() or "cc" in k.lower():
                    print(f"Found Spec key '{k}': {v} (Tipo: {type(v)})")

if __name__ == "__main__":
    debug_apache()
