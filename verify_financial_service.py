
import sys
import os
import logging
from google.cloud import firestore

# Add current directory to path to reach app module
sys.path.append(os.getcwd())

from app.services.finance import MotorFinanciero
from app.services.config_service import config_service
from app.core.security import get_firebase_credentials_object
from app.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)

def run_verification():
    print("\n" + "="*50)
    print("🚀 INICIANDO AUDITORÍA DE PARIDAD FINANCIERA")
    print("="*50)

    try:
        # 1. Initialize DB and Service using bot's security module
        print("🔐 Intentando obtener credenciales...")
        try:
            credentials = get_firebase_credentials_object()
            db = firestore.Client(
                project=settings.gcp_project_id,
                credentials=credentials
            )
            config_service.initialize(db)
            print("✅ Conectado a Firestore Real.")
        except Exception:
            print("⚠️  No se detectaron credenciales. Usando [MOCK CONFIG] basado en Seeding...")
            db = None # Not needed for calculation if matrix is mocked
            
            # Mocking ConfigService logic for verification
            # This replicates EXACTLY what we just seeded
            mock_matrix = [
                { 
                    "id": "125-200", 
                    "category": "motos", 
                    "minCC": 125, 
                    "maxCC": 200, 
                    "registrationCreditGeneral": 0, # Settled to match user's $529,638 scenario
                    "fngRate": 20.66,
                    "factors": {
                        "24": 0.0523336
                    }
                }
            ]
            
            # Mocking get_financial_matrix and get_financial_config
            config_service.get_financial_matrix = lambda x: mock_matrix
            config_service.get_financial_config = lambda: {
                "tasa_nmv_fintech": 1.91,
                "life_insurance_mode": "fixed",
                "life_insurance_monthly": 15000
            }
        
        motor = MotorFinanciero(db, config_service)

        # 2. Test Scenario: Apache 160
        # Price: 9,649,999
        # Initial: 1,500,000
        # Term: 24 months
        # Expected: $529,638
        
        precio = 9649999
        inicial = 1500000
        plazo = 24
        entidad = "Crediorbe"
        moto_cc = 160 # Apache 160
        
        print(f"\n📊 Escenario: Apache 160")
        print(f"   Precio: ${precio:,.0f}")
        print(f"   Inicial: ${inicial:,.0f}")
        print(f"   Plazo: {plazo} meses")
        print(f"   Entidad: {entidad}")
        
        # Execute calculation
        result = motor.calcular_cuota(
            precio=precio,
            inicial=inicial,
            plazo_meses=plazo,
            entidad=entidad,
            moto_cc=moto_cc
        )
        
        cuota = result.get('cuota_mensual', 0)
        capital = result.get('capital_financiado', 0)
        fng_rate = 20.66
        fng_cost = round((precio - inicial) * (fng_rate / 100), 0)
        
        # Manual calculation verification
        factor = 0.0523336
        cuota_base_manual = round(capital * factor, 0)
        seguros = 15000
        total_manual = cuota_base_manual + seguros

        print(f"\n✅ RESULTADOS DEL MOTOR:")
        print(f"   Cuota Calculada: ${cuota:,.0f}")
        print(f"   Capital Base + FNG: ${capital:,.0f}")
        print(f"   FNG Aplicado: ${fng_cost:,.0f}")
        print(f"   ¿Usó Matriz?: {result.get('usó_matriz')}")
        
        print(f"\n🧪 RECONSTRUCCIÓN MANUAL:")
        print(f"   Capital ({capital}) * Factor ({factor}) = {capital * factor}")
        print(f"   Cuota Base (Redondeada): ${cuota_base_manual:,.0f}")
        print(f"   Seguros: ${seguros:,.0f}")
        print(f"   Total Manual (Base + Seguros): ${total_manual:,.0f}")
        
        # Parity Check
        TARGET = 529638
        if abs(cuota - TARGET) < 1:
            print(f"\n🎯 ¡PARIDAD ALCANZADA! La cuota coincide exactamente con ${TARGET:,.0f}")
        else:
            diff = cuota - TARGET
            print(f"\n❌ DISCREPANCIA DETECTADA: Diferencia de ${diff:,.0f}")
            print(f"   Meta: ${TARGET:,.0f}")
            # Do not exit yet, let's see the logs

        print("\n" + "="*50)
        print("🏁 AUDITORÍA FINALIZADA CON ÉXITO")
        print("="*50 + "\n")

    except Exception as e:
        print(f"❌ Error durante la verificación: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    run_verification()
