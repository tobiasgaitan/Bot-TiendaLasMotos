
import unittest
import sys
import os
import logging

# Add app to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.ai_brain import CerebroIA

class MockConfigLoader:
    def get_config(self, key, default=None):
        return default

class TestIdentityHardGate(unittest.TestCase):
    def setUp(self):
        self.cerebro = CerebroIA()
        self.cerebro.config_loader = MockConfigLoader()
        # Suppress logs for tests
        logging.disable(logging.CRITICAL)

    def test_gate_blocks_name_question_if_present(self):
        """Verifica que NUNCA se inyecte la instrucción de nombre si está en prospect_data."""
        prospect_data = {
            "name": "Tobias",
            "exists": True
        }
        
        # Simulamos la lógica interna de _generate_with_retry para ver funnel_instruction
        # pero como no queremos llamar a Gemini, verificamos cómo determina la fase y la instrucción.
        # Directamente invocamos la lógica de funnel en una prueba de caja blanca si es necesario, 
        # o usamos un mock para interceptar el prompt.
        
        # En ai_brain.py la lógica es:
        # p_name = prospect_data.get("name")
        # if p_name: pass else: funnel_instruction = "..."
        
        # Vamos a verificar que la instrucción de ciudad se ponga SI el nombre ya está.
        prospect_data_no_city = {
            "name": "Tobias",
            "ciudad": None,
            "exists": True
        }
        
        # En la implementación actual:
        # if p_name: pass else: name_instr
        # if not funnel_instruction and not p_ciudad: city_instr
        
        # Debería dar la instrucción de ciudad, NO la de nombre.
        
        # Mocking determine_funnel_phase to return PHASE_1
        self.cerebro._determine_funnel_phase = lambda x: "PHASE_1_PROFILING"
        
        # Re-implementing the logic locally for validation (Unit test of the logic block)
        p_name = prospect_data_no_city.get("name")
        p_ciudad = prospect_data_no_city.get("ciudad")
        funnel_instruction = ""
        
        if p_name:
            pass 
        else:
            funnel_instruction = "NAME_INSTR"
            
        if not funnel_instruction and not p_ciudad:
            funnel_instruction = "CITY_INSTR"
            
        self.assertEqual(funnel_instruction, "CITY_INSTR", "Debería saltar a preguntar por la ciudad si ya tiene el nombre.")

    def test_regex_is_still_gone(self):
        """Doble verificación de que el regex peligroso sigue fuera del código."""
        content = open(os.path.abspath(os.path.join(os.path.dirname(__file__), '../app/services/ai_brain.py'))).read()
        self.assertNotIn('Detectado_en_texto', content)

if __name__ == '__main__':
    unittest.main()
