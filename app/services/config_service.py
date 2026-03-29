"""
Configuration Service
Loads and manages Firestore configuration documents in memory.
Provides fast access to financial and partner configuration.
"""

import logging
from typing import Dict, Any, Optional, List, Union

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
    
    # Defaults (Fallbacks) - JSON Voorhees Contract
    # [SSOT] All values must align with 'financial_config/general/global_params/global_params'
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
            - financial_config/general/global_params/global_params: Certified Route
            - configuracion/aliados: Partner/entity configuration
        """
        try:
            logger.info("📋 Loading configuration from Firestore...")
            
            # Load financial configuration (SSOT)
            financial_ref = self._db.collection("financial_config").document("general").collection("global_params").document("global_params")
            financial_doc = financial_ref.get()
            
            if financial_doc.exists:
                self._financial_config = financial_doc.to_dict()
                logger.info(f"✅ Financial config loaded from Certified Route: {len(self._financial_config)} keys")
            else:
                logger.critical("🔥 CRITICAL: 'financial_config/.../global_params' not found! Using Hardcoded Defaults.")
                self._financial_config = self.DEFAULT_FINANCIAL.copy()
            
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
            self._financial_config = self.DEFAULT_FINANCIAL.copy()
            self._partners_config = {}

    def get_financial_matrix(self, entity_id: str) -> List[Dict[str, Any]]:
        """
        Get the factor matrix for a specific financial entity.
        
        Args:
            entity_id: ID of the entity (crediorbe, brilla, banco_bogota)
            
        Returns:
            List of rows in the matrix
        """
        try:
            # v1.3.1: Try requested path 'configuracion/simulador_web' first (future-proof)
            # Defaulting to the existing 'financial_config' path which we confirmed has the data.
            # Normalized entity_id to match Firestore (e.g., 'crediorbe', 'brilla', 'banco_bogota')
            normalized_id = entity_id.lower().replace("banco_de_bogotá", "banco_bogota").replace("brilla_de_gases", "brilla").replace(" ", "_")
            
            # Additional safety for 'brilla' variations
            if "brilla" in normalized_id:
                normalized_id = "brilla"
            elif "bogota" in normalized_id:
                normalized_id = "banco_bogota"
            elif "crediorbe" in normalized_id:
                normalized_id = "crediorbe"
            
            # 1. Primary path: financial_config/general/financieras/{entity}
            matrix_ref = self._db.collection("financial_config").document("general").collection("financieras").document(normalized_id)
            matrix_doc = matrix_ref.get()
            
            if matrix_doc.exists:
                data = matrix_doc.to_dict()
                return data.get("rows", [])
            
            logger.warning(f"⚠️  Matrix not found for {normalized_id} in primary path.")
            return []
            
        except Exception as e:
            logger.error(f"❌ Error getting financial matrix for {entity_id}: {str(e)}")
            return []
    
    def get_financial_config(self) -> Dict[str, Any]:
        """
        Get financial configuration.
        """
        return self._financial_config or self.DEFAULT_FINANCIAL.copy()
    
    def get_partners_config(self) -> Dict[str, Any]:
        """
        Get partners/entities configuration.
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
