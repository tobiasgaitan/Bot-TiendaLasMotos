
import unittest
import sys
import os
from unittest.mock import MagicMock

# Add app to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.ai_brain import CerebroIA
from app.services.finance import MotorFinanciero

class TestProactiveCredit(unittest.TestCase):
    def setUp(self):
        self.cerebro = CerebroIA()
        # Mocking the client to avoid real API calls
        self.cerebro.client = MagicMock()

    def test_retro_compatibility_name_or(self):
        """
        GIVEN: Un prospecto con 'name' en lugar de 'nombre' (legacy).
        THEN: _determine_funnel_phase debe reconocer que tiene nombre (has_name=True).
        """
        prospect_legacy = {
            "name": "Juan Pablo",
            "ciudad": "Medellin",
            "moto_interest": "Raider",
            "moto_confirmada": True,
            "payment_method": "credito"
        }
        # Inyectamos el mock de history con el link para que pueda avanzar si todos los campos están
        # Pero aquí solo probamos si detecta el nombre para la fase 2.
        phase = self.cerebro._determine_funnel_phase(prospect_legacy, history=[])
        # Con nombre, ciudad, moto_confirmada y credito -> PHASE_2_HABEAS_DATA
        self.assertEqual(phase, "PHASE_2_HABEAS_DATA")

    def test_retro_compatibility_payment_or(self):
        """
        GIVEN: Un prospecto con 'payment_method' en lugar de 'forma_pago'.
        THEN: _determine_funnel_phase debe reconocer el interés en crédito.
        """
        prospect_legacy = {
            "nombre": "Juan Pablo",
            "ciudad": "Medellin",
            "moto_confirmada": True,
            "payment_method": "credito"
        }
        phase = self.cerebro._determine_funnel_phase(prospect_legacy, history=[])
        self.assertEqual(phase, "PHASE_2_HABEAS_DATA")

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

    def test_deterministic_insurance_fallback(self):
        """
        GIVEN: El MotorFinanciero se inicializa.
        THEN: El seguro de vida debe ser $15,000 por defecto.
        """
        # Mock firestore client
        mock_db = MagicMock()
        # Mock config service
        mock_config = MagicMock()
        mock_config.get_financial_config.return_value = None # Force fallback
        
        motor = MotorFinanciero(mock_db, config_service=mock_config)
        res = motor.calcular_cuota(5000000, 1000000, 24, 2.22)
        
        self.assertEqual(res["seguro_vida"], 15000, "El seguro de vida debe aplicar el fallback de $15,000.")

if __name__ == '__main__':
    unittest.main()
