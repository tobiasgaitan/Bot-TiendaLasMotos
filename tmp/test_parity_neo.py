from app.services.financial_service import FinancialService
from app.services.config_service import config_service
import unittest.mock as mock

def test_neo_nx():
    config_service._financial_config = {
        "tasa_nmv_banco": 1.87,
        "tasa_nmv_fintech": 2.22,
        "fng_rate": 20.66,
        "life_insurance_monthly": 15000,
        "brillaManagementRate": 5,
        "coverageRate": 4
    }
    config_service._partners_config = {}
    
    m = FinancialService()

    try:
        res = m.calcular_cuota(
            precio=6699999,
            inicial=1004999,
            plazo_meses=24,
            entidad="crediorbe",
            moto_cc=109.7
        )
        print("--- RESULTADOS TVS NEO NX 110 ---")
        print(f"Target web: $416.647")
        print(f"Cuota Bot: ${res.get('cuota_mensual')}")
    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"Error: {e}")

if __name__ == "__main__":
    test_neo_nx()
