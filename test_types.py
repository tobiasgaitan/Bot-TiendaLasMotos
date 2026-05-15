import json
from google.cloud import firestore
db = firestore.Client()
docs = db.collection("pagina").document("catalogo").collection("items").stream()
types = {}
for doc in docs:
    data = doc.to_dict()
    v = data.get("isVisible")
    t = type(v).__name__
    types[t] = types.get(t, 0) + 1
print("isVisible types:", types)
