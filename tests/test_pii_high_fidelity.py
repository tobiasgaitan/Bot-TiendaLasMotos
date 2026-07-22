
import unittest
import sys
import os
import pytest

# Add app to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.utils.json_processor import clean_json_voorhees
from tests.validators import (
    assert_no_pii_leak,
    assert_no_control_chars,
    assert_pii_whitelist,
    assert_truncated_50,
)

class TestPIIHighFidelity(unittest.TestCase):
    def test_high_fidelity_schema_cleaning(self):
        """Verifica que el nuevo esquema PII se limpie correctamente."""
        raw_json = """
        {
          "summary": "El cliente está interesado en una moto para trabajo.",
          "extracted": {
            "name": "Juan Pérez",
            "city": "Bogotá",
            "moto_interest": "Pulsar 200",
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
        self.assertEqual(result["extracted"]["moto_interest"], "Pulsar 200")
        self.assertTrue(result["extracted"]["habeas_data_accepted"])
        self.assertEqual(result["extracted"]["servicios_publicos"], "Gas Natural")
        print("✅ PII High-Fidelity Schema Verification Passed!")

    def test_pii_sanitize_fields_contract_with_regex_validators(self):
        """[Incidente H-A · HA-4] Contrato de _sanitize_fields con validadores regex:
        eliminación de control-chars, whitelist estricta y truncado a 50 chars
        sobre los campos PII críticos (name/city/moto_interest)."""
        raw_control_char = "Jua\x00n \x0bPérez"
        raw_long_name = "Alejandro Maximiliano Constantino de la Santísima Trinidad"
        raw_email_name = "juan.perez@gmail.com"
        raw_emoji_city = "Bogotá 😀 @#$ <script>"
        raw_payload = f"""
        {{
          "summary": "Cliente con PII adversaria embebida.",
          "extracted": {{
            "name": "{raw_long_name}",
            "city": "{raw_emoji_city}",
            "moto_interest": "Pulsar <200>",
            "habeas_data_accepted": true
          }}
        }}
        """
        result, is_valid = clean_json_voorhees(raw_payload)
        self.assertTrue(is_valid)
        extracted = result["extracted"]

        # 1. Cero control-chars en TODOS los campos críticos sanitizados
        for field in ("name", "city", "moto_interest"):
            assert_no_control_chars(extracted[field])
        # 2. Whitelist estricta (sin emoji, @, <, >, $, #)
        for field in ("name", "city", "moto_interest"):
            assert_pii_whitelist(extracted[field])
        # 3. Truncado a 50 chars (el nombre de 60+ chars queda en <= 50)
        for field in ("name", "city", "moto_interest"):
            assert_truncated_50(extracted[field])
        self.assertLessEqual(len(extracted["name"]), 50)
        self.assertGreater(len(extracted["name"]), 40)  # truncado real, no borrado
        # 4. Email imposibilitado ('@' fuera de whitelist → no hay leak de email)
        assert_no_pii_leak(extracted["name"], check_phone=False)
        # 5. El valor sanitizado conserva el contenido legítimo
        self.assertTrue(extracted["city"].startswith("Bogotá"))

        # Contrato directo sobre el campo con control-chars crudos
        result_ctrl, valid_ctrl = clean_json_voorhees(f"""
        {{"summary": "s", "extracted": {{"name": "Jua\\u0000n Pérez", "habeas_data_accepted": true}}}}
        """)
        self.assertTrue(valid_ctrl)
        assert_no_control_chars(result_ctrl["extracted"]["name"])
        self.assertEqual(result_ctrl["extracted"]["name"], "Juan Pérez")

    def test_pii_validators_mutation_checks(self):
        """[HA-4] Mutation checks: los validadores PII DEBEN fallar ante input mutado
        (anti-falso-positivo) y el bypass del sanitizador queda evidenciado."""
        # M1 — control-char residual → assert_no_control_chars falla
        with pytest.raises(AssertionError):
            assert_no_control_chars("Jua\x00n")
        # M2 — violador de whitelist (emoji) → assert_pii_whitelist falla
        with pytest.raises(AssertionError):
            assert_pii_whitelist("Bogotá 😀")
        # M3 — violador de whitelist (@) → assert_pii_whitelist falla
        with pytest.raises(AssertionError):
            assert_pii_whitelist("juan@gmail.com")
        # M4 — 51 chars → assert_truncated_50 falla
        with pytest.raises(AssertionError):
            assert_truncated_50("x" * 51)
        # M5 — teléfono CO crudo → assert_no_pii_leak falla
        with pytest.raises(AssertionError):
            assert_no_pii_leak("Contacto: +57 319 856 7788")
        # M6 — email crudo → assert_no_pii_leak falla
        with pytest.raises(AssertionError):
            assert_no_pii_leak("Email: juan.perez@gmail.com")
        # M7 — BYPASS del sanitizador: el INPUT CRUDO (sin _sanitize_fields) es
        # rechazado por los validadores → prueba que la sanitización hace el trabajo.
        raw_unsanitized = "Jua\x00n 😀 gmail.com " + "y" * 60
        with pytest.raises(AssertionError):
            assert_no_control_chars(raw_unsanitized)
        with pytest.raises(AssertionError):
            assert_pii_whitelist(raw_unsanitized)
        with pytest.raises(AssertionError):
            assert_truncated_50(raw_unsanitized)

if __name__ == '__main__':
    unittest.main()
