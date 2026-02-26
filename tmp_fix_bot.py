from app.core.config import settings
from app.core.security import get_firebase_credentials_object
from google.cloud import firestore
from app.core.prompts import JUAN_PABLO_SYSTEM_INSTRUCTION

credentials = get_firebase_credentials_object()
db = firestore.Client(project=settings.gcp_project_id, credentials=credentials)
print("Updating juan_pablo_personality...")
doc_ref = db.collection("configuracion").document("juan_pablo_personality")
doc_ref.set({"system_instruction": JUAN_PABLO_SYSTEM_INSTRUCTION}, merge=True)
print("Updated successfully.")

print("\nChecking Victory Bomber image URL in Firestore...")
items_ref = db.collection("pagina").document("catalogo").collection("items")
docs = items_ref.stream()
for doc in docs:
    data = doc.to_dict()
    name = str(data.get("referencia") or data.get("nombre") or data.get("title") or doc.id).lower()
    if 'bomber' in name:
        print(f"Found {name}:")
        print(f"  imagenUrl mapping: {data.get('imagenUrl')}")
        print(f"  imagen string: {data.get('imagen')}")
        print(f"  foto string: {data.get('foto')}")
