import os
import sys
from google.cloud import firestore

# Configuration for Seeding (Marzo 2026)
PROJECT_ID = "tiendalasmotos"
ENTITIES = ["brilla", "banco_bogota"]
MASTER_FACTOR_24 = 0.0523336
UNIFIED_RATE = 1.91
INSURANCE_FIXED = 15000

# Base Brackets from fix_admin.ts (Values for Santa Marta as requested)
SANTA_MARTA_REGISTRATION = {
    "0-99": 760000,
    "100-124": 840000,
    "125-200": 920000,
    "gt-200": 1120000,
    "electrical": 540000,
    "motocarro": 950000
}

def seed_financials():
    db = firestore.Client(project=PROJECT_ID)
    print(f"🚀 Starting Massive Seeding for project: {PROJECT_ID}")

    for entity in ENTITIES:
        print(f"📋 Processing entity: {entity}...")
        
        # Entity-level config
        # [BOT-BUILD-FIX-E-CREDIORBE-ERADICATION-001] Crediorbe erradicada del dominio:
        # fng_rate=0.0 y finance_docs=True aplican uniformemente a todas las entidades.
        fng_rate = 0.0
        finance_docs = True
        
        # Define Rows
        rows = []
        
        # 1. Bracket 0-99
        rows.append({
            "id": "0-99",
            "minCC": 0,
            "maxCC": 99,
            "registrationCreditGeneral": SANTA_MARTA_REGISTRATION["0-99"],
            "factors": {
                "24": MASTER_FACTOR_24,
                "36": 0.041234,  # Fallback/Current
                "48": 0.035678   # Fallback/Current
            }
        })
        
        # 2. Bracket 100-124
        rows.append({
            "id": "100-124",
            "minCC": 100,
            "maxCC": 124,
            "registrationCreditGeneral": SANTA_MARTA_REGISTRATION["100-124"],
            "factors": {
                "24": MASTER_FACTOR_24,
                "36": 0.041234,
                "48": 0.035678
            }
        })
        
        # 3. Bracket 125-200 (The Apache 160 case)
        rows.append({
            "id": "125-200",
            "minCC": 125,
            "maxCC": 200,
            "category": "URBANA Y/O TRABAJO",
            "registrationCreditGeneral": SANTA_MARTA_REGISTRATION["125-200"],
            "factors": {
                "24": MASTER_FACTOR_24,
                "36": 0.041234,
                "48": 0.035678
            }
        })
        
        # 4. Bracket gt-200
        rows.append({
            "id": "gt-200",
            "minCC": 201,
            "maxCC": 9999,
            "registrationCreditGeneral": SANTA_MARTA_REGISTRATION["gt-200"],
            "factors": {
                "24": MASTER_FACTOR_24,
                "36": 0.041234,
                "48": 0.035678
            }
        })
        
        # 5. Electrical
        rows.append({
            "id": "electrical",
            "category": "ELECTRICA",
            "registrationCreditGeneral": SANTA_MARTA_REGISTRATION["electrical"],
            "factors": {
                "24": MASTER_FACTOR_24,
                "36": 0.041234,
                "48": 0.035678
            }
        })
        
        # 6. Motocarro
        rows.append({
            "id": "motocarro",
            "category": "MOTOCARRO Y/O MOTOCARGUERO",
            "registrationCreditGeneral": SANTA_MARTA_REGISTRATION["motocarro"],
            "factors": {
                "24": MASTER_FACTOR_24,
                "36": 0.041234,
                "48": 0.035678
            }
        })

        # Final Document Data
        data = {
            "interestRate": UNIFIED_RATE,
            "fngRate": fng_rate,
            "financeDocs": finance_docs,
            "lifeInsuranceValue": INSURANCE_FIXED,
            "lifeInsuranceType": "fixed",
            "rows": rows,
            "updatedAt": firestore.SERVER_TIMESTAMP
        }
        
        # Brilla Special Fields
        if entity == "brilla":
            data["brillaManagementRate"] = 5
            data["coverageRate"] = 4
            
        # Update Firestore
        doc_ref = db.collection("financial_config").document("general").collection("financieras").document(entity)
        doc_ref.set(data, merge=True)
        print(f"✅ Entity {entity} updated successfully.")

    print("\n✨ Massive Seeding Completed.")

if __name__ == "__main__":
    seed_financials()
