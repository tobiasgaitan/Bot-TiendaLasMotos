"""
V6.0 Dynamic Configuration Loader
Loads and manages dynamic configuration from Firestore for:
- Sebas personality and system instructions
- Routing rules for message classification
- Catalog configuration
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from google.cloud import firestore

logger = logging.getLogger(__name__)


class ConfigLoader:
    """
    Singleton service for managing dynamic configuration from Firestore.
    
    Loads configuration at startup and provides methods to access
    personality, routing rules, and catalog settings. Supports
    hot-reload via refresh() method.
    
    Uses Singleton pattern to ensure only one instance exists.
    """
    
    _instance: Optional['ConfigLoader'] = None
    _initialized: bool = False
    
    def __new__(cls, db: Optional[firestore.Client] = None):
        """
        Singleton pattern implementation.
        
        Args:
            db: Firestore client (required on first instantiation)
        
        Returns:
            The singleton instance of ConfigLoader
        """
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, db: Optional[firestore.Client] = None):
        """
        Initialize the configuration loader (only once).
        
        Args:
            db: Initialized Firestore client (required on first call)
        """
        # Prevent re-initialization
        if self._initialized:
            return
        
        if db is None:
            raise ValueError("Firestore client is required for first initialization")
        
        self._db = db
        self._sebas_personality: Optional[Dict[str, Any]] = None
        self._routing_rules: Optional[Dict[str, Any]] = None
        self._catalog_config: Optional[Dict[str, Any]] = None
        self._last_loaded: Optional[datetime] = None
        self._initialized = True
    
    def load_all(self) -> None:
        """
        Load all V6.0 configuration documents from Firestore.
        
        Loads:
            - configuracion/sebas_personality: AI personality configuration
            - configuracion/routing_rules: Message routing keywords
            - configuracion/catalog_config: Product catalog settings
        """
        try:
            logger.info("🧠 Loading V6.0 dynamic configuration...")
            
            # Load Sebas personality configuration
            self._load_sebas_personality()
            
            # Load routing rules
            self._load_routing_rules()
            
            # Load catalog configuration
            self._load_catalog_config()
            
            self._last_loaded = datetime.now()
            logger.info("✅ V6.0 configuration loaded successfully")
            
        except Exception as e:
            logger.error(f"❌ Error loading V6.0 configuration: {str(e)}")
            # Initialize with safe defaults to prevent crashes
            self._initialize_defaults()
    
    def _load_sebas_personality(self) -> None:
        """Load Sebas AI personality configuration from Firestore."""
        try:
            doc_ref = self._db.collection("configuracion").document("sebas_personality")
            doc = doc_ref.get()
            
            if doc.exists:
                self._sebas_personality = doc.to_dict()
                logger.info(f"✅ Sebas personality loaded (model: {self._sebas_personality.get('model_version')})")
            else:
                logger.warning("⚠️  Sebas personality document not found, using defaults")
                self._sebas_personality = self._get_default_sebas_personality()
                
        except Exception as e:
            logger.error(f"❌ Error loading Sebas personality: {str(e)}")
            self._sebas_personality = self._get_default_sebas_personality()
    
    def _load_routing_rules(self) -> None:
        """Load message routing rules from Firestore."""
        try:
            doc_ref = self._db.collection("configuracion").document("routing_rules")
            doc = doc_ref.get()
            
            if doc.exists:
                self._routing_rules = doc.to_dict()
                logger.info(f"✅ Routing rules loaded ({len(self._routing_rules.get('financial_keywords', []))} financial keywords)")
            else:
                logger.warning("⚠️  Routing rules document not found, using defaults")
                self._routing_rules = self._get_default_routing_rules()
                
        except Exception as e:
            logger.error(f"❌ Error loading routing rules: {str(e)}")
            self._routing_rules = self._get_default_routing_rules()
    
    def _load_catalog_config(self) -> None:
        """Load catalog configuration from Firestore."""
        try:
            doc_ref = self._db.collection("configuracion").document("catalog_config")
            doc = doc_ref.get()
            
            if doc.exists:
                self._catalog_config = doc.to_dict()
                logger.info(f"✅ Catalog config loaded ({len(self._catalog_config.get('items', []))} items)")
            else:
                logger.warning("⚠️  Catalog config document not found, using defaults")
                self._catalog_config = self._get_default_catalog_config()
                
        except Exception as e:
            logger.error(f"❌ Error loading catalog config: {str(e)}")
            self._catalog_config = self._get_default_catalog_config()
    
    def _initialize_defaults(self) -> None:
        """Initialize all configurations with safe defaults."""
        self._sebas_personality = self._get_default_sebas_personality()
        self._routing_rules = self._get_default_routing_rules()
        self._catalog_config = self._get_default_catalog_config()
    
    # ==================== Getters ====================
    
    def get_sebas_personality(self) -> Dict[str, Any]:
        """
        Get Sebas AI personality configuration.
        
        Returns:
            Dictionary containing personality settings including:
            - name: AI assistant name
            - role: Professional role description
            - tone: Communication tone
            - system_instruction: Full system prompt
            - model_version: Gemini model version to use
            - catalog_knowledge: Array of products Sebas knows about
        """
        return self._sebas_personality or self._get_default_sebas_personality()
    
    def get_routing_rules(self) -> Dict[str, Any]:
        """
        Get message routing rules.
        
        Returns:
            Dictionary containing:
            - financial_keywords: List of keywords for financial routing
            - sales_keywords: List of keywords for sales routing
            - default_handler: Default service to use (cerebro_ia)
        """
        return self._routing_rules or self._get_default_routing_rules()
    
    def get_catalog_config(self) -> Dict[str, Any]:
        """
        Get catalog configuration.
        
        Returns:
            Dictionary containing catalog settings and items
        """
        return self._catalog_config or self._get_default_catalog_config()
    
    def refresh(self) -> None:
        """
        Refresh all configurations from Firestore.
        
        Can be called to reload configurations without restarting the app.
        Useful for hot-reload of personality or routing rules.
        """
        logger.info("🔄 Refreshing V6.0 configurations...")
        self.load_all()
    
    # ==================== Default Configurations ====================
    
    @staticmethod
    def _get_default_sebas_personality() -> Dict[str, Any]:
        """
        Get default Sebas personality configuration.
        
        This is a fail-safe fallback if Firestore is unavailable.
        """
        from app.core.prompts import JUAN_PABLO_SYSTEM_INSTRUCTION
        return {
            "name": "Juan Pablo",
            "role": "Asesor experto en financiación y venta de motocicletas",
            "tone": "educado, profesional y empático",
            "model_version": "gemini-2.5-flash",
            "system_instruction": JUAN_PABLO_SYSTEM_INSTRUCTION,
            "catalog_knowledge": [
                "NKD 125",
                "Sport 100",
                "Victory Black",
                "MRX 150"
            ]
        }
    
    @staticmethod
    def _get_default_routing_rules() -> Dict[str, Any]:
        """
        Get default routing rules.
        
        These keywords determine which service handles the message.
        """
        return {
            "financial_keywords": [
                "simular",
                "simulación",
                "cuota",
                "crédito",
                "credito",
                "financiar",
                "financiación",
                "inicial",
                "mensual"
            ],
            "sales_keywords": [
                "precio",
                "busco",
                "nkd",
                "comprar",
                "vender",
                "disponible",
                "catálogo",
                "catalogo",
                "motos"
            ],
            "default_handler": "cerebro_ia"
        }
    
    @staticmethod
    def _get_default_catalog_config() -> Dict[str, Any]:
        """Get default catalog configuration."""
        return {
            "items": [],
            "last_updated": None,
            "auto_sync_enabled": False
        }


# Singleton instance is managed internally by the class
# Access via: config_loader = ConfigLoader(db) on first call
# Then: config_loader = ConfigLoader() on subsequent calls
