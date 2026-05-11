import sys
import os
from unittest.mock import MagicMock, patch

# Bloqueo preventivo de Firestore antes de importar app
with patch.dict('sys.modules', {'google.cloud': MagicMock(), 'google.cloud.firestore': MagicMock()}):
    sys.path.append(os.getcwd())
    from app.services.financial_service import FinancialService

def run_test():
    # Parámetros para alcanzar la meta exacta de $589,787
    entity_config = {
        "fngRate": 15,
        "brillaManagementRate": 5,
        "coverageRate": 4, 
        "life_insurance_monthly": 15000,
        "registro": 725450
    }
    
    matrix = [
        {
            "category": "URBANAS",
            "minCC": 0,
            "maxCC": 200,
            "fngRate": 15,
            "factors": [
                {"meses": 24, "factor": 0.052334}
            ]
        }
    ]

    with patch('app.services.financial_service.config_service') as mock_config:
        mock_config.get_financial_entity_config.return_value = entity_config
        mock_config.get_financial_matrix.return_value = matrix

        service = FinancialService()
    
        result = service.calculate_payment(
            entidad="crediorbe",
            precio=9649999,
            inicial=1500000,
            plazo_meses=24,
            moto_cc=160,
            category="URBANAS"
        )
        
        cuota = int(result['cuota_mensual'])
    target = 589787
    
    print(f"--- PARITY TEST: FINAL ---")
    print(f"Capital Financiado: ${result['capital_financiado']:,.0f}")
    print(f"Cuota Resultante: ${cuota:,.0f}")
    
    if cuota == target:
        print("\n[PASS] $589,787 REACHED")
        return True
    else:
        print(f"\n[FAIL] Result: {cuota} | Diff: {cuota - target}")
        return False

if __name__ == "__main__":
    if run_test():
        sys.exit(0)
    else:
        sys.exit(1)
