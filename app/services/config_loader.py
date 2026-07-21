"""
Dynamic Config Loader Service (Fase 1)
Single Source of Truth for Financial and Partner Configuration.
Implements in-memory caching with TTL (5 minutes) and robust fallbacks.
"""

import logging
import threading
import time
from typing import Dict, Any, Optional
from google.cloud import firestore

logger = logging.getLogger(__name__)

class FinanceConfigLoader:
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
        "tasa_nmv_fintech": 2.22,
        "fng_rate": 20.66,
        "life_insurance_mode": "fixed",
        "life_insurance_monthly": 15000,
        "default_down_payment_ratio": 0.10,
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
            cls._instance = super(FinanceConfigLoader, cls).__new__(cls)
        return cls._instance

    def __init__(self, db: Optional[firestore.Client] = None):
        if self._initialized:
            return
            
        if db is None:
            logger.warning("Construction of FinanceConfigLoader without DB client. Waiting for initialize.")
            self._db = None
        else:
            self._db = db
            
        self._financial_cache: Optional[Dict[str, Any]] = None
        self._partners_cache: Optional[Dict[str, Any]] = None
        self._last_fetch_time = 0.0
        # [BOT-BUILD-REFACTOR-03-05-RESIDUAL]
        # WHY: RLock de escritura. _check_cache() refresca inline en hilos de
        # request al expirar el TTL; serializa esas mutaciones. NUNCA se adquiere
        # en los getters (vía rápida de lectura).
        self._write_lock = threading.RLock()
        self._initialized = True
        logger.info("🔧 FinanceConfigLoader initialized (Service Layer)")

    def initialize(self, db: firestore.Client) -> None:
        """Late initialization of DB client."""
        self._db = db
        # Initial load attempt
        self._refresh_cache()

    def _refresh_cache(self) -> None:
        """Forces a refresh of the cache from Firestore."""
        if not self._db:
            logger.error("❌ FinanceConfigLoader: Cannot refresh, DB not initialized.")
            return

        # WHY RLock + assign-at-end: ambos documentos se acumulan en variables
        # locales y se publican en un único commit final. Un lector concurrente
        # ve el par previo ÍNTEGRO o el nuevo ÍNTEGRO; jamás una mezcla rasgada
        # (BOT-BUILD-REFACTOR-03-05-RESIDUAL).
        with self._write_lock:
            try:
                # 1. Financial Config
                fin_ref = self._db.collection("financial_config").document("general").collection("global_params").document("global_params")
                fin_doc = fin_ref.get()

                if fin_doc.exists:
                    financial_cache = fin_doc.to_dict()
                    logger.info(f"✅ Loaded Financial Config from Firestore: {financial_cache}")
                else:
                    logger.critical("🔥 CRITICAL: 'financial_config/.../global_params' not found! Using Hardcoded Defaults.")
                    financial_cache = self.DEFAULT_FINANCIAL.copy()

                # 2. Partners Config
                aliados_ref = self._db.collection("configuracion").document("aliados")
                aliados_doc = aliados_ref.get()

                if aliados_doc.exists:
                    partners_cache = aliados_doc.to_dict()
                    logger.info(f"✅ Loaded Partners Config from Firestore: {len(partners_cache)} items")
                else:
                    logger.critical("🔥 CRITICAL: 'configuracion/aliados' not found! Using Hardcoded Defaults.")
                    partners_cache = self.DEFAULT_PARTNERS.copy()

                # ATOMIC COMMIT (cada asignación es GIL-atómica, sin I/O entre ellas)
                self._financial_cache = financial_cache
                self._partners_cache = partners_cache
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
