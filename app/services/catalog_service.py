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
        Load catalog items from Firestore into memory.
        
        Loads all documents from pagina/catalogo/items collection
        and builds indexes for fast lookup by ID and category.
        """
        try:
            logger.info("🏍️  Loading catalog from Firestore...")
            
            # Query all items from catalog
            items_ref = self._db.collection("catalog_items")
            items_docs = items_ref.stream()
            
            # Reset indexes
            self._items = []
            self._items_by_id = {}
            self._items_by_category = {}
            
            # Process each item
            for doc in items_docs:
                item_data = doc.to_dict()
                item_data["id"] = doc.id  # Add document ID to item data
                
                # Add to main list
                self._items.append(item_data)
                
                # Index by ID
                self._items_by_id[doc.id] = item_data
                
                # Index by category
                category = item_data.get("category", "uncategorized")
                if category not in self._items_by_category:
                    self._items_by_category[category] = []
                self._items_by_category[category].append(item_data)
            
            # Silencing legacy log to avoid confusion with V6.0 dynamic config
            # logger.info(f"✅ Catalog loaded: {len(self._items)} items")
            logger.info(f"📂 Categories: {list(self._items_by_category.keys())}")
            
        except Exception as e:
            logger.error(f"❌ Error loading catalog: {str(e)}")
            # Initialize with empty lists to prevent None errors
            self._items = []
            self._items_by_id = {}
            self._items_by_category = {}
    
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
            item_id: Document ID of the item
            
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
