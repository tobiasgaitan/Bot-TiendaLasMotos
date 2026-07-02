
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



    def test_phase1_excludes_credit_tool(self):
        """
        BOT-BRAIN-SCOPE-096: En PHASE_1_PROFILING (enganche) la herramienta
        'calculate_credit_score' NO debe estar disponible para evitar que el
        LLM detone el motor de crédito en consultas de catálogo simples.
        """
        prospect_data = {
            "exists": True,
            "habeas_data_accepted": False,
            "moto_interest": "Raider 125"
        }
        tools = self.cerebro._create_tools(prospect_data)
        
        function_names = []
        for tool in tools:
            for fd in tool.function_declarations:
                function_names.append(fd.name)
        
        self.assertNotIn(
            "calculate_credit_score", function_names,
            "PHASE_1_PROFILING NO debe exponer calculate_credit_score (BOT-BRAIN-SCOPE-096)."
        )
        self.assertIn("search_catalog", function_names, "search_catalog DEBE estar siempre disponible.")

    def test_phase2_includes_credit_tool(self):
        """
        GIVEN: Un prospecto en Fase 2 (Habeas Data Request) con intención financiera.
        THEN: La herramienta 'calculate_credit_score' DEBE estar disponible.
        """
        prospect_data = {
            "nombre": "Juan",
            "ciudad": "Bogota",
            "moto_confirmada": True,
            "moto_interest": "Raider 125",
            "forma_pago": "credito",
            "habeas_data_accepted": False
        }
        tools = self.cerebro._create_tools(prospect_data)
        
        function_names = [fd.name for tool in tools for fd in tool.function_declarations]
        self.assertIn("calculate_credit_score", function_names,
                       "PHASE_2_HABEAS_DATA DEBE incluir calculate_credit_score.")

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
