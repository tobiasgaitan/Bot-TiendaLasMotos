import os
import sys

# Asegurarnos de que importamos desde el app local
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from google.cloud import firestore
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    try:
        db = firestore.Client()
        collection_ref = db.collection("template_configs")
        
        # Documento 1
        doc1_ref = collection_ref.document("contactos_impulsa")
        doc1_ref.set({"fields": ["nombre", "moto_interes"]})
        logger.info("✅ Documento contactos_impulsa creado.")
        
        # Documento 2
        doc2_ref = collection_ref.document("leads_brilla_invitation")
        doc2_ref.set({"fields": ["nombre"]})
        logger.info("✅ Documento leads_brilla_invitation creado.")
        
    except Exception as e:
        logger.error(f"Error al inicializar Firestore: {e}")

if __name__ == "__main__":
    main()
