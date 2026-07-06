import logging
import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add app to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.catalog_service import CatalogService

class TestCatalogDoubleBuffer(unittest.TestCase):
    def setUp(self):
        self.service = CatalogService()
        
        # Mock config service to avoid external calls and global pollution
        self.config_patcher = patch('app.services.config_service.config_service')
        self.mock_config = self.config_patcher.start()
        self.mock_config.get_registration_cost.return_value = 0
        
        self.service._db = MagicMock()

    def tearDown(self):
        self.config_patcher.stop()

    def test_load_catalog_preserves_memory_state_on_error(self):
        """
        Verify that load_catalog implements double-buffering correctly:
        1. An initial successful query populates the in-memory indexes.
        2. A subsequent query that fails with an exception does NOT wipe
           out the existing indexes, and logs the exception correctly.
        """
        # --- PHASE 1: Successful Load ---
        mock_doc = MagicMock()
        mock_doc.id = "victory_one"
        mock_doc.to_dict.return_value = {
            "brand": "Victory",
            "referencia": "One",
            "price": 4500000,
            "categoria": "urban",
            "imagen_url": "https://example.com/victory_one.jpg",
            "active": True,
            "isVisible": True,
            "onStock": True
        }
        
        # Setup Firestore collection mocks
        self.service._db.collection.return_value.document.return_value.collection.return_value.stream.return_value = [mock_doc]
        
        # Load catalog
        self.service.load_catalog()
        
        # Verify initial population
        self.assertEqual(len(self.service._items), 1)
        self.assertIn("victory_one", self.service._items_by_id)
        self.assertEqual(self.service._items_by_id["victory_one"]["price"], 4500000)
        self.assertEqual(len(self.service._items_by_category.get("urban", [])), 1)
        
        # Save snapshot of state references
        original_items = list(self.service._items)
        original_items_by_id = dict(self.service._items_by_id)
        original_items_by_category = dict(self.service._items_by_category)
        
        # --- PHASE 2: Firestore Error ---
        # Configure stream to raise a simulated connection timeout / error
        self.service._db.collection.return_value.document.return_value.collection.return_value.stream.side_effect = Exception("Simulated Firestore Timeout/Connection Error")
        
        # This call should not raise an exception to the caller, but log it internally and preserve memory state
        with patch('app.services.catalog_service.logger.exception') as mock_log_exception:
            self.service.load_catalog()
            
            # Verify exception was logged under global forensic protocol
            mock_log_exception.assert_called_once()
            
        # Verify the in-memory state is preserved intact and NOT reset to empty lists/dicts
        self.assertEqual(len(self.service._items), 1)
        self.assertEqual(self.service._items, original_items)
        self.assertEqual(self.service._items_by_id, original_items_by_id)
        self.assertEqual(self.service._items_by_category, original_items_by_category)
        self.assertEqual(self.service._items[0]["id"], "victory_one")
