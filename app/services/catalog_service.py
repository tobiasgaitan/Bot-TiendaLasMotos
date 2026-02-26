"""
Catalog Service
Manages motorcycle catalog from Firestore.
Provides in-memory access to catalog items with category filtering.
"""

import logging
from typing import List, Dict, Any, Optional, Union

from google.cloud import firestore

logger = logging.getLogger(__name__)


class CatalogService:
    """
    Service for managing motorcycle catalog from Firestore.
    
    Loads catalog items from the 'catalogo' collection (Spanish fields)
    and maps them to the internal English model.
    """
    
    def __init__(self):
        """Initialize the catalog service with empty state."""
        self._items: List[Dict[str, Any]] = []
        self._items_by_id: Dict[str, Dict[str, Any]] = {}
        self._items_by_category: Dict[str, List[Dict[str, Any]]] = {}
        self._db: Optional[firestore.Client] = None
    
    def initialize(self, db: firestore.Client) -> None:
        """
        Initialize the service with Firestore client and load catalog.
        
        Args:
            db: Initialized Firestore client
        """
        self._db = db
        self.load_catalog()
    
    def load_catalog(self) -> None:
        """
        Load catalog items from Firestore 'catalogo' collection into memory.
        
        Security Document: Maps Spanish fields (referencia, precio, categoria, link, ficha_tecnica) to English model.
        The 'link' field is critical to mitigate AI hallucinations and prevent spoofing of external URLs. 
        Only authorized URLs present in Firestore are explicitly passed to the LLM.
        """
        try:
            logger.info("🔍 Connecting to sub-collection: pagina/catalogo/items")
            
            if not self._db:
                logger.warning("⚠️ Firestore client not initialized in CatalogService")
                return

            # Query all items from sub-collection 'pagina/catalogo/items'
            items_ref = self._db.collection("pagina").document("catalogo").collection("items")
            items_docs = items_ref.stream()
            
            # Reset indexes
            self._items = []
            self._items_by_id = {}
            self._items_by_category = {}
            
            # Process each item
            for doc in items_docs:
                data = doc.to_dict()
                
                # --- Map Fields Explicitly (New Schema) ---
                
                # Brand: brand -> marca -> ""
                brand = data.get("brand") or data.get("marca") or ""
                
                # Reference: referencia -> nombre -> title -> doc.id
                ref = data.get("referencia") or data.get("nombre") or data.get("title") or doc.id
                
                # Name: Construct "Brand Reference" if brand exists, else just Reference
                name = f"{brand} {ref}".strip() if brand else str(ref).strip()
                
                # Price: precio -> price
                price_val = data.get("precio") or data.get("price") or 0
                price = self._parse_price(price_val)
                
                # Category: categoria -> category -> machine_name -> 'general'
                category = data.get("categoria") or data.get("category") or data.get("machine_name") or "general"
                
                # Image: Prioritize Firebase Storage fields (imagen/foto/image) over external imagenUrl
                image_val = data.get("imagen") or data.get("foto") or data.get("image")
                if image_val:
                    image_url = self._get_first_image(image_val)
                else:
                    # Fallback to imagenUrl dictionary if storage fields are missing
                    image_url_obj = data.get("imagenUrl", {})
                    if isinstance(image_url_obj, dict):
                        image_url = image_url_obj.get("url", "")
                    else:
                        image_url = ""

                # Search Tags: searchBy (list)
                search_tags = data.get("searchBy", [])
                if not isinstance(search_tags, list):
                    search_tags = []
                
                # Normalize tags
                search_tags = [str(t).lower().strip() for t in search_tags if t]
                
                # Active Status: active -> activo -> is_active -> True (default)
                is_active = data.get("active", data.get("activo", data.get("is_active", True)))
                
                # Relaxed active check
                if str(is_active).lower() == 'false': 
                    continue

                # Link: external_url -> url -> link
                link = data.get("external_url") or data.get("url") or data.get("link") or ""

                # Specs: fichatecnica -> ficha_tecnica -> specs
                raw_specs = data.get("fichatecnica") or data.get("ficha_tecnica") or data.get("specs")
                specs = self._parse_specs(raw_specs)

                # Create standardized item
                mapped_item = {
                    "id": doc.id,
                    "name": name,
                    "price": price,
                    "formatted_price": f"${price:,.0f}".replace(",", "."),
                    "category": str(category).lower().strip(),
                    "image_url": image_url,
                    "active": True,
                    "description": data.get("descripcion", data.get("description", "")),
                    "specs": specs,
                    "link": link,
                    "search_tags": search_tags 
                }

                self._items.append(mapped_item)
                
                # Index by ID
                self._items_by_id[doc.id] = mapped_item
                
                # Index by category
                cat_key = mapped_item["category"]
                if cat_key not in self._items_by_category:
                    self._items_by_category[cat_key] = []
                self._items_by_category[cat_key].append(mapped_item)
            
            logger.info(f"✅ Catalog loaded: {len(self._items)} items from 'pagina/catalogo/items'")
            logger.info(f"📂 Categories: {list(self._items_by_category.keys())}")
            
        except Exception as e:
            logger.error(f"❌ Error loading catalog: {str(e)}")
            self._items = []
            self._items_by_id = {}
            self._items_by_category = {}

    def _parse_specs(self, specs_input: Any) -> str:
        """
        Parse technical specifications into a single formatted string.
        Handles both dictionaries and plain strings.
        """
        if not specs_input:
            return ""
        
        if isinstance(specs_input, dict):
            # Parse dict into a key: value list
            lines = []
            for k, v in specs_input.items():
                if v and str(v).strip():
                    key_formatted = str(k).replace("_", " ").title()
                    lines.append(f"- {key_formatted}: {str(v).strip()}")
            return "\n".join(lines)
            
        elif isinstance(specs_input, str):
            return specs_input.strip()
            
        return str(specs_input)

    def _parse_price(self, price_input: Any) -> int:
        """
        Helper to parse price from various formats (int, string, etc).
        Handles '$ 5.000.000', '5.000.000', etc.
        """
        if isinstance(price_input, (int, float)):
            return int(price_input)
        
        if isinstance(price_input, str):
            try:
                # Remove currency symbols, dots, commas, spaces
                clean_price = price_input.replace("$", "").replace(".", "").replace(",", "").replace(" ", "").strip()
                if not clean_price:
                    return 0
                return int(clean_price)
            except ValueError:
                return 0
        
        return 0

    def _get_first_image(self, val: Any) -> str:
        """
        Helper to extract the first valid image URL.
        Handles both string URLs and lists of URLs.
        Args:
            val: The value from Firestore (str, list, or None)
        """
        if not val:
            return ""
            
        if isinstance(val, list):
            # Return first non-empty string in list
            for item in val:
                if isinstance(item, str) and item.strip():
                    return item.strip()
        
        elif isinstance(val, str) and val.strip():
            return val.strip()
            
        return ""

    def get_all_items(self) -> List[Dict[str, Any]]:
        """Get all catalog items."""
        return self._items
    
    def get_by_id(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific item by ID."""
        return self._items_by_id.get(item_id)
    
    def get_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Get all items in a specific category."""
        return self._items_by_category.get(category, [])
    
    def get_categories(self) -> List[str]:
        """Get list of all available categories."""
        return list(self._items_by_category.keys())
    
    def search_items(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for items using fuzzy matching, token tolerance, and tags.
        Returns top results sorted by implementation score.
        """
        import difflib
        
        query = query.lower().strip()
        if not query:
            return []

        scored_results = []
        
        # Pre-compute query tokens
        query_tokens = query.split()
        
        logger.info(f"🔎 DEBUG SEARCH: Query='{query}' Tokens={query_tokens}")
        
        for item in self._items:
            score = 0
            
            # Fields to search
            name = item.get("name", "").lower()
            category = item.get("category", "").lower()
            tags = item.get("search_tags", [])
            
            # 1. Exact Substring in Name (Highest Confidence)
            if query in name:
                score += 100
            
            # 2. Check Search Tags (High Confidence)
            # If query matches a tag exactly or if all query tokens are present in tags
            for tag in tags:
                if query == tag:
                    score += 95
                elif query in tag:
                    score += 80
            
            # 3. Token Match (e.g. "TVS 125" -> "TVS" + "125" in "TVS Raider 125")
            # Checks if ALL query tokens exist in the item's name/category/tags
            if len(query_tokens) > 0:
                # Combine all text sources
                item_text = f"{name} {category} {' '.join(tags)}"
                
                matches = 0
                for t in query_tokens:
                    if t in item_text:
                        matches += 1
                    else:
                        # Fuzzy matches for tokens? "Raidr" -> "Raider"
                        # Check against name words and tags
                        fuzzy_hit = False
                        
                        # Check name words
                        for word in name.split():
                            if difflib.SequenceMatcher(None, t, word).ratio() > 0.8:
                                fuzzy_hit = True
                                break
                        
                        # Check tags
                        if not fuzzy_hit:
                            for tag in tags:
                                if difflib.SequenceMatcher(None, t, tag).ratio() > 0.8:
                                    fuzzy_hit = True
                                    break
                                    
                        if fuzzy_hit:
                            matches += 0.8 # Slightly less than exact token match

                if matches >= len(query_tokens):
                    score += 90 
                elif matches > 0:
                    score += (matches / len(query_tokens)) * 70

            # 4. Fuzzy Overall Name Match (Typos: "Raidr" -> "Raider")
            ratio = difflib.SequenceMatcher(None, query, name).ratio()
            if ratio > 0.6: # Reasonable similarity threshold
                score += ratio * 60

            if score > 30: # Lowered threshold as requested
                scored_results.append((score, item))
        
        # Sort by score descending
        scored_results.sort(key=lambda x: x[0], reverse=True)
        
        if scored_results:
             logger.info(f"✅ Top Result: {scored_results[0][1]['name']} (Score: {scored_results[0][0]})")
        
        # Return top 5 unique items
        unique_results = []
        seen_ids = set()
        for _, item in scored_results:
            if item["id"] not in seen_ids:
                unique_results.append(item)
                seen_ids.add(item["id"])
                
        return unique_results[:5]

    def refresh(self) -> None:
        """Refresh catalog from Firestore."""
        logger.info("🔄 Refreshing catalog...")
        self.load_catalog()

# Global service instance
catalog_service = CatalogService()
