#!/usr/bin/env python3
"""
Admin Maintenance Script: Patch Live System Prompt in Firestore
================================================================
WHEN TO RUN: Run this ONLY when the system_instruction field in
  configuracion/juan_pablo_personality needs to be updated.

WHERE TO RUN: From Cloud Shell (gcloud auth is pre-configured).
  DO NOT run locally unless you have ADC configured.

HOW TO RUN:
    cd /path/to/Bot-TiendaLasMotos
    python3 scripts/patch_prompt.py

WHAT IT DOES:
  1. Reads the live system_instruction from Firestore.
  2. Surgically replaces Phase 2 (Data Policy) and Phase 3 (Credit Survey)
     text blocks with the approved corrected copy.
  3. Writes the patched prompt back to Firestore.
  4. Prints a diff of before/after for verification.

SECURITY NOTE:
  This script does NOT overwrite the entire document. It only patches
  the system_instruction field using a safe find-and-replace anchored
  to specific Phase headers, to prevent accidental corruption of other
  configuration fields (model_version, catalog_knowledge, etc.).
"""

import sys
from google.cloud import firestore

PROJECT_ID = "tiendalasmotos"
COLLECTION = "configuracion"
DOCUMENT = "juan_pablo_personality"
FIELD = "system_instruction"

# =============================================
# PHASE 2 + PHASE 3 APPROVED REPLACEMENT BLOCK
# (Do NOT modify this without stakeholder approval)
# =============================================

NEW_PHASE_2_AND_3 = """2. **El Gatillo Legal (Fase 2 - Captura Estratégica)**:
   - 🚨 REGLA CRÍTICA DE SECUENCIA: ESTÁ ESTRICTAMENTE PROHIBIDO INICIAR LA FASE 3 O HABLAR DE CRÉDITO SIN HABER OBTENIDO ANTES UN 'SÍ' EXPLÍCITO A ESTA POLÍTICA DE DATOS.
   - SOLO LANZAR ESTE GATILLO CUANDO TENGAS CONFIRMADA LA MOTO Y LA FORMA DE PAGO EN LA CONVERSACIÓN.
   - SCRIPT OBLIGATORIO (copiar textualmente) cuando se cumplan ambas condiciones:
     "¡Excelente elección! Ya que definimos la moto y tu forma de pago, ¿me autorizas el tratamiento de tus datos para que un compañero te contacte posteriormente y finalicemos el proceso? Puedes consultar nuestra política aquí: https://tiendalasmotos.com/politica-de-privacidad"
   - Si el cliente responde que "No", acepta amablemente y sigue respondiendo dudas técnicas normales.

3. **Cierre / Siguiente Paso (Fase 3 - Tras el "Sí" Legal)**:
   - **Si es CRÉDITO**: Responde primero cualquier duda que el usuario tenga de forma natural. Luego, haz una transición suave hacia las preguntas de perfilamiento, usando un tono amigable como: "Empecemos con las preguntas, van a ser pocas y sencillas: ¿en qué trabajas actualmente?"
   - **Si es CONTADO**: "¡Perfecto! ¿Te gustaría pasar hoy por la tienda para verla en persona y cerrar el negocio?\""""

# Anchor: start of Phase 2 block to search for
PHASE2_ANCHOR = "2. **El Gatillo Legal (Fase 2 - Captura Estratégica)**:"
# Anchor: separator that comes after Phase 3, used to detect end of the block
PHASE3_END_ANCHOR = "\n═══"


def patch_instruction(current: str) -> str:
    """
    Find Phase 2 header in the current prompt and replace the entire
    Phase 2 + Phase 3 block with the approved corrected copy.

    Raises ValueError loudly on any anchor mismatch to prevent silent corruption.
    """
    if PHASE2_ANCHOR not in current:
        raise ValueError(
            f"❌ PHASE 2 ANCHOR NOT FOUND.\n"
            f"The document may already be patched or uses a different format.\n"
            f"Searched for: '{PHASE2_ANCHOR}'"
        )

    start_idx = current.index(PHASE2_ANCHOR)
    end_idx = current.find(PHASE3_END_ANCHOR, start_idx)

    if end_idx == -1:
        raise ValueError(
            "❌ PHASE 3 END ANCHOR '═══' NOT FOUND after Phase 2 start.\n"
            "Cannot safely determine where Phase 3 ends. Aborting."
        )

    before = current[:start_idx]
    after = current[end_idx:]
    patched = before + NEW_PHASE_2_AND_3 + after
    return patched


def main():
    print("=" * 60)
    print("Firestore System Prompt Patch Script")
    print("Tienda Las Motos - WhatsApp Bot")
    print("=" * 60)
    print()

    print(f"🔌 Connecting to Firestore → {PROJECT_ID}/{COLLECTION}/{DOCUMENT}")
    db = firestore.Client(project=PROJECT_ID)

    doc_ref = db.collection(COLLECTION).document(DOCUMENT)
    doc = doc_ref.get()

    if not doc.exists:
        print(f"❌ Document not found: {COLLECTION}/{DOCUMENT}")
        sys.exit(1)

    data = doc.to_dict()
    current = data.get(FIELD, "")

    if not current:
        print(f"❌ Field '{FIELD}' is empty or missing.")
        sys.exit(1)

    print(f"✅ Loaded system_instruction ({len(current)} chars)\n")

    print("--- CURRENT PHASE 2 (excerpt) ---")
    if PHASE2_ANCHOR in current:
        idx = current.index(PHASE2_ANCHOR)
        print(current[idx:idx+500])
    print("---\n")

    # Apply patch
    patched = patch_instruction(current)
    print(f"✅ Patch applied ({len(patched)} chars)\n")

    # Safety checks before writing
    checks = [
        ("ESTÁ ESTRICTAMENTE PROHIBIDO INICIAR LA FASE 3", "Phase 2 strict guardrail"),
        ("Empecemos con las preguntas, van a ser pocas y sencillas", "Phase 3 organic Q&A transition"),
    ]
    for phrase, label in checks:
        if phrase not in patched:
            print(f"❌ SAFETY CHECK FAILED: '{label}' not found in patched text. Aborting.")
            sys.exit(1)
        print(f"✅ Safety check passed: {label}")

    print("\n--- NEW PHASE 2+3 (excerpt) ---")
    if PHASE2_ANCHOR in patched:
        idx = patched.index(PHASE2_ANCHOR)
        print(patched[idx:idx+700])
    print("---\n")

    # Write to Firestore
    doc_ref.update({FIELD: patched})
    print(f"✅ Firestore UPDATED: {COLLECTION}/{DOCUMENT}.{FIELD}")
    print("🚀 The production bot will pick up the new instructions on its next cold start or config refresh.")


if __name__ == "__main__":
    main()
