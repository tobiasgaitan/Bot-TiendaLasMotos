#!/usr/bin/env python3
"""
Admin Maintenance Script: Patch Down Payment Ratio in Firestore (v1.0.0)
========================================================================
Updates both the financial configuration and the AI system instructions.
"""

from google.cloud import firestore
import re

PROJECT_ID = "tiendalasmotos"

def patch_financial_params(db):
    print("🔌 Patching 'config/financial_parameters'...")
    doc_ref = db.collection("config").document("financial_parameters")
    doc = doc_ref.get()
    if not doc.exists:
        print("⚠️  'config/financial_parameters' not found.")
        return

    data = doc.to_dict()
    old_ratio = data.get("default_down_payment_ratio")
    print(f"   Current ratio: {old_ratio}")
    
    doc_ref.update({"default_down_payment_ratio": 0.10})
    print("   ✅ Updated to 0.10")

def patch_juan_pablo_personality(db):
    print("🔌 Patching 'configuracion/juan_pablo_personality'...")
    doc_ref = db.collection("configuracion").document("juan_pablo_personality")
    doc = doc_ref.get()
    if not doc.exists:
        print("⚠️  'configuracion/juan_pablo_personality' not found.")
        return

    data = doc.to_dict()
    instruction = data.get("system_instruction", "")
    
    if not instruction:
        print("⚠️  No system_instruction found.")
        return

    # Look for the credit_matrix block and update 15% to 10%
    # Specifically: "- Reportados: Pueden acceder con 15% de cuota inicial."
    new_instruction = instruction.replace("15% de cuota inicial", "10% de cuota inicial")
    
    if new_instruction != instruction:
        doc_ref.update({"system_instruction": new_instruction})
        print("   ✅ Updated '15% de cuota inicial' to '10% de cuota inicial'")
    else:
        print("   ℹ️ No changes needed in system_instruction (15% not found in that exact phrase).")

def patch_global_params(db):
    print("🔌 Patching 'financial_config/general/global_params/global_params'...")
    doc_ref = db.collection("financial_config").document("general").collection("global_params").document("global_params")
    doc = doc_ref.get()
    if not doc.exists:
        print("⚠️  'financial_config' not found.")
        return

    data = doc.to_dict()
    old_ratio = data.get("default_down_payment_ratio")
    print(f"   Current ratio: {old_ratio}")
    
    doc_ref.update({"default_down_payment_ratio": 0.10})
    print("   ✅ Updated to 0.10")

def main():
    db = firestore.Client(project=PROJECT_ID)
    patch_global_params(db)
    patch_financial_params(db)
    patch_juan_pablo_personality(db)
    print("\n🚀 All Firestore patches completed.")

if __name__ == "__main__":
    main()
