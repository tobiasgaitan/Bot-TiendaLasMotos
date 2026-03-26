
import unittest
import sys
import os

# Add app to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.utils.json_processor import clean_json_voorhees

class TestJsonVoorhees(unittest.TestCase):
    def test_strip_markdown(self):
        """Test removing markdown code blocks."""
        raw = '```json\n{"summary": "Test", "extracted": {"nombre": "Tobias"}}\n```'
        result, is_valid = clean_json_voorhees(raw)
        self.assertTrue(is_valid)
        self.assertEqual(result["extracted"]["nombre"], "Tobias")

    def test_fix_quotes_and_commas(self):
        """Test fixing smart quotes and trailing commas."""
        raw = '{"summary": "Test", "extracted": {"ciudad": “Medellín”,},}'
        result, is_valid = clean_json_voorhees(raw)
        self.assertTrue(is_valid)
        self.assertEqual(result["extracted"]["ciudad"], "Medellín")

    def test_sanitize_pii_and_utf8(self):
        """Test PII sanitization (regex) and UTF-8 normalization."""
        # Name with special chars that should be stripped, and accents that should be normalized
        raw = '{"summary": "Test", "extracted": {"nombre": "Tobiás! @Gaita-n_123"}}'
        result, is_valid = clean_json_voorhees(raw)
        self.assertTrue(is_valid)
        # Regex [^a-zA-Z0-9áéíóúÁÉÍÓÚñÑ\s\.\-]
        # '!' and '@' and '_' should be gone, but '-' stays
        self.assertEqual(result["extracted"]["nombre"], "Tobiás Gaita-n123")
        print(f"✅ Sanitized name: {result['extracted']['nombre']}")

    def test_fallback_preserved_minimal(self):
        """Test that invalid JSON returns the preserved minimal state."""
        raw = 'This is not JSON at all'
        result, is_valid = clean_json_voorhees(raw, session_id="test_session", last_intent="testing")
        self.assertFalse(is_valid)
        self.assertEqual(result["session_id"], "test_session")
        self.assertEqual(result["last_valid_intent"], "testing")
        self.assertTrue(result["preserved_minimal"])
        print("✅ Fallback Preserved Minimal State Verified!")

if __name__ == '__main__':
    unittest.main()
