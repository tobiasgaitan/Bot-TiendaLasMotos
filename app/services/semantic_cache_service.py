"""
Semantic Cache Service
Pure Python implementation for caching semantic query results to mitigate latency.
"""

import logging
import re
import unicodedata
from typing import Dict, Optional, Tuple, List, Set
from collections import Counter

logger = logging.getLogger(__name__)

class SemanticCacheService:
    """
    Provides an in-memory cache for catalog search queries.
    Uses pure Python token-based overlap similarity (Jaccard / TF-IDF light) 
    to evaluate semantic equivalence without external libraries.
    """

    def __init__(self):
        # Dictionary storing normalized query -> Markdown string response
        self._cache: Dict[str, str] = {}
        logger.info("🧠 SemanticCacheService initialized (In-Memory)")

    def _normalize_text(self, text: str) -> str:
        """Lowercases, removes accents, and non-alphanumeric chars."""
        if not text:
            return ""
        text = str(text).lower()
        text = ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
        text = re.sub(r'[^a-z0-9\s]', ' ', text)
        return text

    def _tokenize(self, text: str) -> Set[str]:
        """Extracts unique tokens excluding basic stop words."""
        norm_text = self._normalize_text(text)
        tokens = norm_text.split()
        stop_words = {"una", "un", "moto", "motos", "busco", "la", "el", "de", "las", "los", "con", "en", "para", "y", "o"}
        return set(t for t in tokens if t not in stop_words)

    def _calculate_similarity(self, query1: str, query2: str) -> float:
        """
        Calculates similarity using difflib.SequenceMatcher.
        Provides a solid, fast pure-Python semantic overlap score.
        """
        import difflib
        norm_q1 = self._normalize_text(query1).strip()
        norm_q2 = self._normalize_text(query2).strip()
        
        if not norm_q1 or not norm_q2:
            return 0.0

        return difflib.SequenceMatcher(None, norm_q1, norm_q2).ratio()

    def get(self, query: str, threshold: float = 0.85) -> Tuple[Optional[str], float]:
        """
        Retrieves a cached markdown response if the semantic similarity > threshold.
        """
        if not query or not self._cache:
            return None, 0.0

        best_score = 0.0
        best_match_key = None

        # Check exact match first for O(1) performance
        norm_query = self._normalize_text(query).strip()
        if norm_query in self._cache:
            return self._cache[norm_query], 1.0

        for cached_query, response in self._cache.items():
            score = self._calculate_similarity(query, cached_query)
            if score > best_score:
                best_score = score
                best_match_key = cached_query

        if best_score >= threshold and best_match_key is not None:
            return self._cache[best_match_key], best_score

        return None, best_score

    def set(self, query: str, response: str) -> None:
        """
        Stores the Markdown response in the cache.
        """
        if not query or not response:
            return
            
        norm_query = self._normalize_text(query).strip()
        if not norm_query:
            return
            
        self._cache[norm_query] = response
        logger.debug(f"💾 Saved query '{query}' to semantic cache.")

    def clear(self) -> None:
        """Clears the cache."""
        self._cache.clear()
        logger.info("🧹 Semantic cache cleared.")
