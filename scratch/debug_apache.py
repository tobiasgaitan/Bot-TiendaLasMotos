
import asyncio
import os
import sys
from google.cloud import firestore

# Setup paths
sys.path.append(os.getcwd())

from app.services.config_service import config_service
from app.services.financial_service import financial_service

async def debug_apache():
    db = firestore.Client()
    config_service.initialize(db)
    
    entidad = "Crediorbe"
    moto_cc = 160.0
    category = "motos"
    precio = 11100000
    inicial = 1500000
    plazo_meses = 24
    
    entity_config = config_service.get_financial_entity_config(entidad)
    print(f"DEBUG: entity_config keys: {list(entity_config.keys())}")
    print(f"DEBUG: entity_config['fngRate']: {entity_config.get('fngRate')}")
    print(f"DEBUG: entity_config['coverageRate']: {entity_config.get('coverageRate')}")
    
    matrix = config_service.get_financial_matrix(entidad)
    print(f"DEBUG: matrix length: {len(matrix)}")
    
    matching_rows = []
    for row in matrix:
        min_cc = float(row.get("minCC", 0))
        max_cc = float(row.get("maxCC", 9999))
        if min_cc <= moto_cc <= max_cc:
            matching_rows.append(row)
    
    print(f"DEBUG: matching_rows: {len(matching_rows)}")
    if matching_rows:
        row = matching_rows[0]
        print(f"DEBUG: row data: {row}")
        print(f"DEBUG: row fngRate: {row.get('fngRate')}")
        
    res = financial_service.calculate_payment(precio=precio, inicial=inicial, plazo_meses=plazo_meses, moto_cc=moto_cc)
    print(f"DEBUG: result: {res}")

if __name__ == '__main__':
    asyncio.run(debug_apache())
