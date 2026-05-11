
import sys
import os
from unittest.mock import MagicMock

# Setup path
sys.path.append(os.getcwd())

# Mock ConfigService BEFORE importing FinancialService
import app.services.config_service
mock_config = MagicMock()
app.services.config_service.config_service = mock_config

# Mock data for Crediorbe
mock_config.get_financial_entity_config.return_value = {
    "fngRate": 20.66,
    "registro": 0,
    "brillaManagementRate": 0,
    "coverageRate": 4,
    "life_insurance_monthly": 0
}
mock_config.get_financial_matrix.return_value = [
    {
        "minCC": 155,
        "maxCC": 200,
        "factors": {"24": 0.0523336},
        "registrationCreditGeneral": 1100000,
        "fngRate": 20.66
    }
]

from app.services.financial_service import FinancialService

def test_apache_parity():
    service = FinancialService()
    # Injecting mocks
    service._config_service = mock_config
    
    print("🧪 Verificando Paridad Matemática para Apache 160 (v1.5.0)")
    
    # Case: Apache 160
    p1, i1, t1, cc1 = 11100000, 1500000, 24, 160.0
    res = service.calculate_payment(precio=p1, inicial=i1, plazo_meses=t1, moto_cc=cc1)
    
    target = 589787
    val = res['cuota_mensual']
    diff = val - target
    
    print(f"Obtenido: ${val:,.0f}")
    print(f"Target:   ${target:,.0f}")
    print(f"Diff:     ${diff:,.2f}")
    
    if abs(diff) < 1:
        print("✅ ¡PARIDAD LOGRADA!")
    else:
        print("❌ FALLO DE PARIDAD")
        sys.exit(1)

if __name__ == "__main__":
    test_apache_parity()
