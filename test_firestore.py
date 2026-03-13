import sys
sys.path.append("/Users/tobiasgaitangallego/Bot-TiendaLasMotos")
from google.cloud import firestore

def main():
    # Try default initialization
    db = firestore.Client(project="tiendalasmotos")
    docs = db.collection("pagina").document("catalogo").collection("items").stream()
    targets = ["Bomber", "Combat", "TVS Sport"]
    print("--- FIRESTORE EXACT VALUES ---")
    
    count = 0
    for doc in docs:
        count += 1
        data = doc.to_dict()
        ref = data.get("referencia", "") or data.get("nombre", "") or ""
        brand = data.get("marca", "") or data.get("brand", "")
        title = data.get("title", "")
        # The logic from catalog_service is f"{brand} {ref}".strip() if brand else str(ref).strip()
        ref_val = data.get("referencia") or data.get("nombre") or data.get("title") or doc.id
        name = f"{brand} {ref_val}".strip() if brand else str(ref_val).strip()
        
        match = False
        for t in targets:
            if t.lower() in name.lower() or t.lower() in str(ref_val).lower():
                match = True
                break
                
        if match:
            print(f"ID: {doc.id}")
            print(f"  Name (calculated): {name}")
            print(f"  referencia: {repr(data.get('referencia'))}")
            print(f"  nombre: {repr(data.get('nombre'))}")
            print(f"  title: {repr(data.get('title'))}")
            print(f"  categoria: {repr(data.get('categoria'))}")
            print(f"  category: {repr(data.get('category'))}")
            print(f"  machine_name: {repr(data.get('machine_name'))}")
            print(f"  categories: {repr(data.get('categories'))}")
            print("  ---")
    
    print(f"Total documents scanned: {count}")

if __name__ == "__main__":
    main()
