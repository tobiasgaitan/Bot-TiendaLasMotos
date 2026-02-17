"""
Catalog Service
Manages motorcycle catalog from Firestore.
Provides in-memory access to catalog items with category filtering.
"""

import logging
from typing import List, Dict, Any, Optional

from google.cloud import firestore

logger = logging.getLogger(__name__)


class CatalogService:
    """
    Service for managing motorcycle catalog from Firestore.
    
    Loads catalog items at startup and keeps them in memory
    for fast access and filtering by category.
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
        
        Loads all documents from the root 'catalogo' collection
        and builds indexes for fast lookup by ID and category.
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
                raw_data = doc.to_dict()
                
                # --- Availability Logic ---
                # Default to Available unless 'active' is explicitly False
                # (Some legacy items might not have the 'active' field)
                is_active = raw_data.get("active", True)
                if not is_active:
                    continue

                # --- Data Mapping ---
                item_data = self._map_firestore_data(doc.id, raw_data)
                
                # Add to main list
                self._items.append(item_data)
                
                # Index by ID (using the mapped logical ID)
                self._items_by_id[item_data["id"]] = item_data
                
                # Index by category
                category = item_data.get("category", "general")
                if category not in self._items_by_category:
                    self._items_by_category[category] = []
                self._items_by_category[category].append(item_data)
            
            logger.info(f"✅ Catalog loaded: {len(self._items)} items from 'catalogo'")
            logger.info(f"📂 Categories: {list(self._items_by_category.keys())}")
            
        except Exception as e:
            logger.error(f"❌ Error loading catalog: {str(e)}")
            # Initialize with empty lists to prevent None errors
            self._items = []
            self._items_by_id = {}
            self._items_by_category = {}
    
    def _map_firestore_data(self, doc_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map raw Firestore data to the standardized internal item format.
        
        Args:
            doc_id: The Firestore document ID.
            data: The raw dictionary from Firestore.
            
        Returns:
            Standardized item dictionary.
        """
        # 1. ID & Name
        # Prefer 'referencia' -> 'nombre' -> doc_id
        # We use a normalized ID for internal lookups
        raw_name = data.get("referencia") or data.get("nombre") or doc_id
        item_id = str(raw_name).lower().replace(" ", "-") # Simple normalization
        
        # 2. Price
        # Handle string prices like "5.000.000" or integers
        price = 0
        raw_price = data.get("precio", 0)
        try:
            if isinstance(raw_price, (int, float)):
                price = int(raw_price)
            elif isinstance(raw_price, str):
                # Remove currency symbols, dots, etc.
                clean_price = raw_price.replace("$", "").replace(".", "").replace(",", "").strip()
                if clean_price:
                    price = int(clean_price)
        except (ValueError, TypeError):
            logger.warning(f"⚠️ Could not parse price for item {doc_id}: {raw_price}")
            price = 0

        # 3. Image
        # Check 'imagen', 'foto', 'thumbnail'. Handle lists or strings.
        image_url = ""
        for img_field in ["imagen", "foto", "thumbnail", "image"]:
            val = data.get(img_field)
            if val:
                if isinstance(val, list) and len(val) > 0:
                    image_url = val[0]
                    break
                elif isinstance(val, str) and val.strip():
                    image_url = val
                    break
        
        # 4. Category
        # Default to 'general' if missing
        category = data.get("categoria", "general").lower()
        
        return {
            "id": item_id,
            "name": str(raw_name).strip(),  # Display Name
            "price": price,
            "formatted_price": f"${price:,.0f}".replace(",", "."), # COP formatting
            "image": image_url,
            "category": category,
            "description": data.get("descripcion", ""),
            "specs": data.get("ficha_tecnica", {}), # Preserve raw specs if avail
            "raw_id": doc_id # Keep reference to original doc ID
        }

    def get_all_items(self) -> List[Dict[str, Any]]:
        """
        Get all catalog items.
        
        Returns:
            List of all catalog items
        """
        return self._items
    
    def get_by_id(self, item_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific item by ID.
        
        Args:
            item_id: Document ID or normalized name of the item
            
        Returns:
            Item data if found, None otherwise
        """
        return self._items_by_id.get(item_id)
    
    def get_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        Get all items in a specific category.
        
        Args:
            category: Category name to filter by
            
        Returns:
            List of items in the specified category
        """
        return self._items_by_category.get(category, [])
    
    def get_categories(self) -> List[str]:
        """
        Get list of all available categories.
        
        Returns:
            List of category names
        """
        return list(self._items_by_category.keys())
    
    def refresh(self) -> None:
        """
        Refresh catalog from Firestore.
        
        Can be called to reload catalog without restarting the app.
        """
        logger.info("🔄 Refreshing catalog...")
        self.load_catalog()


# Global service instance
catalog_service = CatalogService()
