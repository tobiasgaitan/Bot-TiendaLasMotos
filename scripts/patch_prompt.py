#!/usr/bin/env python3
"""
Admin Maintenance Script: Patch Live System Prompt in Firestore (v2.1.0)
========================================================================
Surgically updates <phase_1_profiling> and <phase_2_habeas_data_accepted> blocks.
"""

import sys
import re
from google.cloud import firestore

PROJECT_ID = "tiendalasmotos"
COLLECTION = "configuracion"
DOCUMENT = "juan_pablo_personality"
FIELD = "system_instruction"

# ========================================================
# CONTRATO JSON v2.1.0 - MODIFICACIONES APROBADAS
# ========================================================

PHASE_1_REPLACEMENT = """  <phase_1_profiling>
    Objetivo: Obtener Nombre, Ciudad, Moto de Interés y Forma de Pago (Crédito/Contado).
    - Un dato a la vez.
    - Si ya recomendaste una moto, no preguntes "¿Qué moto buscas?", sino "¿Te gustaría saber más de la [Moto]?".
    - BLOQUEO: Bajo ninguna circunstancia inicies el protocolo de Habeas Data si las variables Ciudad y Forma de Pago son desconocidas.
  </phase_1_profiling>"""

PHASE_2_REPLACEMENT = """  <phase_2_habeas_data_accepted>
    Objetivo: Obtener autorización legal.
    - SCRIPT OBLIGATORIO: Solicita autorización de datos de forma natural y entrega el link de la política solo si el usuario acepta y ha confirmado previamente su interés en una moto.
    - Si dicen "No", respeta su decisión y responde dudas generales.
  </phase_2_habeas_data_accepted>"""

def surgical_patch(current_text: str) -> str:
    """
    Finds and replaces <phase_1_profiling> and <phase_2_habeas_data_accepted> blocks.
    Ensures that other parts of the prompt (Rules, Persona, Phase 3) are untouched.
    """
    # Patch Phase 1
    p1_pattern = r'<phase_1_profiling>.*?</phase_1_profiling>'
    if not re.search(p1_pattern, current_text, re.DOTALL):
        raise ValueError("❌ Error: <phase_1_profiling> tag NO encontrado en Firestore.")
    
    patched = re.sub(p1_pattern, PHASE_1_REPLACEMENT, current_text, flags=re.DOTALL)
    
    # Patch Phase 2
    p2_pattern = r'<phase_2_habeas_data_accepted>.*?</phase_2_habeas_data_accepted>'
    if not re.search(p2_pattern, patched, re.DOTALL):
        raise ValueError("❌ Error: <phase_2_habeas_data_accepted> tag NO encontrado en Firestore.")
    
    patched = re.sub(p2_pattern, PHASE_2_REPLACEMENT, patched, flags=re.DOTALL)
    
    return patched

def main():
    print("=" * 60)
    print("Firestore System Prompt Patch Tool (JSON Voorhees v2.1.0)")
    print("=" * 60)

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
        print(f"❌ Documento no encontrado.")
        sys.exit(1)

    current_prompt = doc.to_dict().get(FIELD, "")
    if not current_prompt:
        print(f"❌ Campo '{FIELD}' vacío o no existe.")
        sys.exit(1)

    print(f"✅ Documento cargado exitosamente ({len(current_prompt)} caracteres).")

    try:
        patched_prompt = surgical_patch(current_prompt)
        print("✅ Parche quirúrgico aplicado exitosamente en memoria.")
    except ValueError as ve:
        print(ve)
        sys.exit(1)

    # Mostrar cambios (diff manual simple)
    print("\n--- RESUMEN DE CAMBIOS ---")
    print("Inyectado: BLOQUEO de Fase 1 (Ciudad/Pago)")
    print("Inyectado: SCRIPT OBLIGATORIO de Fase 2 (Autorización)")
    print("--------------------------\n")

    # Guardar cambios
    doc_ref.update({FIELD: patched_prompt})
    print(f"🚀 Firestore ACTUALIZADO: {COLLECTION}/{DOCUMENT}")
    print("Puntos de control de seguridad validados.")

if __name__ == "__main__":
    main()
