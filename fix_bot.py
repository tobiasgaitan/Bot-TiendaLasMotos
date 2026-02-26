import asyncio
from app.core.config_loader import ConfigLoader
from app.core.firebase_admin_setup import get_firestore_client
from app.core.prompts import JUAN_PABLO_SYSTEM_INSTRUCTION

db = get_firestore_client()
print("Updating juan_pablo_personality...")
doc_ref = db.collection("configuracion").document("juan_pablo_personality")
doc_ref.set({"system_instruction": JUAN_PABLO_SYSTEM_INSTRUCTION}, merge=True)
print("Updated successfully.")
