"""
v8.0.0 Dynamic Configuration Loader
Loads and manages dynamic configuration from Firestore for:
- Juan Pablo personality and system instructions
- Routing rules for message classification
- Catalog configuration
"""

import logging
import threading
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
        self._juan_pablo_personality: Optional[Dict[str, Any]] = None
        self._routing_rules: Optional[Dict[str, Any]] = None
        self._catalog_config: Optional[Dict[str, Any]] = None
        self._last_loaded: Optional[datetime] = None
        # [BOT-BUILD-REFACTOR-03-05-RESIDUAL]
        # WHY: RLock de escritura. Serializa load_all()/refresh() entre hilos
        # (el startup diferido y el refresh admin vía asyncio.to_thread comparten
        # el executor por defecto). NUNCA se adquiere en los getters (vía rápida).
        self._write_lock = threading.RLock()
        self._initialized = True
    
    def load_all(self) -> None:
        """
        Load all v8.0.0 configuration documents from Firestore.
        
        Loads:
            - configuracion/juan_pablo_personality: AI personality configuration
            - configuracion/routing_rules: Message routing keywords
            - configuracion/catalog_config: Product catalog settings
        """
        # WHY RLock + assign-at-end: los 3 documentos se acumulan en variables
        # locales y se publican en un único commit final. Un lector concurrente
        # ve el snapshot previo ÍNTEGRO o el nuevo ÍNTEGRO; jamás una mezcla
        # rasgada ni defaults transitorios (BOT-BUILD-REFACTOR-03-05-RESIDUAL).
        with self._write_lock:
            try:
                logger.info("🧠 Loading v8.0.0 dynamic configuration...")

                # Load Juan Pablo personality configuration
                juan_pablo_personality = self._load_juan_pablo_personality()

                # Load routing rules
                routing_rules = self._load_routing_rules()

                # Load catalog configuration
                catalog_config = self._load_catalog_config()

                # ATOMIC COMMIT (cada asignación es GIL-atómica, sin I/O entre ellas)
                self._juan_pablo_personality = juan_pablo_personality
                self._routing_rules = routing_rules
                self._catalog_config = catalog_config
                self._last_loaded = datetime.now()
                logger.info("✅ v8.0.0 configuration loaded successfully")

            except Exception as e:
                logger.error(f"❌ Error loading v8.0.0 configuration: {str(e)}")
                # Initialize with safe defaults to prevent crashes
                self._initialize_defaults()
    
    def _load_juan_pablo_personality(self) -> Dict[str, Any]:
        """Load Juan Pablo AI personality configuration from Firestore."""
        try:
            doc_ref = self._db.collection("configuracion").document("juan_pablo_personality")
            doc = doc_ref.get()

            if doc.exists:
                personality = doc.to_dict()
                logger.info(f"✅ Juan Pablo personality loaded (model: {personality.get('model_version')})")
                return personality
            else:
                logger.warning("⚠️  Juan Pablo personality document not found, using defaults")
                return self._get_default_juan_pablo_personality()

        except Exception as e:
            logger.error(f"❌ Error loading Juan Pablo personality: {str(e)}")
            return self._get_default_juan_pablo_personality()
    
    def _load_routing_rules(self) -> Dict[str, Any]:
        """Load message routing rules from Firestore."""
        try:
            doc_ref = self._db.collection("configuracion").document("routing_rules")
            doc = doc_ref.get()

            if doc.exists:
                routing_rules = doc.to_dict()
                logger.info(f"✅ Routing rules loaded ({len(routing_rules.get('financial_keywords', []))} financial keywords)")
                return routing_rules
            else:
                logger.warning("⚠️  Routing rules document not found, using defaults")
                return self._get_default_routing_rules()

        except Exception as e:
            logger.error(f"❌ Error loading routing rules: {str(e)}")
            return self._get_default_routing_rules()
    
    def _load_catalog_config(self) -> Dict[str, Any]:
        """Load catalog configuration from Firestore."""
        try:
            doc_ref = self._db.collection("configuracion").document("catalog_config")
            doc = doc_ref.get()

            if doc.exists:
                catalog_config = doc.to_dict()
                logger.info(f"✅ Catalog config loaded ({len(catalog_config.get('items', []))} items)")
                return catalog_config
            else:
                logger.warning("⚠️  Catalog config document not found, using defaults")
                return self._get_default_catalog_config()

        except Exception as e:
            logger.error(f"❌ Error loading catalog config: {str(e)}")
            return self._get_default_catalog_config()
            

    
    def _initialize_defaults(self) -> None:
        """Initialize all configurations with safe defaults."""
        self._juan_pablo_personality = self._get_default_juan_pablo_personality()
        self._routing_rules = self._get_default_routing_rules()
        self._catalog_config = self._get_default_catalog_config()
    
    # ==================== Getters ====================
    
    def get_juan_pablo_personality(self) -> Dict[str, Any]:
        """
        Get Juan Pablo AI personality configuration.
        
        Returns:
            Dictionary containing personality settings including:
            - name: AI assistant name
            - role: Professional role description
            - tone: Communication tone
            - system_instruction: Full system prompt
            - model_version: Gemini model version to use
            - catalog_knowledge: Array of products Juan Pablo knows about
        """
        return self._juan_pablo_personality or self._get_default_juan_pablo_personality()
    
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

    def get_partners_config(self) -> Dict[str, Any]:
        """
        Get partners configuration (e.g. links) via ConfigService.
        
        Returns:
            Dictionary containing partners configuration
        """
        from app.services.config_service import config_service
        config = config_service.get_partners_config()
        return config if config else self._get_default_partners_config()
    
    def refresh(self) -> None:
        """
        Refresh all configurations from Firestore.
        
        Can be called to reload configurations without restarting the app.
        Useful for hot-reload of personality or routing rules.
        """
        logger.info("🔄 Refreshing v8.0.0 configurations...")
        self.load_all()
    
    # ==================== Default Configurations ====================
    
    @staticmethod
    def _get_default_juan_pablo_personality() -> Dict[str, Any]:
        """
        Get default Juan Pablo personality configuration.
        
        This is a fail-safe fallback if Firestore is unavailable.
        """
        from app.core.prompts import JUAN_PABLO_SYSTEM_INSTRUCTION
        return {
            "name": "Juan Pablo",
            "role": "Asesor experto en financiación y venta de motocicletas",
            "tone": "educado, profesional y empático",
            "model_version": "gemini-3.0-flash",
            "system_instruction": JUAN_PABLO_SYSTEM_INSTRUCTION,
            "catalog_knowledge": [] # CLEANED HALLUCINATIONS
        }
    
    @staticmethod
    def _get_default_routing_rules() -> Dict[str, Any]:
        """
        Get default routing rules.
        
        These keywords determine which service handles the message.
        """
        return {
            "financial_keywords": ["simular", "credito", "financiar", "cuota", "inicial"],
            "sales_keywords": ["precio", "comprar", "moto", "catalogo", "info"],
            "default_handler": "cerebro_ia"
        }
    
    @staticmethod
    def _get_default_catalog_config() -> Dict[str, Any]:
        """Get default catalog configuration."""
        return {
            "items": [],
            "last_updated": None,
            "auto_sync_enabled": False,
            "category_aliases": {}, # Fallback to prevent crash if field is missing in Firestore
            "competitor_brands": ["boxer", "nkd", "pulsar", "yamaha", "honda", "suzuki", "akt"]
        }
        
    @staticmethod
    def _get_default_partners_config() -> Dict[str, Any]:
        """Get default partners configuration."""
        return {
            "link_banco_bogota": "https://digital.bancodebogota.com/",
            "link_crediorbe": "https://crediorbe.com/",
            "link_brilla": "https://brilladegasesdeoccidente.com/",
            "privacy_policy_url": "https://tiendalasmotos.com/politica-de-privacidad"
        }


# Singleton instance is managed internally by the class
# Access via: config_loader = ConfigLoader(db) on first call
# Then: config_loader = ConfigLoader() on subsequent calls
