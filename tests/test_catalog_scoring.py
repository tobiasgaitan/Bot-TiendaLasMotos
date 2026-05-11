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
            "search_tags": ["trabajo", "economica", "mensajeria"],
            "search_text": "tvs sport 100 trabajo economica mensajeria",
            "search_tokens": ["tvs", "sport", "100", "trabajo", "economica", "mensajeria"],
            "active": True
        }
        
        item2 = {
            "id": "victory_bomber",
            "name": "Victory Bomber 125",
            "price": 5500000,
            "category": "urbana",
            "search_tags": ["urbana", "pique"],
            "search_text": "victory bomber 125 urbana pique",
            "search_tokens": ["victory", "bomber", "125", "urbana", "pique"],
            "active": True
        }
        
        item3 = {
            "id": "tvs_raider",
            "name": "TVS Raider 125",
            "price": 6000000,
            "category": "deportiva",
            "search_tags": ["sport", "tecnologia"],
            "search_text": "tvs raider 125 deportiva sport tecnologia",
            "search_tokens": ["tvs", "raider", "125", "deportiva", "sport", "tecnologia"],
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

if __name__ == '__main__':
    unittest.main()
