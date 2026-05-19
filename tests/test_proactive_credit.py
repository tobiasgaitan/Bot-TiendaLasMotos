
import unittest
import sys
import os
from unittest.mock import MagicMock, patch

# Add app to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.ai_brain import CerebroIA
from app.services.financial_service import FinancialService

class TestProactiveCredit(unittest.TestCase):
    def setUp(self):
        self.cerebro = CerebroIA()
        # Mocking the client to avoid real API calls
        self.cerebro.client = MagicMock()



    def test_proactive_tools_without_habeas(self):
        """
        GIVEN: Un prospecto nuevo (sin Habeas Data aceptado).
        THEN: La herramienta 'calculate_credit_score' DEBE estar disponible (Proactivo).
        """
        prospect_data = {
            "exists": True,
            "habeas_data_accepted": False,
            "moto_interest": "Raider 125"
        }
        tools = self.cerebro._create_tools(prospect_data)
        
        # Extraer nombres de funciones de las declaraciones
        function_names = []
        for tool in tools:
            for fd in tool.function_declarations:
                function_names.append(fd.name)
        
        self.assertIn("calculate_credit_score", function_names, "La herramienta de crédito debe estar disponible proactivamente.")

    def test_proactive_tools_in_phase_2(self):
        """
        GIVEN: Un prospecto en Fase 2 (Habeas Data Request).
        THEN: La herramienta 'calculate_credit_score' DEBE estar disponible.
        """
        prospect_data = {
            "nombre": "Juan",
            "ciudad": "Bogota",
            "moto_confirmada": True,
            "forma_pago": "credito",
            "habeas_data_accepted": False
        }
        # Forzar que _determine_funnel_phase devuelva PHASE_2
        # (Ya debería devolverlo con estos datos)
        tools = self.cerebro._create_tools(prospect_data)
        
        function_names = [fd.name for tool in tools for fd in tool.function_declarations]
        self.assertIn("calculate_credit_score", function_names)

    def test_deterministic_insurance_fallback(self):
        """
        GIVEN: El FinancialService se inicializa.
        THEN: El seguro de vida debe ser $15,000 por defecto si no hay config.
        """
        # Mock firestore client y config service
        with patch('app.services.financial_service.config_service') as mock_config:
            mock_config.get_financial_entity_config.return_value = {} # Empty config forces fallbacks
            mock_config.get_financial_matrix.return_value = []
            
            service = FinancialService()
            res = service.calculate_payment(5000000, 1000000, 24, entidad="Banco")
            
            self.assertEqual(res["seguro_vida"], 15000.0, "El seguro de vida debe aplicar el fallback de $15,000.")

if __name__ == '__main__':
    unittest.main()
