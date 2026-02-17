
import unittest
from unittest.mock import MagicMock
import sys
import os

# Add app to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.catalog_service import CatalogService

class TestCatalogServiceRefactor(unittest.TestCase):
    def setUp(self):
        self.mock_db = MagicMock()
        self.service = CatalogService()

    def test_load_catalog_mapping(self):
        """Test that data is mapped correctly from Firestore docs."""
        # Mock Firestore documents
        mock_docs = []
        
        # 1. Standard Item
        doc1 = MagicMock()
        doc1.id = "moto_1"
        doc1.to_dict.return_value = {
            "referencia": "NKD 125",
            "precio": 5000000,
            "imagen": "http://img.com/nkd.jpg",
            "categoria": "Urbana",
            "active": True
        }
        mock_docs.append(doc1)

        # 2. String Price & Alternate Fields
        doc2 = MagicMock()
        doc2.id = "moto_2"
        doc2.to_dict.return_value = {
            "nombre": "Sport 100",  # Uses 'nombre' instead of 'referencia'
            "precio": "$4.500.000", # String price
            "foto": ["http://img.com/sport.jpg"], # List of stats
            "categoria": "Deportiva"
            # Missing 'active', should default to True
        }
        mock_docs.append(doc2)

        # 3. Inactive Item
        doc3 = MagicMock()
        doc3.id = "moto_3"
        doc3.to_dict.return_value = {
            "referencia": "Old Moto",
            "active": False
        }
        mock_docs.append(doc3)

        # 4. Bad Price Data & Missing Image
        doc4 = MagicMock()
        doc4.id = "moto_4"
        doc4.to_dict.return_value = {
            "referencia": "Mystery Moto",
            "precio": "Consultar", # Invalid int
            # No image fields
        }
        mock_docs.append(doc4)

        # Setup Mock DB Chain
        self.mock_db.collection.return_value.stream.return_value = mock_docs

        # Execute
        self.service.initialize(self.mock_db)
        items = self.service.get_all_items()

        # Assertions
        self.assertEqual(len(items), 3, "Should load 3 items (1 inactive skipped)")

        # Verify Item 1 (Standard)
        item1 = next(i for i in items if i["id"] == "nkd-125")
        self.assertEqual(item1["name"], "NKD 125")
        self.assertEqual(item1["price"], 5000000)
        self.assertEqual(item1["image"], "http://img.com/nkd.jpg")
        self.assertEqual(item1["category"], "urbana")

        # Verify Item 2 (Edge cases)
        item2 = next(i for i in items if i["id"] == "sport-100")
        self.assertEqual(item2["name"], "Sport 100")
        self.assertEqual(item2["price"], 4500000)
        self.assertEqual(item2["image"], "http://img.com/sport.jpg")
        
        # Verify Item 4 (Bad Data)
        item4 = next(i for i in items if i["id"] == "mystery-moto")
        self.assertEqual(item4["price"], 0)
        self.assertEqual(item4["image"], "")

        print("\n✅ Catalog Service Refactor Verification Passed!")
        print(f"   Loaded {len(items)} items correctly.")
        print(f"   Verified price parsing, field mapping, and availability logic.")

if __name__ == '__main__':
    unittest.main()
