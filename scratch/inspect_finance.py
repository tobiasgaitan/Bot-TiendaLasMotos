
import asyncio
from google.cloud import firestore
from app.services.config_service import config_service
from app.services.financial_service import financial_service

async def inspect():
    db = firestore.Client()
    config_service.initialize(db)
    
    entidad = "Crediorbe"
    moto_cc = 160.0
    category = "motos"
    precio = 11100000
    inicial = 1500000
    plazo_meses = 24
    
    entity_config = config_service.get_financial_entity_config(entidad)
    matrix = config_service.get_financial_matrix(entidad)
    
    print(f"--- Inspection for {entidad} {moto_cc}cc ---")
    print(f"Entity Config keys: {list(entity_config.keys())}")
    print(f"FNG Rate (root): {entity_config.get('fngRate')}")
    print(f"Registro (root): {entity_config.get('registro')}")
    
    row = None
    for r in matrix:
        min_cc = float(r.get("minCC", 0))
        max_cc = float(r.get("maxCC", 9999))
        if min_cc <= moto_cc <= max_cc:
            row = r
            break
            
    if row:
        print(f"Matching Row: {row}")
        print(f"FNG Rate (row): {row.get('fngRate')}")
        print(f"Registration (row): {row.get('registrationCreditGeneral')}")
    else:
        print("No matching row found!")

    res = financial_service.calculate_payment(precio, inicial, plazo_meses, moto_cc=moto_cc)
    print(f"\nResult: {res}")

if __name__ == '__main__':
    asyncio.run(inspect())
