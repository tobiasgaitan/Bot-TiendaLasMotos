"""
Inventory Service
Hybrid search and budget calculator for motorcycles.
"""

import logging
from typing import List, Dict, Any, Optional
import asyncio

from app.services.catalog_service import catalog_service
from app.services.finance import MotorFinanciero

logger = logging.getLogger(__name__)

# Vertex AI Imports (Conditional)
try:
    import vertexai
    from vertexai.language_models import TextEmbeddingModel
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np
    VERTEX_AI_AVAILABLE = True
except ImportError:
    VERTEX_AI_AVAILABLE = False
    logger.warning("⚠️ Vertex AI or sklearn not found. Vector search will be disabled.")

class InventoryService:
    """
    Advanced inventory management with Semantic Search and Budget Calculation.
    """

    def __init__(self, config_loader=None):
        self._config_loader = config_loader
        self._embedding_model = None
        self._item_embeddings = {} # {id: embedding}
        self._initialized = False
        self._motor_financiero = None # Lazy init to avoid circular deps if any

    async def initialize(self, db=None):
        """Initialize models and cache embeddings."""
        if self._initialized:
            return

        # Init Motor Financiero (lightweight)
        if db:
            self._motor_financiero = MotorFinanciero(db, self._config_loader)
        
        # Init Vertex AI
        if VERTEX_AI_AVAILABLE:
            try:
                # Assuming project/location already set in environment or main
                # vertexai.init(project=..., location=...) 
                # We assume global init or already done in AI Brain
                self._embedding_model = TextEmbeddingModel.from_pretrained("text-embedding-004")
                logger.info("🧠 InventoryService: Embedding model loaded.")
                
                # Pre-compute catalog embeddings (Async if possible, but here we do sync for simplicity on startup)
                # In real prod, this should be cached/persisted. for <100 items, we can do it.
                await self._compute_catalog_embeddings()
                
            except Exception as e:
                logger.error(f"❌ InventoryService: Failed to init embeddings: {e}")
                self._embedding_model = None
        
        self._initialized = True

    async def _compute_catalog_embeddings(self):
        """Compute embeddings for all catalog descriptions."""
        items = catalog_service.get_all_items()
        if not items or not self._embedding_model:
            return

        logger.info(f"🧠 Computing embeddings for {len(items)} catalog items...")
        
        # Batch processing could be better, but doing one by one for simplicity/rate limits
        # Construct text representation: "Name Category Description"
        # We can run this in executor to not block if needed, but startup is ok.
        
        count = 0
        for item in items:
            item_id = item.get("id")
            text = f"{item.get('name', '')} {item.get('category', '')} {item.get('brand', '')} {item.get('description', '')}"
            
            try:
                # Vertex AI call
                embeddings = self._embedding_model.get_embeddings([text])
                if embeddings:
                    self._item_embeddings[item_id] = embeddings[0].values
                    count += 1
            except Exception as e:
                logger.warning(f"Failed embedding for {item_id}: {e}")
        
        logger.info(f"✅ Computed {count} embeddings.")

    def find_bikes_by_budget(self, max_monthly_quota: float) -> List[Dict[str, Any]]:
        """
        List motorcycles fitting a monthly budget.
        
        Assumptions:
        - Term: 36 months
        - Rate: Fintech Rate (Default ~2.22%)
        - Initial: $0 (To show what covers fully, or maybe we assume they have SOME initial?)
        * User spec: "use MotorFinanciero math in reverse".
        * We will assume $0 initial payment to find reachable bikes safely.
        """
        if not self._motor_financiero:
            # Fallback if not init with db, though ConfigLoader is enough for rates
            self._motor_financiero = MotorFinanciero(None, self._config_loader)

        # Get Rate
        rate = 2.22 # Default
        if self._config_loader:
             config = self._config_loader.get_financial_config()
             rate = config.get("tasa_nmv_fintech", 2.22)
        
        matches = []
        items = catalog_service.get_all_items()
        term = 36
        
        for item in items:
            price = float(item.get("price", 0))
            if price <= 0: 
                continue
                
            # Calculate quota with 0 initial
            plan = self._motor_financiero.calcular_cuota(precio=price, inicial=0, plazo_meses=term, tasa_mensual=rate)
            quota = plan.get("cuota_mensual", 999999999)
            
            if quota <= max_monthly_quota:
                matches.append({
                    "moto": item,
                    "monthly_payment": quota,
                    "term": term,
                    "gap": max_monthly_quota - quota
                })
        
        # Sort by gap (closest to budget first)
        matches.sort(key=lambda x: x["gap"])
        return matches

    def search_semantic(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Semantic search for motorcycles."""
        if not VERTEX_AI_AVAILABLE or not self._embedding_model or not self._item_embeddings:
            logger.warning("⚠️ Semantic search unavailable. Falling back to simple keyword.")
            return self._fallback_search(query)

        try:
            # Embed query
            query_embedding = self._embedding_model.get_embeddings([query])[0].values
            
            # Simple Cosine Similarity
            scores = []
            for item_id, emb in self._item_embeddings.items():
                # Cosine Sim: dot(A, B) / (norm(A)*norm(B))
                # Vertex embeddings are roughly normalized usually? Let's assume standard calculation
                score = np.dot(query_embedding, emb) / (np.linalg.norm(query_embedding) * np.linalg.norm(emb))
                scores.append((item_id, score))
            
            # Sort DESC
            scores.sort(key=lambda x: x[1], reverse=True)
            
            # Retrieve items
            results = []
            for item_id, score in scores[:limit]:
                item = catalog_service.get_by_id(item_id)
                if item:
                    item_copy = item.copy()
                    item_copy["similarity_score"] = score
                    results.append(item_copy)
                    
            return results

        except Exception as e:
            logger.error(f"❌ Semantic search error: {e}")
            return self._fallback_search(query)

    def _fallback_search(self, query: str) -> List[Dict[str, Any]]:
        """Simple keyword search."""
        items = catalog_service.get_all_items()
        q = query.lower()
        results = [i for i in items if q in i.get("name", "").lower() or q in i.get("description", "").lower()]
        return results[:3]

# Global Instance
inventory_service = InventoryService()
