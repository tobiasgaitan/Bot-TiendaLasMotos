
import unittest
import sys
import os

# Add app to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.ai_brain import CerebroIA

class MockConfigLoader:
    def get_config(self, key, default=None):
        return default

class TestCompetitorProtocol(unittest.TestCase):
    def setUp(self):
        self.cerebro = CerebroIA()
        # Mocking config_loader to avoid Firestore calls
        self.cerebro.config_loader = MockConfigLoader()

    def test_determine_phase_blocks_competitor(self):
        """Verifica que el funnel NO avance a Fase 2 si hay una marca de competencia."""
        # Escenario: Tenemos nombre y ciudad, pero la moto es competencia (Boxer)
        prospect_data = {
            "name": "Pedro Picapiedra",
            "ciudad": "Bogotá",
            "moto_interes": "Boxer CT 100",
            "moto_confirmada": True,
            "payment_method": "credito",
            "interest_confirmed_in_alternative": False
        }
        
        phase = self.cerebro._determine_funnel_phase(prospect_data)
        self.assertEqual(phase, "PHASE_1_PROFILING", "Debería bloquear el avance a Fase 2 por competencia.")

    def test_determine_phase_allows_friendly_brand(self):
        """Verifica que el funnel AVANCE a Fase 2 si la moto es de la casa (TVS)."""
        prospect_data = {
            "name": "Pedro Picapiedra",
            "ciudad": "Bogotá",
            "moto_interes": "TVS Apache 160",
            "moto_confirmada": True,
            "payment_method": "credito",
            "interest_confirmed_in_alternative": False
        }
        
        phase = self.cerebro._determine_funnel_phase(prospect_data)
        self.assertEqual(phase, "PHASE_2_HABEAS_DATA", "Debería permitir el avance para marcas propias.")

    def test_determine_phase_allows_competitor_if_alternative_confirmed(self):
        """Verifica que el funnel AVANCE si el usuario confirmó interés en la alternativa."""
        prospect_data = {
            "name": "Pedro Picapiedra",
            "ciudad": "Bogotá",
            "moto_interes": "NKD 125", # Competencia
            "moto_confirmada": True,
            "payment_method": "credito",
            "interest_confirmed_in_alternative": True # Confirmado interés en alternativa
        }
        
        phase = self.cerebro._determine_funnel_phase(prospect_data)
        self.assertEqual(phase, "PHASE_2_HABEAS_DATA", "Debería permitir el avance si ya aceptó la alternativa.")

if __name__ == '__main__':
    unittest.main()
