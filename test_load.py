from google.cloud import firestore

db = firestore.Client()
items_ref = db.collection("pagina").document("catalogo").collection("items")
docs = items_ref.stream()

for doc in docs:
    data = doc.to_dict()
    is_visible = data.get("isVisible", True)
    if not is_visible:
        print(f"[{doc.id}] keys: {list(data.keys())}")
        print(f"[{doc.id}] isVisible: {data.get('isVisible')}, active: {data.get('active')}, onStock: {data.get('onStock')}")
