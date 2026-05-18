import logging
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import sys
import os

# Add app to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.catalog_service import CatalogService

logging.basicConfig(level=logging.INFO)

class TestCatalogPriceBonus(unittest.TestCase):
    def setUp(self):
        self.service = CatalogService()
        
        # Mock config service to avoid external calls and global pollution
        self.config_patcher = patch('app.services.config_service.config_service')
        self.mock_config = self.config_patcher.start()
        self.mock_config.get_registration_cost.return_value = 0
        
        self.service._db = MagicMock()

    def tearDown(self):
        self.config_patcher.stop()

    def test_load_catalog_extracts_canonical_price_and_bonus(self):
        """
        Verify that load_catalog:
        1. Uses ONLY the canonical 'price' key.
        2. Successfully extracts bonusAmount and bonusEndDate.
        """
        # Create a mock Firestore document
        mock_doc = MagicMock()
        mock_doc.id = "tvs_sport"
        
        # Test item data: uses both 'precio' (legacy/incorrect) and 'price' (canonical).
        # We explicitly set 'precio' to a different value to ensure it is NOT chosen,
        # since the instruction is: price_val = data.get("price") or 0.
        future_date = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
        mock_doc.to_dict.return_value = {
            "brand": "TVS",
            "referencia": "Sport 100",
            "precio": 9999999,  # Legacy key, should be ignored
            "price": 5000000,   # Canonical key
            "categoria": "trabajo",
            "imagen_url": "https://example.com/tvs_sport.jpg",
            "active": True,
            "isVisible": True,
            "onStock": True,
            "bonusAmount": 200000,
            "bonusEndDate": future_date
        }
        
        # Mock the collection query stream
        mock_stream = MagicMock()
        mock_stream.__iter__.return_value = [mock_doc]
        
        self.service._db.collection.return_value.document.return_value.collection.return_value.stream.return_value = [mock_doc]
        
        # Call load_catalog
        self.service.load_catalog()
        
        # Verify indexes
        self.assertEqual(len(self.service._items), 1)
        item = self.service._items[0]
        
        # Assert canonical price was used
        self.assertEqual(item["price"], 5000000)
        self.assertNotEqual(item["price"], 9999999)
        
        # Assert bonus details are extracted
        self.assertEqual(item["bonusAmount"], 200000)
        self.assertEqual(item["bonusEndDate"], future_date)

    def test_get_active_bonus_info(self):
        """
        Verify that _get_active_bonus_info correctly parses and validates active/expired dates.
        """
        # 1. Valid future date (active)
        future_dt = datetime.now() + timedelta(days=2)
        future_str = future_dt.strftime("%Y-%m-%d")
        
        info = self.service._get_active_bonus_info(500000, future_str)
        self.assertIsNotNone(info)
        self.assertEqual(info["amount"], 500000)
        self.assertEqual(info["end_date"], future_dt.strftime("%Y-%m-%d"))
        
        # 2. Expired past date (None)
        past_dt = datetime.now() - timedelta(days=2)
        past_str = past_dt.strftime("%Y-%m-%d")
        
        info = self.service._get_active_bonus_info(500000, past_str)
        self.assertIsNone(info)
        
        # 3. Invalid bonus amount <= 0
        info = self.service._get_active_bonus_info(0, future_str)
        self.assertIsNone(info)
        info = self.service._get_active_bonus_info(-100, future_str)
        self.assertIsNone(info)
        
        # 4. Handle object with timestamp attribute (Mock Firestore Timestamp)
        mock_timestamp = MagicMock()
        mock_timestamp.timestamp.return_value = (datetime.now() + timedelta(days=3)).timestamp()
        mock_timestamp.to_datetime.return_value = datetime.now() + timedelta(days=3)
        mock_timestamp.tzinfo = None
        
        info = self.service._get_active_bonus_info(300000, mock_timestamp)
        self.assertIsNotNone(info)
        self.assertEqual(info["amount"], 300000)
        
        # 5. Expired mock timestamp
        mock_expired_timestamp = MagicMock()
        mock_expired_timestamp.timestamp.return_value = (datetime.now() - timedelta(days=3)).timestamp()
        mock_expired_timestamp.to_datetime.return_value = datetime.now() - timedelta(days=3)
        mock_expired_timestamp.tzinfo = None
        
        info = self.service._get_active_bonus_info(300000, mock_expired_timestamp)
        self.assertIsNone(info)

    def test_search_items_serialization_of_bonus(self):
        """
        Verify that search_items/truncated_item correcty includes active bonuses
        or sets them to 0/None when expired.
        """
        # Active bonus item
        future_date = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
        item_active = {
            "id": "tvs_sport_active",
            "name": "TVS Sport Active",
            "price": 5000000,
            "category": "trabajo",
            "imagen_url": "https://example.com/active.jpg",
            "search_tokens": ["tvs", "sport", "active"],
            "search_text": "tvs sport active",
            "cc": 100,
            "bonusAmount": 250000,
            "bonusEndDate": future_date
        }
        
        # Expired bonus item
        past_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        item_expired = {
            "id": "tvs_sport_expired",
            "name": "TVS Sport Expired",
            "price": 5000000,
            "category": "trabajo",
            "imagen_url": "https://example.com/expired.jpg",
            "search_tokens": ["tvs", "sport", "expired"],
            "search_text": "tvs sport expired",
            "cc": 100,
            "bonusAmount": 250000,
            "bonusEndDate": past_date
        }
        
        self.service._items = [item_active, item_expired]
        self.service._items_by_id = {i["id"]: i for i in self.service._items}
        
        # 1. Search active
        results_active = self.service.search_items("active")
        self.assertEqual(len(results_active), 1)
        truncated_active = results_active[0]
        self.assertEqual(truncated_active["bonusAmount"], 250000)
        self.assertEqual(truncated_active["bonusEndDate"], future_date)
        
        # 2. Search expired
        results_expired = self.service.search_items("expired")
        self.assertEqual(len(results_expired), 1)
        truncated_expired = results_expired[0]
        self.assertEqual(truncated_expired["bonusAmount"], 0)
        self.assertIsNone(truncated_expired["bonusEndDate"])

    def test_search_catalog_markdown_mutation(self):
        """
        Verify that search_catalog formats the Markdown string to include
        the explicit '[BONO EXCLUSIVO DE CONTADO: $X válido hasta Y]' only when active.
        """
        future_date = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
        item_active = {
            "id": "tvs_sport_active",
            "name": "TVS Sport Active",
            "price": 5000000,
            "category": "trabajo",
            "imagen_url": "https://example.com/active.jpg",
            "search_tokens": ["tvs", "sport", "active"],
            "search_text": "tvs sport active",
            "cc": 100,
            "bonusAmount": 250000,
            "bonusEndDate": future_date
        }
        
        past_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        item_expired = {
            "id": "tvs_sport_expired",
            "name": "TVS Sport Expired",
            "price": 5000000,
            "category": "trabajo",
            "imagen_url": "https://example.com/expired.jpg",
            "search_tokens": ["tvs", "sport", "expired"],
            "search_text": "tvs sport expired",
            "cc": 100,
            "bonusAmount": 250000,
            "bonusEndDate": past_date
        }
        
        self.service._items = [item_active, item_expired]
        self.service._items_by_id = {i["id"]: i for i in self.service._items}
        
        # 1. Search active
        res_active = self.service.search_catalog("active")
        self.assertIn("[BONO EXCLUSIVO DE CONTADO: $250.000 válido hasta", res_active)
        self.assertIn(future_date, res_active)
        
        # 2. Search expired
        res_expired = self.service.search_catalog("expired")
        self.assertNotIn("[BONO EXCLUSIVO DE CONTADO", res_expired)

if __name__ == '__main__':
    unittest.main()
