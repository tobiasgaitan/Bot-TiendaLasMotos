"""
Dynamic Config Loader Service (Fase 1)
Single Source of Truth for Financial and Partner Configuration.
Implements in-memory caching with TTL (5 minutes) and robust fallbacks.
"""

import logging
import time
from typing import Dict, Any, Optional
from google.cloud import firestore

logger = logging.getLogger(__name__)

class ConfigLoader:
    """
    Service to load and cache configuration from Firestore.
    Follows Singleton pattern for shared state.
    """
    
    _instance = None
    _initialized = False
    
    # Cache Configuration
    CACHE_TTL = 300  # 5 minutes in seconds
    
    # Defaults (Fallbacks)
    DEFAULT_FINANCIAL = {
        "tasa_nmv_banco": 1.87,
        "tasa_nmv_fintech": 2.22, # Slightly bumped per spec if failing
        "porcentaje_aval": 5.0,
        "seguro_vida_base": 2500,
        "score_min_banco": 700,
        "score_min_fintech": 400
    }
    
    DEFAULT_PARTNERS = {
        "link_banco_bogota": "https://digital.bancodebogota.com/",
        "link_crediorbe": "https://crediorbe.com/",
        "link_brilla": "https://brilladegasesdeoccidente.com/"
    }

    def __new__(cls, db: Optional[firestore.Client] = None):
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
        return cls._instance

    def __init__(self, db: Optional[firestore.Client] = None):
        if self._initialized:
            return
            
        if db is None:
            logger.warning("Construction of ConfigLoader without DB client. Waiting for initialize.")
            self._db = None
        else:
            self._db = db
            
        self._financial_cache: Optional[Dict[str, Any]] = None
        self._partners_cache: Optional[Dict[str, Any]] = None
        self._last_fetch_time = 0.0
        self._initialized = True
        logger.info("🔧 ConfigLoader initialized (Service Layer)")

    def initialize(self, db: firestore.Client) -> None:
        """Late initialization of DB client."""
        self._db = db
        # Initial load attempt
        self._refresh_cache()

    def _refresh_cache(self) -> None:
        """Forces a refresh of the cache from Firestore."""
        if not self._db:
            logger.error("❌ ConfigLoader: Cannot refresh, DB not initialized.")
            return

        try:
            # 1. Financial Config
            fin_ref = self._db.collection("configuracion").document("financiera")
            fin_doc = fin_ref.get()
            
            if fin_doc.exists:
                self._financial_cache = fin_doc.to_dict()
                logger.info(f"✅ Loaded Financial Config from Firestore: {self._financial_cache}")
            else:
                logger.critical("🔥 CRITICAL: 'configuracion/financiera' not found! Using Hardcoded Defaults.")
                self._financial_cache = self.DEFAULT_FINANCIAL.copy()

            # 2. Partners Config
            aliados_ref = self._db.collection("configuracion").document("aliados")
            aliados_doc = aliados_ref.get()
            
            if aliados_doc.exists:
                self._partners_cache = aliados_doc.to_dict()
                logger.info(f"✅ Loaded Partners Config from Firestore: {len(self._partners_cache)} items")
            else:
                logger.critical("🔥 CRITICAL: 'configuracion/aliados' not found! Using Hardcoded Defaults.")
                self._partners_cache = self.DEFAULT_PARTNERS.copy()

            self._last_fetch_time = time.time()
            
        except Exception as e:
            logger.critical(f"🔥 CRITICAL: Error refreshing config: {e}. using defaults.")
            # Ensure we have something
            if not self._financial_cache:
                self._financial_cache = self.DEFAULT_FINANCIAL.copy()
            if not self._partners_cache:
                self._partners_cache = self.DEFAULT_PARTNERS.copy()

    def _check_cache(self) -> None:
        """Checks if cache is valid, otherwise refreshes."""
        current_time = time.time()
        is_expired = (current_time - self._last_fetch_time) > self.CACHE_TTL
        
        if is_expired or self._financial_cache is None:
            logger.debug("🔄 Cache expired or empty. Refreshing...")
            self._refresh_cache()

    def get_financial_config(self) -> Dict[str, Any]:
        """Returns financial configuration (Rates, Scores, etc)."""
        self._check_cache()
        return self._financial_cache or self.DEFAULT_FINANCIAL

    def get_partners_config(self) -> Dict[str, Any]:
        """Returns partners configuration (Links)."""
        self._check_cache()
        return self._partners_cache or self.DEFAULT_PARTNERS
