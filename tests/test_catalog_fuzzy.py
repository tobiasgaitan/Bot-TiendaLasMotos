import logging
import unittest
from unittest.mock import MagicMock, patch
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.catalog_service import CatalogService

class TestCatalogFuzzy(unittest.TestCase):
    def setUp(self):
        self.service = CatalogService()
        
        # Guard against Global State Pollution from other tests mocking config_service
        self.config_patcher = patch('app.services.config_service.config_service')
        self.mock_config = self.config_patcher.start()
        self.mock_config.get_registration_cost.return_value = 0
        
        # Bypass Firestore loading and inject items directly
        item1 = {
            "id": "tvs_sport",
            "name": "TVS Sport 100",
            "price": 5000000,
            "category": "trabajo",
            "image_url": "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos/o/tvs_sport.jpg",
            "search_tags": ["trabajo", "economica", "mensajeria", "nkd", "boxer"],
            "search_text": "tvs sport 100 trabajo economica mensajeria nkd boxer",
            "search_tokens": ["tvs", "sport", "100", "trabajo", "economica", "mensajeria", "nkd", "boxer"],
            "searchBy": ["trabajo", "economica", "mensajeria", "nkd", "boxer"],
            "description": "Moto de trabajo muy economica y duradera con excelente consumo de combustible.",
            "link": "https://tiendalasmotos.com/tvs-sport",
            "active": True
        }
        
        item2 = {
            "id": "victory_bomber",
            "name": "Victory Bomber 125",
            "price": 5500000,
            "category": "urbana",
            "image_url": "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos/o/victory_bomber.jpg",
            "search_tags": ["urbana", "pique"],
            "search_text": "victory bomber 125 urbana pique",
            "search_tokens": ["victory", "bomber", "125", "urbana", "pique"],
            "searchBy": ["urbana", "pique"],
            "description": "Moto urbana ideal para el dia a dia con estilo clasico.",
            "link": "https://tiendalasmotos.com/victory-bomber",
            "active": True
        }
        
        item3 = {
            "id": "tvs_raider",
            "name": "TVS Raider 125",
            "price": 6000000,
            "category": "deportiva",
            "image_url": "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos/o/tvs_raider.jpg",
            "search_tags": ["sport", "tecnologia"],
            "search_text": "tvs raider 125 deportiva sport tecnologia",
            "search_tokens": ["tvs", "raider", "125", "deportiva", "sport", "tecnologia"],
            "searchBy": ["sport", "tecnologia"],
            "description": "Moto deportiva con tecnologia de punta y gran desempeño.",
            "link": "https://tiendalasmotos.com/tvs-raider",
            "active": True
        }

        self.service._items = [item1, item2, item3]
        self.service._items_by_id = {i["id"]: i for i in self.service._items}
        self.service._db = MagicMock()
        
    def tearDown(self):
        self.config_patcher.stop()

    def test_fuzzy_match_rayder_to_raider(self):
        """
        Validate that queries like 'rayder' retrieve the TVS Raider 125.
        Uses phonetic matching/synonyms in search_items.
        """
        results = self.service.search_items("rayder")
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["name"], "TVS Raider 125")
        
        # Test search_catalog text output
        text_output = self.service.search_catalog("rayder")
        self.assertIn("TVS Raider 125", text_output)

    def test_fuzzy_identity_escalation_rider(self):
        """
        [BOT-PERF-IDENTITY-CALIBRATION-122] RIGID ASSERTION — Fuzzy Identity Escalation.
        
        Validates that searching "rider" (missing 'a', common colloquial variation)
        triggers the FUZZY IDENTITY ESCALATION path (ratio >= 0.85 → name_match = True)
        and returns TVS Raider 125 as the first result.
        
        Without the fix, ratio ~ 0.91 would only add ratio*60 score points but
        name_match would stay False, blocking the critical +20,000 identity boost
        in _apply_scoring_adaptor Tier 1.
        """
        results = self.service.search_items("rider")
        # RIGID: Must return at least one result
        self.assertTrue(len(results) > 0, "search_items('rider') returned no results — escalación de identidad fallida")
        # RIGID: First result MUST be the Raider (identity match, not a random fuzzy result)
        self.assertEqual(
            results[0]["name"], "TVS Raider 125",
            f"Expected 'TVS Raider 125' as top result for 'rider', got '{results[0]['name']}'. "
            "Fuzzy Identity Escalation (+20,000 boost) is NOT firing correctly."
        )

    def test_fuzzy_identity_escalation_raidr(self):
        """
        [BOT-PERF-IDENTITY-CALIBRATION-122] Cobertura fonética adicional.
        
        Validates "raidr" (previously handled only in spelling_map but without
        a guarantee of the +20,000 identity boost). Ratio >= 0.85 path must fire.
        """
        results = self.service.search_items("raidr")
        self.assertTrue(len(results) > 0, "search_items('raidr') returned no results")
        self.assertEqual(
            results[0]["name"], "TVS Raider 125",
            f"Expected 'TVS Raider 125' as top result for 'raidr', got '{results[0]['name']}'"
        )

if __name__ == '__main__':
    unittest.main()
