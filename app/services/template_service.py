"""
Template Service
================
Provides dynamic configuration for Meta WhatsApp templates.
Queries Firestore to get the dynamic fields required for each template
and caches the results to prevent read saturation during mass campaigns.
"""

import logging
import time
from typing import List, Dict, Optional
from google.cloud import firestore

logger = logging.getLogger(__name__)

class TemplateService:
    """
    Singleton service to fetch and cache template configurations.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TemplateService, cls).__new__(cls)
            cls._instance._cache: Dict[str, dict] = {}
            cls._instance._ttl = 300  # 5 minutes cache
            cls._instance.db = None
        return cls._instance

    def _get_db(self):
        """Lazy initialization of Firestore client."""
        if self.db is None:
            # We use AsyncClient to support async fetch
            self.db = firestore.AsyncClient()
        return self.db

    async def get_template_fields(self, template_name: str) -> List[str]:
        """
        Retrieves the required fields for a given template from Firestore.
        Uses a 5-minute TTL cache.
        
        Args:
            template_name: The ID of the template configuration in Firestore.
            
        Returns:
            A list of field names. Returns empty list if not found or on error.
        """
        current_time = time.time()
        
        # Check cache
        if template_name in self._cache:
            cache_entry = self._cache[template_name]
            if current_time - cache_entry['timestamp'] < self._ttl:
                logger.debug(f"🔍 Template '{template_name}' retrieved from cache.")
                return cache_entry['fields']
            else:
                logger.debug(f"♻️ Cache for template '{template_name}' expired.")
                
        try:
            db = self._get_db()
            doc_ref = db.collection("template_configs").document(template_name)
            doc = await doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                fields = data.get("fields", [])
                
                # Update cache
                self._cache[template_name] = {
                    'fields': fields,
                    'timestamp': current_time
                }
                
                logger.info(f"✅ Template '{template_name}' fetched from Firestore and cached. Fields: {fields}")
                return fields
            else:
                logger.warning(f"⚠️ Template config '{template_name}' not found in Firestore. Returning empty fields.")
                return []
                
        except Exception as e:
            logger.error(f"❌ Error fetching template config '{template_name}': {e}", exc_info=True)
            return []

# Singleton instance
template_service = TemplateService()
