
import unittest
import sys
import os
import re
import unicodedata

# Add app to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.ai_brain import CerebroIA
from app.utils.json_processor import clean_json_voorhees


class _FakeCatalog:
    """Minimal catalog stand-in for canonicity tests (no Firestore)."""

    def __init__(self, items):
        self._items = items

    @staticmethod
    def _normalize_item_id_key(raw: str) -> str:
        if not raw or not isinstance(raw, str):
            return ""
        s = unicodedata.normalize("NFKC", raw).lower().strip()
        s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
        s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
        return s

    def search_items(self, query: str, trace_id=None):
        q = query.lower()
        matches = []
        for item in self._items:
            name = str(item.get("name", "")).lower()
            tags = [str(t).lower() for t in item.get("searchBy", [])]
            if q in name or any(q in t for t in tags):
                matches.append(item)
        return matches[:3]


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
        GIVEN: El prospecto tiene habeas_data_accepted=True (canonical key v7.7.0).
        BUT: habeas_data_accepted_sent es False.
        THEN: El orquestador DEBE inyectar PHASE_2_HABEAS_DATA (no PHASE_3).

        WHY canonical key: _determine_funnel_phase reads prospect_data.get("habeas_data_accepted")
        as of refactor b4471b3. Tests must use this key to correctly exercise the gate.
        """
        prospect_data = {
            "nombre": "Test User",
            "ciudad": "Medellin",
            "moto_interest": "TVS Raider",
            "moto_confirmada": True,
            "forma_pago": "credito",
            "habeas_data_accepted": True,        # Canonical key (v7.7.0) — was habeas_data_accepted_accepted
            "habeas_data_accepted_sent": False   # Gate condition: script not sent yet
        }
        
        # Test con history vacío — no toca la rama de intent financiero (.get("role"))
        phase = self.cerebro._determine_funnel_phase(prospect_data, history=[])
        self.assertEqual(phase, "PHASE_2_HABEAS_DATA", "Debe bloquear PHASE_3 si el script no fue enviado.")

    def test_phase_block_without_physical_link(self):
        """
        [BOT-BUILD-CLASSIFIER-011] Re-pin de reconciliación: el documento padre
        pasa a ser la fuente primaria de verdad para el consentimiento.

        GIVEN: habeas_data_accepted=True y habeas_data_accepted_sent=True en DB.
        BUT: El link físico de privacidad no está en el historial del chat.
        THEN: El orquestador DEBE avanzar a PHASE_3 (no bloquear).

        WHY: `habeas_data_accepted_sent=True` en el padre ya atestigua que el bot
        envió el script legal y el enlace. El link físico en historial queda como
        evidencia fallback (OR), no como requisito bloqueante.
        """
        prospect_data = {
            "nombre": "Test User",
            "ciudad": "Medellin",
            "moto_interest": "TVS Raider",
            "moto_confirmada": True,
            "forma_pago": "credito",
            "habeas_data_accepted": True,        # Canonical key (v7.7.0)
            "habeas_data_accepted_sent": True    # Script/link sent per parent doc
        }
        # history=[] → no hay link físico, pero accepted_sent del padre es suficiente
        history = []

        phase = self.cerebro._determine_funnel_phase(prospect_data, history=history)
        self.assertEqual(phase, "PHASE_3_CREDIT_PROFILING", "Con consentimiento latcheado en padre, el link físico en historial no debe bloquear PHASE_3.")

    def test_phase_allowed_with_sent_and_accepted(self):
        """
        Verifica que el avance a PHASE_3 sea permitido si AMBOS flags son True Y el link está en el historial.
        Uses canonical key 'habeas_data_accepted' (v7.7.0).
        """
        prospect_data = {
            "nombre": "Test User",     # Required by has_name check (line 329)
            "ciudad": "Medellin",
            "moto_interest": "TVS Raider",
            "moto_confirmada": True,
            "forma_pago": "credito",
            "habeas_data_accepted": True,        # Canonical key (v7.7.0)
            "habeas_data_accepted_sent": True
        }
        # History con el link de privacidad en el texto de .parts
        history = [
            type('obj', (object,), {'parts': [type('obj', (object,), {'text': 'Acepta aqui: tiendalasmotos.com/politica-de-privacidad'})()]})(),
            type('obj', (object,), {'parts': [type('obj', (object,), {'text': 'Sí, acepto.'})()]})()
        ]
        
        phase = self.cerebro._determine_funnel_phase(prospect_data, history=history)
        self.assertEqual(phase, "PHASE_3_CREDIT_PROFILING", "Debe permitir PHASE_3 si hay evidencia del link y aceptación.")

    def test_phase_1_when_category_plus_credit_intent(self):
        """
        [BOT-BUILD-FUNNEL-SKIP-014 PIN-014-A1]
        GIVEN: moto_interest is a category (non-canonical), history contains credit intent.
        THEN: Must stay in PHASE_1_PROFILING (not jump to Habeas).
        """
        catalog = _FakeCatalog([
            {"name": "Victory MRX 150", "searchBy": ["doble proposito", "enduro"]},
        ])
        cerebro = CerebroIA(catalog_service=catalog)
        prospect_data = {
            "moto_interest": "doble propósito",
            "forma_pago": "",
            "habeas_data_accepted": False,
            "habeas_data_accepted_sent": False,
        }
        history = [{"role": "user", "content": "Hola, quisiera una moto doble propósito a crédito"}]
        phase = cerebro._determine_funnel_phase(prospect_data, history=history)
        self.assertEqual(phase, "PHASE_1_PROFILING", "Categoría + intención de crédito no debe saltar a Habeas.")

    def test_phase_3_with_canonical_moto_and_habeas_complete(self):
        """
        [BOT-BUILD-FUNNEL-SKIP-014 PIN-014-A2]
        GIVEN: canonical moto, habeas accepted+sent, name+city present.
        THEN: PHASE_3_CREDIT_PROFILING (no regression from 011).
        """
        catalog = _FakeCatalog([
            {"name": "TVS Raider 125", "searchBy": ["sport"]},
        ])
        cerebro = CerebroIA(catalog_service=catalog)
        prospect_data = {
            "nombre": "Test",
            "ciudad": "Medellin",
            "moto_interest": "TVS Raider 125",
            "moto_confirmada": True,
            "forma_pago": "credito",
            "habeas_data_accepted": True,
            "habeas_data_accepted_sent": True,
        }
        phase = cerebro._determine_funnel_phase(prospect_data, history=[])
        self.assertEqual(phase, "PHASE_3_CREDIT_PROFILING", "Modelo canónico + habeas completo debe mantener PHASE_3.")

    def test_phase_1_when_category_with_habeas_latches(self):
        """
        [BOT-BUILD-FUNNEL-SKIP-014 PIN-014-A3]
        GIVEN: non-canonical category but habeas_data_accepted=True and sent=True.
        THEN: Still PHASE_1_PROFILING because moto is not canonical.
        """
        catalog = _FakeCatalog([
            {"name": "Victory MRX 150", "searchBy": ["doble proposito", "enduro"]},
        ])
        cerebro = CerebroIA(catalog_service=catalog)
        prospect_data = {
            "nombre": "Test",
            "ciudad": "Medellin",
            "moto_interest": "doble propósito",
            "forma_pago": "credito",
            "habeas_data_accepted": True,
            "habeas_data_accepted_sent": True,
        }
        history = [{"role": "user", "content": "Hola, quisiera una moto doble propósito a crédito"}]
        phase = cerebro._determine_funnel_phase(prospect_data, history=history)
        self.assertEqual(phase, "PHASE_1_PROFILING", "Categoría no canónica nunca debe activar Habeas aunque latches estén True.")

    def test_phase_1_when_canonical_moto_without_credit_or_habeas(self):
        """
        [BOT-BUILD-FUNNEL-SKIP-014 PIN-014-A4]
        GIVEN: canonical moto, no forma_pago, no habeas, no financial intent in history.
        THEN: PHASE_1_PROFILING (recommendation phase, not Habeas).
        """
        catalog = _FakeCatalog([
            {"name": "TVS Raider 125", "searchBy": ["sport"]},
        ])
        cerebro = CerebroIA(catalog_service=catalog)
        prospect_data = {
            "moto_interest": "TVS Raider 125",
            "forma_pago": "",
            "habeas_data_accepted": False,
            "habeas_data_accepted_sent": False,
        }
        history = [{"role": "user", "content": "Me gusta la TVS Raider 125"}]
        phase = cerebro._determine_funnel_phase(prospect_data, history=history)
        self.assertEqual(phase, "PHASE_1_PROFILING", "Modelo canónico sin intención de crédito debe permanecer en PHASE_1.")

if __name__ == '__main__':
    unittest.main()
