
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



    def test_phase1_includes_credit_tool(self):
        """
        BOT-ARCH-STATE-101: En PHASE_1_PROFILING (enganche) la herramienta
        'calculate_credit_score' SÍ debe estar disponible para evitar bucles de pánico cognitivo del LLM.
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
        
        self.assertIn(
            "calculate_credit_score", function_names,
            "PHASE_1_PROFILING debe exponer calculate_credit_score."
        )
        self.assertIn("search_catalog", function_names, "search_catalog DEBE estar siempre disponible.")

    def test_phase1_rejects_credit_tool_execution(self):
        """
        BOT-ARCH-STATE-101: Si calculate_credit_score es invocada prematuramente en PHASE_1_PROFILING,
        la función DEBE retornar un JSON con un mensaje de error explícito para el LLM indicando
        que la acción está denegada y obligándolo a usar search_catalog y mostrar precio/imagen.
        """
        class MockFunctionCall:
            def __init__(self, name, args):
                self.name = name
                self.args = args

        class MockPart:
            def __init__(self, function_call=None, text=None):
                self.function_call = function_call
                self.text = text

        class MockContent:
            def __init__(self, parts):
                self.parts = parts

        class MockCandidate:
            def __init__(self, content):
                self.content = content

        class MockResponse:
            def __init__(self, candidates):
                self.candidates = candidates

        fc = MockFunctionCall(name="calculate_credit_score", args={})
        candidate = MockCandidate(content=MockContent(parts=[MockPart(function_call=fc)]))
        gemini_response = MockResponse(candidates=[candidate])

        candidate_text = MockCandidate(content=MockContent(parts=[MockPart(text="Obligatorio buscar moto")]))
        gemini_response_text = MockResponse(candidates=[candidate_text])

        captured_response_parts = None
        call_count = 0
        async def mock_call(*args, **kwargs):
            nonlocal call_count, captured_response_parts
            call_count += 1
            if call_count == 1:
                return gemini_response
            if len(args) > 1:
                captured_response_parts = args[1]
            return gemini_response_text

        prospect_data = {
            "exists": True,
            "habeas_data_accepted": False,
            "moto_interest": "Raider 125"
        }

        with patch.object(self.cerebro, '_call_gemini_with_retry_async', new=mock_call), \
             patch('app.services.ai_brain.SDK_AVAILABLE', True):
            
            import asyncio
            asyncio.run(self.cerebro.pensar_respuesta("Quiero saber mi credito", prospect_data=prospect_data))
            
            # The tool should have been rejected at runtime and response_parts should contain the error JSON
            self.assertIsNotNone(captured_response_parts, "Gemini should have received response parts back.")
            
            credit_part = None
            for part in captured_response_parts:
                if getattr(part, 'function_response', None) and part.function_response.name == "calculate_credit_score":
                    credit_part = part.function_response
                    break
            
            self.assertIsNotNone(credit_part, "Should find a function response for calculate_credit_score.")
            self.assertIn("error", credit_part.response, "The tool response should contain the 'error' key.")
            self.assertIn("Acción denegada", credit_part.response["error"], "The error message should indicate that the action is denied.")
            self.assertIn("search_catalog", credit_part.response["error"], "The error message should instruct to use search_catalog.")

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
