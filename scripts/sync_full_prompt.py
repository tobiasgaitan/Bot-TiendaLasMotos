import os
import sys

# Añadir el path actual para poder importar la app
sys.path.append(os.getcwd())

from google.cloud import firestore
from app.core.prompts import JUAN_PABLO_SYSTEM_INSTRUCTION

PROJECT_ID = "tiendalasmotos"
COLLECTION = "configuracion"
DOCUMENT = "juan_pablo_personality"
FIELD = "system_instruction"

def main():
    print("=" * 60)
    print("🚀 FULL PROMPT SYNC: Firestore ↔️ app/core/prompts.py")
    print("=" * 60)

    db = firestore.Client(project=PROJECT_ID)
    doc_ref = db.collection(COLLECTION).document(DOCUMENT)

    print(f"📡 Subiendo prompt local ({len(JUAN_PABLO_SYSTEM_INSTRUCTION)} caracteres)...")
    
    try:
        doc_ref.update({FIELD: JUAN_PABLO_SYSTEM_INSTRUCTION})
        print("✅ ÉXITO: Firestore ha sido actualizado con la versión auditada.")
        print("💡 Ahora la base de datos y tu código son espejos idénticos.")
    except Exception as e:
        print(f"❌ ERROR CRÍTICO: {e}")

if __name__ == "__main__":
    main()
