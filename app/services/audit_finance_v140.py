import asyncio
import os
import sys
import logging
from google.cloud import firestore

# Setup paths
sys.path.append(os.getcwd())

from app.services.financial_service import financial_service
from app.services.config_service import config_service

# Configure logging
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

async def test_calculation():
    print("🚀 Iniciando Auditoría de Paridad (v1.5.0) - FinancialService Consolidated")
    
    try:
        # 1. Initialize Firestore client
        db = firestore.Client()
        
        # 2. Initialize ConfigService with db
        config_service.initialize(db)
        
        # CASE 1: Apache 160 (The Standard)
        # Goal: $589,787
        print("\n--- CASO 1: Apache 160 ---")
        p1, i1, t1, cc1 = 11100000, 1500000, 24, 160.0
        res1 = financial_service.calculate_payment(precio=p1, inicial=i1, plazo_meses=t1, moto_cc=cc1)
        
        target1 = 589787
        val1 = res1['cuota_mensual']
        diff1 = val1 - target1
        print(f"Obtenido: ${val1:,.0f} | Target: ${target1:,.0f} | Diff: ${diff1:,.2f}")
        
        # CASE 2: Neo NX (Small Displacement Parity)
        # Goal: $416,647
        print("\n--- CASO 2: Neo NX ---")
        p2, i2, t2, cc2 = 6700000, 1500000, 24, 110.0
        res2 = financial_service.calculate_payment(precio=p2, inicial=i2, plazo_meses=t2, moto_cc=cc2)
        
        target2 = 416647
        val2 = res2['cuota_mensual']
        diff2 = val2 - target2
        print(f"Obtenido: ${val2:,.0f} | Target: ${target2:,.0f} | Diff: ${diff2:,.2f}")

        if abs(diff1) < 5 and abs(diff2) < 5:
            print("\n✅ ¡PARIDAD GLOBAL LOGRADA (V1.4.0 Compliance)!")
        else:
            print("\n❌ Discrepancia crítica en paridad matemática.")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Error durante el test: {e}")
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(test_calculation())
