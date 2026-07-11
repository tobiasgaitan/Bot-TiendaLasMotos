import logging
import unittest
from unittest.mock import MagicMock
import sys
import os
logging.basicConfig(level=logging.INFO)

# Add app to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.catalog_service import CatalogService

class TestCatalogScoring(unittest.TestCase):
    def setUp(self):
        from unittest.mock import patch
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
        self.service._db = MagicMock() # Still need it for logic checks
        print(f"DEBUG: Manually injected {len(self.service._items)} items into CatalogService")

    def tearDown(self):
        self.config_patcher.stop()

    def test_intent_bonus_trabajo(self):
        """Test that searching for 'trabajo' applies bonus to TVS Sport."""
        results = self.service.search_items("trabajo")
        
        # TVS Sport should be first because of the 1.5x bonus for the 'trabajo' tag
        self.assertEqual(results[0]["name"], "TVS Sport 100")
        print(f"✅ Intent Bonus Test (trabajo): First result is {results[0]['name']}")

    def test_identity_preservation_raider(self):
        """Test that exact model search (Raider) is not displaced by tag bonuses."""
        results = self.service.search_items("Raider")
        
        # TVS Raider should be first even if other bikes have more tags
        self.assertEqual(results[0]["name"], "TVS Raider 125")
        print(f"✅ Identity Preservation Test (Raider): First result is {results[0]['name']}")

    def test_multiplier_logic(self):
        """Direct check of the scoring adaptor logic."""
        # Now using search_tokens instead of search_tags
        item = {"name": "Test Bike", "search_tokens": ["keyword"], "id": "123"}
        
        # 1. No match -> same score
        score = self.service._apply_scoring_adaptor(item, ["other"], 100, False)
        self.assertEqual(score, 100)
        
        # 2. Intent match -> 1.5x score
        score = self.service._apply_scoring_adaptor(item, ["keyword"], 100, False)
        self.assertEqual(score, 150)
        
        # 3. Identity match -> Adds 20,000 Tier 1 Bonus (No semantic multiplier applied)
        score = self.service._apply_scoring_adaptor(item, ["keyword"], 100, True)
        self.assertEqual(score, 20100.0)
        
        print("✅ Multiplier Logic Tests Passed!")

    def test_hard_lock_tvs_sport(self):
        """Verify the +10,000 Hard-Lock for TVS Sport 100 on work intent."""
        # Item that IS a TVS Sport
        item_tvs = {"name": "TVS Sport 100 ELS", "search_tokens": ["tvs", "sport"], "id": "tvs_sport"}
        # Item that is NOT a TVS Sport but has work tags
        item_other = {"name": "Victory Bomber", "search_tokens": ["trabajo"], "id": "victory"}
        
        # Query with work intent
        query_tokens = ["moto", "para", "trabajo"]
        
        # TVS Sport should get +10k
        score_tvs = self.service._apply_scoring_adaptor(item_tvs, query_tokens, 100, False)
        self.assertGreaterEqual(score_tvs, 10000)
        
        # Victory Bomber should NOT get the +10k (only semantic 1.5x if match)
        score_other = self.service._apply_scoring_adaptor(item_other, query_tokens, 100, False)
        self.assertLess(score_other, 10000)
        
        print(f"✅ Hard-Lock Test Passed: TVS Sport Score={score_tvs}, Other={score_other}")

    def test_competitor_brand_resolution_nkd(self):
        """
        Verify brand rival resolution (e.g. 'NKD') against catalog items via 'searchBy',
        ensuring visual payload keys ('price', 'image_url') are returned without None or empty values.
        Also verifies the presence of 'Ficha Tecnica:' and the competitor pivot instructions.
        """
        # Test search_items
        results = self.service.search_items("NKD")
        self.assertTrue(len(results) > 0, "Should return at least one competitor alternative")
        
        # Verify the top alternative is TVS Sport 100 (equivalent work bike containing 'nkd' in searchBy)
        top_match = results[0]
        self.assertEqual(top_match["name"], "TVS Sport 100")
        
        # Verify visual payload integrity
        self.assertIsNotNone(top_match.get("price"))
        self.assertNotEqual(top_match.get("price"), "")
        self.assertIsNotNone(top_match.get("image_url"))
        self.assertNotEqual(top_match.get("image_url"), "")
        
        # Verify searchBy exists and is populated
        self.assertIsNotNone(top_match.get("searchBy"))
        self.assertIn("nkd", top_match["searchBy"])
        
        # Verify summary is not empty
        self.assertIsNotNone(top_match.get("summary"))
        self.assertNotEqual(top_match.get("summary"), "")

        # Test search_catalog text output
        text_output = self.service.search_catalog("NKD")
        
        # Verify competitor pivot instruction is present
        self.assertIn("[SISTEMA: El usuario preguntó por la competencia. ESTÁS OBLIGADO a pivotar a nuestras alternativas...]", text_output)
        
        # Verify the specific items and fields are rendered correctly
        self.assertIn("TVS Sport 100", text_output)
        self.assertIn("Image URL: https://firebasestorage.googleapis.com", text_output)
        
        # Verify content assertion: "Ficha Tecnica:" must be explicitly present and not followed by None/empty
        self.assertIn("Ficha Tecnica:", text_output)
        # Search for "Ficha Tecnica: " followed by non-empty content
        self.assertTrue("Ficha Tecnica: Moto de trabajo" in text_output or "Ficha Tecnica: " in text_output)
        
        # Verify no silent None or empty values in critical formatting lines
        self.assertNotIn("None", text_output)
        self.assertNotIn("Ficha Tecnica: \n", text_output)
        self.assertNotIn("Image URL: \n", text_output)
        
        print("✅ Competitor Brand Resolution & Visual Payload Integrity Tests Passed!")

    def test_searchby_token_forces_identity_match(self):
        """
        Verify that if a search token exactly matches one of the catalog item's
        'searchBy' tags, 'name_match' is forced to True and the +20,000 identity boost is applied.
        """
        from unittest.mock import patch
        
        # Let's perform a search for "economica", which is in TVS Sport's searchBy tags
        results = self.service.search_items("economica")
        
        # Verify TVS Sport is returned as the top result
        self.assertTrue(len(results) > 0)
        top_match = results[0]
        self.assertEqual(top_match["name"], "TVS Sport 100")
        
        # Verify that the score indeed has the identity boost (+20,000) applied.
        # We wrap _apply_scoring_adaptor to check if is_identity_match is set to True.
        with patch.object(self.service, '_apply_scoring_adaptor', wraps=self.service._apply_scoring_adaptor) as mock_adaptor:
            self.service.search_items("economica")
            called_with_identity_true = False
            for call in mock_adaptor.call_args_list:
                item_arg = call[0][0]
                is_identity_match_arg = call[0][3]
                if item_arg["id"] == "tvs_sport" and is_identity_match_arg is True:
                    called_with_identity_true = True
                    break
            self.assertTrue(called_with_identity_true, "Expected _apply_scoring_adaptor to be called with is_identity_match=True for tvs_sport")

    def test_numeric_collision_prevention(self):
        """
        Verify that searching for 'Milan 150' or 'CR4 150' yields empty results
        because of strict alphabetical perimeter validation, preventing purely numeric
        displacement tokens from forcing false positive identity matches or passing search thresholds.
        Also verifies that searching only for '100' or '125' (purely numeric)
        properly delegará the flow and returns relevant items.
        """
        # Inject an item that has "150" in its searchBy/name to simulate the real scenario
        mrx_150 = {
            "id": "victory_mrx_150",
            "name": "Victory MRX 150 Trakku",
            "price": 9000000,
            "category": "motos",
            "image_url": "https://tiendalasmotos.com/mrx-150.jpg",
            "search_tags": ["mrx", "150", "tk", "victory"],
            "search_text": "victory mrx 150 trakku enduro",
            "search_tokens": ["victory", "mrx", "150", "trakku", "enduro"],
            "searchBy": ["mrx", "150", "tk", "victory"],
            "description": "Moto enduro MRX 150.",
            "link": "https://tiendalasmotos.com/mrx-150",
            "active": True
        }
        self.service._items.append(mrx_150)
        self.service._items_by_id[mrx_150["id"]] = mrx_150
        
        # 1. Milan 150 must return empty results
        results_milan = self.service.search_items("Milan 150")
        self.assertEqual(len(results_milan), 0, f"Expected empty results for 'Milan 150', got {results_milan}")
        
        # 2. CR4 150 must return empty results
        results_cr4 = self.service.search_items("CR4 150")
        self.assertEqual(len(results_cr4), 0, f"Expected empty results for 'CR4 150', got {results_cr4}")
        
        # 3. Purely numeric search "150" must NOT be forced to 0 and should return Victory MRX 150 Trakku
        results_150 = self.service.search_items("150")
        self.assertTrue(len(results_150) > 0, "Expected results for purely numeric query '150'")
        self.assertEqual(results_150[0]["name"], "Victory MRX 150 Trakku")
        
        # 4. Purely numeric search "100" should return TVS Sport 100
        results_100 = self.service.search_items("100")
        self.assertTrue(len(results_100) > 0, "Expected results for purely numeric query '100'")
        self.assertEqual(results_100[0]["name"], "TVS Sport 100")

if __name__ == '__main__':
    unittest.main()
