
import unittest
import sys
import os

# Add app to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.ai_brain import CerebroIA
from app.utils.json_processor import clean_json_voorhees

class TestHabeasDataRegression(unittest.TestCase):
    def setUp(self):
        self.cerebro = CerebroIA()

    def test_strict_negative_bias_extraction(self):
        """
        GIVEN: El usuario dice 'ok, me interesa, que necesito para que me aprueben un credito?'.
        THEN: El extractor DEBE devolver 'habeas_data_accepted': False.
        """
        # Simulamos lo que Gemini extraería con el nuevo prompt restrictivo
        # Aquí probamos el adaptador JSON Voorhees que aplica el post-procesamiento
        raw_json = '{"summary": "Usuario interesado en crédito", "extracted": {"habeas_data_accepted": "me interesa", "payment_method": "credito"}}'
        parsed, is_valid = clean_json_voorhees(raw_json)
        
        self.assertTrue(is_valid)
        # El adaptador debe mapear "me interesa" a False porque no es una afirmación directa de "Acepto"
        self.assertFalse(parsed["extracted"]["habeas_data_accepted"], "No debe aceptar Habeas Data por interés en crédito.")

    def test_phase_block_without_sent_flag(self):
        """
        GIVEN: El prospecto tiene habeas_data_accepted en True (por error previo o ruido).
        BUT: habeas_data_sent es False.
        THEN: El orquestador DEBE inyectar PHASE_2_HABEAS_DATA (no PHASE_3).
        """
        prospect_data = {
            "name": "Test User",
            "ciudad": "Medellin",
            "moto_interest": "TVS Raider",
            "moto_confirmada": True,
            "payment_method": "credito",
            "habeas_data_accepted": True, 
            "habeas_data_sent": False     
        }
        
        # Test con history vacío
        phase = self.cerebro._determine_funnel_phase(prospect_data, history=[])
        self.assertEqual(phase, "PHASE_2_HABEAS_DATA", "Debe bloquear PHASE_3 si el script no fue enviado.")

    def test_phase_block_without_physical_link(self):
        """
        GIVEN: habeas_data_accepted=True y habeas_data_sent=True en DB.
        BUT: El link físico de privacidad no está en el historial del chat.
        THEN: El orquestador DEBE bloquear el avance a PHASE_3.
        """
        prospect_data = {
            "name": "Test User",
            "ciudad": "Medellin",
            "moto_interest": "TVS Raider",
            "moto_confirmada": True,
            "payment_method": "credito",
            "habeas_data_accepted": True,
            "habeas_data_sent": True
        }
        # History sin el link
        history = [
            type('obj', (object,), {'parts': [type('obj', (object,), {'text': 'Hola, acepto el tratamiento.'})]})
        ]
        
        phase = self.cerebro._determine_funnel_phase(prospect_data, history=history)
        self.assertEqual(phase, "PHASE_2_HABEAS_DATA", "Debe bloquear si no hay evidencia física del link de privacidad.")

    def test_phase_allowed_with_sent_and_accepted(self):
        """
        Verifica que el avance a PHASE_3 sea permitido si AMBOS flags son True Y el link está en el historial.
        """
        prospect_data = {
            "name": "Test User",
            "ciudad": "Medellin",
            "moto_interest": "TVS Raider",
            "moto_confirmada": True,
            "payment_method": "credito",
            "habeas_data_accepted": True,
            "habeas_data_sent": True
        }
        # History con el link
        history = [
            type('obj', (object,), {'parts': [type('obj', (object,), {'text': 'Acepta aqui: tiendalasmotos.com/politica-de-privacidad'})]}),
            type('obj', (object,), {'parts': [type('obj', (object,), {'text': 'Sí, acepto.'})]})
        ]
        
        phase = self.cerebro._determine_funnel_phase(prospect_data, history=history)
        self.assertEqual(phase, "PHASE_3_CREDIT_PROFILING", "Debe permitir PHASE_3 si hay evidencia del link y aceptación.")

if __name__ == '__main__':
    unittest.main()
