"""
Catalog Service
Manages motorcycle catalog from Firestore.
Provides in-memory access to catalog items with category filtering.
"""

import logging
from typing import List, Dict, Any, Optional, Union

from google.cloud import firestore

logger = logging.getLogger(__name__)


class CatalogService:
    """
    Service for managing motorcycle catalog from Firestore.
    
    Loads catalog items from the 'catalogo' collection (Spanish fields)
    and maps them to the internal English model.
    """
    
    def __init__(self):
        """Initialize the catalog service with empty state."""
        self._items: List[Dict[str, Any]] = []
        self._items_by_id: Dict[str, Dict[str, Any]] = {}
        self._items_by_category: Dict[str, List[Dict[str, Any]]] = {}
        self._db: Optional[firestore.Client] = None
    
    def initialize(self, db: firestore.Client) -> None:
        """
        Initialize the service with Firestore client and load catalog.
        
        Args:
            db: Initialized Firestore client
        """
        self._db = db
        self.load_catalog()
    
    def load_catalog(self) -> None:
        """
        Load catalog items from Firestore 'catalogo' collection into memory.
        
        Maps Spanish fields (referencia, precio, categoria) to English model.
        """
        try:
            logger.info("🏍️  Loading catalog from Firestore 'catalogo'...")
            
            if not self._db:
                logger.warning("⚠️ Firestore client not initialized in CatalogService")
                return

            # Query all items from root 'catalogo' collection
            items_ref = self._db.collection("catalogo")
            items_docs = items_ref.stream()
            
            # Reset indexes
            self._items = []
            self._items_by_id = {}
            self._items_by_category = {}
            
            # Process each item
            for doc in items_docs:
                data = doc.to_dict()
                
                # --- Map Fields Explicitly (Spanish -> English) ---
                
                # Name: referencia -> nombre -> doc.id
                name = data.get("referencia", data.get("nombre", doc.id))
                
                # Price: Handle string formats like "$ 5.000.000"
                price = self._parse_price(data.get("precio", 0))
                
                # Category: Default to 'general'
                category = data.get("categoria", "general")
                
                # Image: Handle list or string, prioritize imagen -> foto
                image_val = data.get("imagen", data.get("foto", ""))
                image_url = self._get_first_image(image_val)
                
                # Active Status
                is_active = data.get("active", True)
                
                # Only process active items
                if not is_active:
                    continue

                # Create standardized item
                mapped_item = {
                    "id": doc.id,
                    "name": str(name).strip(),
                    "price": price,
                    "formatted_price": f"${price:,.0f}".replace(",", "."),
                    "category": str(category).lower().strip(),
                    "image_url": image_url,
                    "active": is_active,
                    "description": data.get("descripcion", ""),
                    "specs": data.get("ficha_tecnica", {})
                }

                self._items.append(mapped_item)
                
                # Index by ID
                self._items_by_id[doc.id] = mapped_item
                
                # Index by category
                cat_key = mapped_item["category"]
                if cat_key not in self._items_by_category:
                    self._items_by_category[cat_key] = []
                self._items_by_category[cat_key].append(mapped_item)
            
            logger.info(f"✅ Catalog loaded: {len(self._items)} items from 'catalogo'")
            logger.info(f"📂 Categories: {list(self._items_by_category.keys())}")
            
        except Exception as e:
            logger.error(f"❌ Error loading catalog: {str(e)}")
            self._items = []
            self._items_by_id = {}
            self._items_by_category = {}

    def _parse_price(self, price_input: Any) -> int:
        """
        Helper to parse price from various formats (int, string, etc).
        Handles '$ 5.000.000', '5.000.000', etc.
        """
        if isinstance(price_input, (int, float)):
            return int(price_input)
        
        if isinstance(price_input, str):
            try:
                # Remove currency symbols, dots, commas, spaces
                clean_price = price_input.replace("$", "").replace(".", "").replace(",", "").replace(" ", "").strip()
                if not clean_price:
                    return 0
                return int(clean_price)
            except ValueError:
                return 0
        
        return 0

    def _get_first_image(self, val: Any) -> str:
        """
        Helper to extract the first valid image URL.
        Handles both string URLs and lists of URLs.
        Args:
            val: The value from Firestore (str, list, or None)
        """
        if not val:
            return ""
            
        if isinstance(val, list):
            # Return first non-empty string in list
            for item in val:
                if isinstance(item, str) and item.strip():
                    return item.strip()
        
        elif isinstance(val, str) and val.strip():
            return val.strip()
            
        return ""

    def get_all_items(self) -> List[Dict[str, Any]]:
        """Get all catalog items."""
        return self._items
    
    def get_by_id(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific item by ID."""
        return self._items_by_id.get(item_id)
    
    def get_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Get all items in a specific category."""
        return self._items_by_category.get(category, [])
    
    def get_categories(self) -> List[str]:
        """Get list of all available categories."""
        return list(self._items_by_category.keys())
    
    def refresh(self) -> None:
        """Refresh catalog from Firestore."""
        logger.info("🔄 Refreshing catalog...")
        self.load_catalog()

# Global service instance
catalog_service = CatalogService()
