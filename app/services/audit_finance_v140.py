import asyncio
import os
import sys
import logging
from google.cloud import firestore

# Setup paths
sys.path.append(os.getcwd())

from app.services.finance import MotorFinanciero
from app.services.config_service import ConfigService

# Configure logging
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

async def test_calculation():
    print("🚀 Iniciando Auditoría de Paridad (v1.4.0) con Inyección Firestore...")
    
    try:
        # 1. Initialize Firestore client
        db = firestore.Client()
        
        # 2. Initialize ConfigService with db
        config_service = ConfigService()
        # Initialize with db and load configs
        config_service.initialize(db)
        
        # 3. Initialize MotorFinanciero
        motor = MotorFinanciero(config_service=config_service)
        
        # Case: Apache 160
        # Price: 11,100,000
        # Initial: 1,500,000
        # Term: 24 months
        # Entity: Crediorbe
        # Goal: $589,787
        
        precio = 11100000
        inicial = 1500000
        plazo = 24
        entidad = "Crediorbe"
        moto_cc = 160.0 # Apache 160
        
        resultado = motor.calcular_cuota(
            precio=precio, 
            inicial=inicial, 
            plazo_meses=plazo, 
            entidad=entidad, 
            moto_cc=moto_cc
        )
        
        print("\n--- RESULTADO DE SIMULACIÓN ---")
        print(f"Entidad: {resultado['entidad']}")
        print(f"Monto Neto a Financiar: \${precio - inicial:,.0f}")
        print(f"Capital Total Financiado: \${resultado['capital_financiado']:,.0f}")
        print(f"Cuota Mensual Final (Visible): \${resultado['cuota_mensual']:,.0f}")
        print(f"Seguro de Vida: \${resultado['seguro_vida']:,.0f}")
        print(f"Cuota Aval (Cobertura): \${resultado.get('cuota_aval', 0):,.0f}")
        print(f"Usó Matriz: {resultado['usó_matriz']}")
        
        target = 589787
        final_value = resultado['cuota_mensual']
        discrepancia = final_value - target
        
        print(f"\nValor Obtenido: \${final_value:,.0f}")
        print(f"Valor Web Target: \${target:,.0f}")
        print(f"Discrepancia: \${discrepancia:,.2f}")
        
        if abs(discrepancia) < 1:
            print("\n✅ ¡PARIDAD LOGRADA DEL 100%!")
        else:
            print(f"\n❌ Discrepancia detectada (\${discrepancia:,.2f}).")
            
    except Exception as e:
        print(f"❌ Error durante el test: {e}")

if __name__ == '__main__':
    asyncio.run(test_calculation())
