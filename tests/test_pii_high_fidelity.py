
import unittest
import sys
import os

# Add app to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.utils.json_processor import clean_json_voorhees

class TestPIIHighFidelity(unittest.TestCase):
    def test_high_fidelity_schema_cleaning(self):
        """Verifica que el nuevo esquema PII se limpie correctamente."""
        raw_json = """
        {
          "summary": "El cliente está interesado en una moto para trabajo.",
          "extracted": {
            "name": "Juan Pérez",
            "city": "Bogotá",
            "moto_interes": "Pulsar 200",
            "moto_ofrecida": "TVS Apache 160",
            "moto_aceptada": "TVS Apache 160",
            "habeas_data_accepted": true,
            "payment_method": "Crédito",
            "ocupacion": "Empleado",
            "datacredito": "Al día",
            "vivienda": "Propia",
            "servicios_publicos": "Gas Natural"
          }
        }
        """
        result, is_valid = clean_json_voorhees(raw_json)
        self.assertTrue(is_valid)
        self.assertEqual(result["extracted"]["moto_interes"], "Pulsar 200")
        self.assertEqual(result["extracted"]["moto_aceptada"], "TVS Apache 160")
        self.assertTrue(result["extracted"]["habeas_data_accepted"])
        self.assertEqual(result["extracted"]["servicios_publicos"], "Gas Natural")
        print("✅ PII High-Fidelity Schema Verification Passed!")

if __name__ == '__main__':
    unittest.main()
