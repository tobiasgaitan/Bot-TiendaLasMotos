#!/usr/bin/env python3
"""
Admin Maintenance Script: Sync Live System Prompt to Firestore (v3.0.0)
========================================================================
Sincroniza el prompt desde app/core/prompts.py (fuente de verdad) hacia
Firestore: configuracion/juan_pablo_personality.system_instruction.
No depende de regex ni de etiquetas específicas.
"""

import sys
import os
from datetime import datetime

# Añadir el proyecto al path para importar prompts
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.cloud import firestore
from app.core.prompts import JUAN_PABLO_SYSTEM_INSTRUCTION

PROJECT_ID = "tiendalasmotos"
COLLECTION = "configuracion"
DOCUMENT = "juan_pablo_personality"
FIELD = "system_instruction"


def main():
    print("=" * 60)
    print("Firestore System Prompt Sync Tool (v3.0.0)")
    print("=" * 60)

    # 1. Validar que el prompt fuente no esté vacío
    if not JUAN_PABLO_SYSTEM_INSTRUCTION or len(JUAN_PABLO_SYSTEM_INSTRUCTION.strip()) < 100:
        print("❌ Error: JUAN_PABLO_SYSTEM_INSTRUCTION está vacío o es demasiado corto.")
        print(f"   Longitud actual: {len(JUAN_PABLO_SYSTEM_INSTRUCTION or '')} caracteres.")
        sys.exit(1)

    print(f"✅ Prompt fuente cargado: {len(JUAN_PABLO_SYSTEM_INSTRUCTION)} caracteres.")

    # 2. Conectar a Firestore
    print(f"🔌 Conectando a Firestore: {PROJECT_ID}/{COLLECTION}/{DOCUMENT}...")
    try:
        db = firestore.Client(project=PROJECT_ID)
        doc_ref = db.collection(COLLECTION).document(DOCUMENT)
        doc = doc_ref.get()
    except Exception as e:
        print(f"❌ Error de conexión/autenticación: {e}")
        print("Asegúrese de haber ejecutado 'gcloud auth application-default login'.")
        sys.exit(1)

    if not doc.exists:
        print(f"❌ Documento no encontrado. Creando nuevo...")

    # 3. Mostrar resumen de cambios
    current_prompt = doc.to_dict().get(FIELD, "") if doc.exists else ""
    if current_prompt:
        diff_size = len(JUAN_PABLO_SYSTEM_INSTRUCTION) - len(current_prompt)
        diff_symbol = "+" if diff_size >= 0 else ""
        print(f"📊 Tamaño actual en Firestore: {len(current_prompt)} caracteres")
        print(f"📊 Nuevo tamaño: {len(JUAN_PABLO_SYSTEM_INSTRUCTION)} caracteres ({diff_symbol}{diff_size})")
    else:
        print("📊 Documento nuevo (no existía antes).")

    # 4. Subir el prompt
    try:
        doc_ref.set({
            FIELD: JUAN_PABLO_SYSTEM_INSTRUCTION,
            "synced_by": "patch_prompt_v3",
            "synced_at": datetime.utcnow().isoformat() + "Z"
        })
        print(f"🚀 Firestore ACTUALIZADO: {COLLECTION}/{DOCUMENT}")
        print("✅ Prompt sincronizado exitosamente.")
    except Exception as e:
        print(f"❌ Error al actualizar Firestore: {e}")
        sys.exit(1)

    # 5. Verificación
    verify_doc = doc_ref.get()
    verify_text = verify_doc.to_dict().get(FIELD, "")
    if verify_text == JUAN_PABLO_SYSTEM_INSTRUCTION:
        print("✅ Verificación: el prompt en Firestore coincide con el fuente.")
    else:
        print(f"⚠️  Verificación: discrepancia detectada.")
        print(f"   Fuente: {len(JUAN_PABLO_SYSTEM_INSTRUCTION)} chars")
        print(f"   Firestore: {len(verify_text)} chars")


if __name__ == "__main__":
    main()