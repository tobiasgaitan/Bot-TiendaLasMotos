"""
Configuration Service
Loads and manages Firestore configuration documents in memory.
Provides fast access to financial and partner configuration.
"""

import logging
from typing import Dict, Any, Optional

from google.cloud import firestore

logger = logging.getLogger(__name__)


class ConfigService:
    """
    Service for managing application configuration from Firestore.
    
    Loads configuration documents at startup and keeps them in memory
    for fast access during request processing.
    """
    
    def __init__(self):
        """Initialize the configuration service with empty state."""
        self._financial_config: Optional[Dict[str, Any]] = None
        self._partners_config: Optional[Dict[str, Any]] = None
        self._db: Optional[firestore.Client] = None
    
    def initialize(self, db: firestore.Client) -> None:
        """
        Initialize the service with Firestore client and load configurations.
        
        Args:
            db: Initialized Firestore client
        """
        self._db = db
        self.load_configurations()
    
    def load_configurations(self) -> None:
        """
        Load configuration documents from Firestore into memory.
        
        Loads:
            - configuracion/financiera: Financial configuration (rates, fees, etc.)
            - configuracion/aliados: Partner/entity configuration
        """
        try:
            logger.info("📋 Loading configuration from Firestore...")
            
            # Load financial configuration
            financial_ref = self._db.collection("configuracion").document("financiera")
            financial_doc = financial_ref.get()
            
            if financial_doc.exists:
                self._financial_config = financial_doc.to_dict()
                logger.info(f"✅ Financial config loaded: {len(self._financial_config)} keys")
            else:
                logger.warning("⚠️  Financial config document not found")
                self._financial_config = {}
            
            # Load partners configuration
            partners_ref = self._db.collection("configuracion").document("aliados")
            partners_doc = partners_ref.get()
            
            if partners_doc.exists:
                self._partners_config = partners_doc.to_dict()
                logger.info(f"✅ Partners config loaded: {len(self._partners_config)} keys")
            else:
                logger.warning("⚠️  Partners config document not found")
                self._partners_config = {}
                
        except Exception as e:
            logger.error(f"❌ Error loading configurations: {str(e)}")
            # Initialize with empty dicts to prevent None errors
            self._financial_config = {}
            self._partners_config = {}
    
    def get_financial_config(self) -> Dict[str, Any]:
        """
        Get financial configuration.
        
        Returns:
            Dictionary containing financial configuration
        """
        return self._financial_config or {}
    
    def get_partners_config(self) -> Dict[str, Any]:
        """
        Get partners/entities configuration.
        
        Returns:
            Dictionary containing partners configuration
        """
        return self._partners_config or {}
    
    def refresh(self) -> None:
        """
        Refresh configurations from Firestore.
        
        Can be called to reload configurations without restarting the app.
        """
        logger.info("🔄 Refreshing configurations...")
        self.load_configurations()


# Global service instance
config_service = ConfigService()
