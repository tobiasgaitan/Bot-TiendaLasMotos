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
            logger.info("🔍 Connecting to sub-collection: pagina/catalogo/items")
            
            if not self._db:
                logger.warning("⚠️ Firestore client not initialized in CatalogService")
                return

            # Query all items from sub-collection 'pagina/catalogo/items'
            items_ref = self._db.collection("pagina").document("catalogo").collection("items")
            items_docs = items_ref.stream()
            
            # Reset indexes
            self._items = []
            self._items_by_id = {}
            self._items_by_category = {}
            
            # Process each item
            for doc in items_docs:
                data = doc.to_dict()
                
                # --- Map Fields Explicitly (Spanish -> English, with Fallbacks) ---
                
                # Name: referencia -> nombre -> title -> name -> doc.id
                name = data.get("referencia") or data.get("nombre") or data.get("title") or data.get("name") or doc.id
                
                # Price: precio -> price
                price_val = data.get("precio") or data.get("price") or 0
                price = self._parse_price(price_val)
                
                # Category: categoria -> category -> machine_name -> 'general'
                category = data.get("categoria") or data.get("category") or data.get("machine_name") or "general"
                
                # Image: imagen -> foto -> image -> picture
                image_val = data.get("imagen") or data.get("foto") or data.get("image") or data.get("picture") or ""
                image_url = self._get_first_image(image_val)
                
                # Active Status: active -> activo -> is_active -> True (default)
                is_active = data.get("active", data.get("activo", data.get("is_active", True)))
                
                # Only process active items (unless forced to load all?) - relying on 'active' default True
                if str(is_active).lower() == 'false': # Handle string 'false' from some CMS
                    continue

                # Create standardized item
                mapped_item = {
                    "id": doc.id,
                    "name": str(name).strip(),
                    "price": price,
                    "formatted_price": f"${price:,.0f}".replace(",", "."),
                    "category": str(category).lower().strip(),
                    "image_url": image_url,
                    "active": True,
                    "description": data.get("descripcion", data.get("description", "")),
                    "specs": data.get("ficha_tecnica", data.get("specs", {}))
                }

                self._items.append(mapped_item)
                
                # Index by ID
                self._items_by_id[doc.id] = mapped_item
                
                # Index by category
                cat_key = mapped_item["category"]
                if cat_key not in self._items_by_category:
                    self._items_by_category[cat_key] = []
                self._items_by_category[cat_key].append(mapped_item)
            
            logger.info(f"✅ Catalog loaded: {len(self._items)} items from 'motos'")
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
