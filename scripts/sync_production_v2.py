#!/usr/bin/env python3
"""
⚠️  LEGACY — [BOT-PLAN-HARDENING-EGRESS-FUNNEL-001 / FIX-E]
Este script queda declarado LEGACY. El CANAL ÚNICO autorizado para sincronizar
el prompt completo es `scripts/sync_full_prompt.py` (pre-write gate + read-back
forense con triple aserción + evidencia archivada). No usar para sync del prompt.

Sync Script v2: Deploy Updated System Prompt to Firestore
=========================================================
This script imports the final, corrected system instruction from
app.core.prompts and pushes it directly to the live Firestore
document for the Juan Pablo personality.

USAGE:
1. Open Google Cloud Shell (or an environment with ADC configured).
2. Run: python3 scripts/sync_production_v2.py
"""

import os
import sys

# Ensure we can import from the app directory
sys.path.append(os.getcwd())

try:
    from google.cloud import firestore
except ImportError:
    print("❌ Error: google-cloud-firestore not installed.")
    print("Run: pip install google-cloud-firestore")
    sys.exit(1)

try:
    from app.core.prompts import JUAN_PABLO_SYSTEM_INSTRUCTION
except ImportError:
    print("❌ Error: Could not import JUAN_PABLO_SYSTEM_INSTRUCTION from app.core.prompts")
    sys.exit(1)

PROJECT_ID = "tiendalasmotos"
COLLECTION = "configuracion"
DOCUMENT = "juan_pablo_personality"
FIELD = "system_instruction"

def main():
    print("=" * 60)
    print("🚀 Firestore Sync Tool - Tienda Las Motos")
    print("=" * 60)
    
    print(f"🔌 Connecting to Firestore (Project: {PROJECT_ID})...")
    db = firestore.Client(project=PROJECT_ID)
    
    doc_ref = db.collection(COLLECTION).document(DOCUMENT)
    
    print(f"📝 Injecting new prompt ({len(JUAN_PABLO_SYSTEM_INSTRUCTION)} chars)...")
    
    try:
        # We perform a full overwrite of the field to ensure all logic (Pivot, Matrix, Locations) 
        # is exactly as reviewed in the repository.
        doc_ref.set({FIELD: JUAN_PABLO_SYSTEM_INSTRUCTION}, merge=True)
        print("✅ SUCCESS: Firestore updated.")
    except Exception as e:
        print(f"❌ FAILED to update Firestore: {e}")
        sys.exit(1)
    
    print("\n🔍 Verifying update...")
    updated_doc = doc_ref.get()
    if updated_doc.exists:
        live_val = updated_doc.to_dict().get(FIELD, "")
        if live_val == JUAN_PABLO_SYSTEM_INSTRUCTION:
            print("✨ VERIFIED: Live prompt matches local source of truth.")
        else:
            print("⚠️ WARNING: Mismatch detected. Update might need refresh.")
    
    print("\n🚀 Production bot is now synced with the latest business logic.")
    print("=" * 60)

if __name__ == "__main__":
    main()
