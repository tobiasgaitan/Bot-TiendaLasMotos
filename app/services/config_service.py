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
            
            # Load partners configuration (Dynamic hydration CP-002)
            self._partners_config = {}
            financieras_ref = self._db.collection("financial_config").document("general").collection("financieras")
            financieras_docs = financieras_ref.stream()
            
            for doc in financieras_docs:
                doc_data = doc.to_dict()
                doc_id = doc.id
                
                # Consolidate standard link_keys for evaluate_profile
                link = doc_data.get("link_url") or doc_data.get("link") or doc_data.get("url") or "#"
                self._partners_config[f"link_{doc_id}"] = link
                
                # Merge all other keys prefixing them to avoid collisions, preserving retrocompatibility
                for k, v in doc_data.items():
                    if k not in ["rows", "matrix", "tasas"]: # Skip heavy matrix data
                        self._partners_config[f"{doc_id}_{k}"] = v
                        # Keep flat key if it matches exactly (e.g., if doc already contains 'link_brilla')
                        if k.startswith("link_"):
                            self._partners_config[k] = v

            if self._partners_config:
                logger.info(f"✅ Partners config loaded from financieras: {len(self._partners_config)} keys")
            else:
                logger.warning("⚠️  Partners config is empty after loading from financieras")
                

        except Exception as e:
            logger.error(f"❌ Error loading configurations: {str(e)}")
            self._financial_config = self.DEFAULT_FINANCIAL.copy()
            self._partners_config = {}

    def _normalize_entity_id(self, entity_id: str) -> str:
        """
        Normalize entity ID to match Firestore document IDs.
        """
        if not entity_id:
            return "crediorbe"
            
        normalized = str(entity_id).lower().replace("banco_de_bogotá", "banco_bogota").replace("brilla_de_gases", "brilla").replace(" ", "_")
        
        if "brilla" in normalized:
            return "brilla"
        elif "bogota" in normalized:
            return "banco_bogota"
        elif "crediorbe" in normalized:
            return "crediorbe"
            
        return normalized

    def get_financial_matrix(self, entity_id: str) -> List[Dict[str, Any]]:
        """
        Get the factor matrix for a specific financial entity.
        """
        try:
            normalized_id = self._normalize_entity_id(entity_id)
            
            matrix_ref = self._db.collection("financial_config").document("general").collection("financieras").document(normalized_id)
            matrix_doc = matrix_ref.get()
            
            if matrix_doc.exists:
                data = matrix_doc.to_dict()
                return data.get("rows", [])
            
            logger.warning(f"⚠️  Matrix not found for {normalized_id}")
            return []
            
        except Exception as e:
            logger.error(f"❌ Error getting financial matrix for {entity_id}: {str(e)}")
            err_msg = str(e).lower()
            if "nonetype" in err_msg or "collection" in err_msg or "grpc" in err_msg or isinstance(e, AttributeError):
                raise
            return []

    def get_financial_entity_config(self, entity_id: str) -> Dict[str, Any]:
        """
        Get the full configuration document for a specific financial entity.
        """
        try:
            normalized_id = self._normalize_entity_id(entity_id)
            
            doc_ref = self._db.collection("financial_config").document("general").collection("financieras").document(normalized_id)
            doc = doc_ref.get()
            
            if doc.exists:
                return doc.to_dict()
                
            logger.warning(f"⚠️  Configuration not found for {normalized_id}")
            return {}
            
        except Exception as e:
            logger.error(f"❌ Error getting entity config for {entity_id}: {str(e)}")
            err_msg = str(e).lower()
            if "nonetype" in err_msg or "collection" in err_msg or "grpc" in err_msg or isinstance(e, AttributeError):
                raise
            return {}
    
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

    def get_registration_cost(self, cc: Optional[Union[int, float]] = None, category: Optional[str] = None) -> int:
        """
        Retrieve registration and SOAT cost from financial configuration.
        
        Mandato v6.8.0 CP-002: 
        - Access is O(1) from memory-cached _financial_config.
        - Strict No-Assumption: Returns 0 if no match is found.
        
        Args:
            cc: Cylinder capacity in cc
            category: Motorcycle category (e.g. ELECTRICA)
            
        Returns:
            int: The registrationCredit amount or 0 if matching fails.
        """
        try:
            if not self._financial_config:
                logger.error("❌ Global params not loaded in memory")
                return 0
                
            rows = self._financial_config.get("rows", [])
            if not rows:
                logger.error("❌ No registration rows found in financial_config")
                return 0
                
            # Normalize inputs
            norm_category = str(category or "").upper().strip()
            
            # 1. Match by specific category (Special cases: ELECTRICA, MOTOCARRO)
            for row in rows:
                row_cat = str(row.get("category") or "").upper().strip()
                if row_cat and norm_category == row_cat:
                    cost = int(row.get("registrationCredit", 0))
                    logger.debug(f"✅ Match by Category: {norm_category} -> ${cost}")
                    return cost
            
            # 2. Match by Cylinder Capacity (CC)
            if cc is not None:
                import math
                cc_val = math.floor(float(cc))
                for row in rows:
                    min_cc = int(row.get("minCC", 0))
                    max_cc = int(row.get("maxCC", 99999))
                    
                    if min_cc <= cc_val <= max_cc:
                        cost = int(row.get("registrationCredit", 0))
                        logger.debug(f"✅ Match by CC Range: {min_cc}-{max_cc} ({cc_val}cc) -> ${cost}")
                        return cost
            
            # 3. Fallback: Log Error (Violation to No-Assumption Policy)
            logger.error(f"⚠️ [MANDATO v6.8.0] Fallo de Match: Falta CC o Categoría para calcular costo de trámite (CC: {cc}, Cat: {category})")
            return 0
            
        except Exception as e:
            logger.error(f"❌ Error indexing registration matrix: {str(e)}")
            return 0
    
    def get_catalog_aliases(self) -> Dict[str, List[str]]:
        """
        Get catalog category aliases (synonyms) for System Prompt injection.

        WHY (BOT-BRAIN-ALIGNMENT-099): The category_aliases dict exists in Firestore
        (configuracion/catalog_config) and is used by CatalogService for search indexing,
        but the LLM has no awareness of regional synonyms (e.g. "señoritera" → scooter).
        This method exposes the aliases so ai_brain.py can inject them into the prompt.

        Firestore stores indexed dicts: {"Semiautomatica": {"0": "Señoritera"}}.
        This method flattens them into: {"Semiautomatica": ["Señoritera"]}.

        Returns:
            Dict mapping category names to lists of synonym strings.
        """
        try:
            from app.core.config_loader import ConfigLoader
            config_loader = ConfigLoader()
            catalog_config = config_loader.get_catalog_config()
            raw_aliases = catalog_config.get("category_aliases", {})

            if not raw_aliases or not isinstance(raw_aliases, dict):
                return {}

            # Flatten Firestore indexed-dict format to proper lists
            flattened: Dict[str, List[str]] = {}
            for category, synonyms in raw_aliases.items():
                if isinstance(synonyms, dict):
                    # Firestore indexed dict: {"0": "Señoritera", "1": "Automatica"}
                    values = [str(v).strip() for v in synonyms.values() if v]
                elif isinstance(synonyms, list):
                    # Already a proper list
                    values = [str(v).strip() for v in synonyms if v]
                elif isinstance(synonyms, str):
                    # Single string value
                    values = [synonyms.strip()] if synonyms.strip() else []
                else:
                    logger.warning(
                        f"⚠️ [CATALOG_ALIASES] Unexpected type for category '{category}': "
                        f"{type(synonyms).__name__}. Skipping."
                    )
                    continue

                if values:
                    flattened[str(category).strip()] = values

            logger.info(f"📖 [CATALOG_ALIASES] Loaded {len(flattened)} categories with synonyms")
            return flattened
        except Exception as e:
            logger.warning(f"⚠️ [CATALOG_ALIASES] Failed to load aliases: {e}")
            return {}

    def refresh(self) -> None:
        """
        Refresh configurations from Firestore.
        
        Can be called to reload configurations without restarting the app.
        """
        logger.info("🔄 Refreshing configurations...")
        self.load_configurations()


# Global service instance
config_service = ConfigService()
