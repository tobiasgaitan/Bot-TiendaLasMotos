"""
Catalog Service
Manages motorcycle catalog from Firestore.
Provides in-memory access to catalog items with category filtering.
"""

import logging
import re
import unicodedata
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
        self._category_aliases: Dict[str, List[str]] = {}
    
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
                
            # Initialize or retrieve dynamic config for aliases
            # Mantenibilidad: Se inyectan dinámicamente desde Firestore para 
            # permitir actualizaciones sin redespliegues (QA Baseline).
            from app.core.config_loader import ConfigLoader
            config_loader = ConfigLoader()
            catalog_config = config_loader.get_catalog_config()
            self._category_aliases = catalog_config.get("category_aliases", {})

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
                
                # Image Selection: Prioritize imagen_url (the designated CMS field)
                # ULTIMATUM: Only allow Firebase Storage links. Block all others including media.autecomobility.com.
                image_url = ""
                potential_fields = ["imagen_url", "imagenUrl", "imagen", "foto", "image"]
                
                for field in potential_fields:
                    val = data.get(field)
                    if val:
                        raw = str(val).strip()
                        # If its a list or dict, extract first string
                        if isinstance(val, list) and len(val) > 0:
                            raw = str(val[0]).strip()
                        elif isinstance(val, dict):
                            raw = str(next(iter(val.values()))).strip()
                            
                        if "firebasestorage.googleapis.com" in raw:
                            # Sanity check: Ensure it's a valid Firebase link
                            image_url = raw
                            logger.info(f"✅ Image Found for {ref} in {field}: {image_url}")
                            break 
                
                if not image_url:
                    logger.warning(f"⚠️ No valid Firebase link found for {ref}. Checked: {potential_fields}")

                # Search Tags: searchBy (list)
                search_tags = data.get("searchBy", [])
                if not isinstance(search_tags, list):
                    search_tags = []
                
                # Normalize tags
                search_tags = [str(t).lower().strip() for t in search_tags if t]
                
                # Active Status: active -> activo -> is_active -> isVisible -> onStock
                is_active = data.get("active", data.get("activo", data.get("is_active", True)))
                is_visible = data.get("isVisible", True)
                on_stock = data.get("onStock", True)
                
                # Rigid filtering for catalog hygiene
                if str(is_active).lower() == 'false' or not is_visible or not on_stock: 
                    continue

                # Link: external_url -> url -> link
                link = data.get("external_url") or data.get("url") or data.get("link") or ""

                # Specs: fichatecnica -> ficha_tecnica -> specs
                raw_specs = data.get("fichatecnica") or data.get("ficha_tecnica") or data.get("specs")
                specs = self._parse_specs(raw_specs)

                # --- EXTRACCIÓN DE CILINDRAJE (Audit v6.8.0) ---
                # Why: Required to fetch the correct registration cost from ConfigService.
                # Must be a numeric value for range matching.
                cc = None
                if isinstance(raw_specs, dict):
                    # Priority 1: Generic 'cilindraje' field in specs
                    cc_raw = raw_specs.get("cilindraje") or raw_specs.get("displacement")
                    if cc_raw:
                        try:
                            # Extract numeric part (e.g., "160 cc" -> 160)
                            cc_match = re.search(r'(\d+)', str(cc_raw))
                            if cc_match:
                                cc = int(cc_match.group(1))
                        except (ValueError, TypeError):
                            pass
                
                # Priority 2: Direct field in data (if available)
                if cc is None:
                    cc_val = data.get("cilindraje") or data.get("cc")
                    if cc_val:
                        try:
                            cc_match = re.search(r'(\d+)', str(cc_val))
                            if cc_match:
                                cc = int(cc_match.group(1))
                        except (ValueError, TypeError):
                            pass

                # --- Build Rich Searchable Corpus ---
                # Why: Concatenating categories, tech specs, tags, and promotional data 
                # resolving the "search blindness" issue for non-name queries (like displacement)
                corpus_parts = [name, str(category)]
                
                # Global Aliases Extension: Ensure "trabajo" always matches TVS Sport
                if "tvs sport" in name.lower():
                    corpus_parts.extend(["trabajo", "trabajar", "mensajeria", "domicilios", "carga"])
                
                categories_arr = data.get("categories", [])
                if isinstance(categories_arr, list):
                    corpus_parts.extend([str(c) for c in categories_arr])
                    
                # --- APPLY FUZZY ALIASES (Semantic Expansion) ---
                # Inject synonyms directly into the search index so strict token matching
                # natively catches semantic intents like "doble proposito"
                for cat in [str(category)] + [str(c) for c in categories_arr]:
                    # Mantenibilidad: Replace '/' with '_' because Firebase Console UI restricts 
                    # the use of forward slashes ('/') in Map keys, ensuring admins can safely 
                    # create keys like "urbana y_o trabajo" instead of failing.
                    clean_cat = str(cat).lower().strip().replace('/', '_')
                    if clean_cat in self._category_aliases:
                        corpus_parts.extend(self._category_aliases[clean_cat])
                
                if isinstance(raw_specs, dict):
                    for spec_key in ["cilindraje", "transmision", "potencia", "torque", "frenos"]:
                        if spec_val := raw_specs.get(spec_key):
                            corpus_parts.append(str(spec_val))
                
                try:
                    if int(data.get("bonusAmount", 0)) > 0:
                        corpus_parts.append("bono descuento promocion")
                except (ValueError, TypeError):
                    pass
                
                corpus_parts.extend(search_tags)
                keywords_arr = data.get("keywords", [])
                if isinstance(keywords_arr, list):
                    corpus_parts.extend([str(k) for k in keywords_arr])
                
                raw_corpus = " ".join(corpus_parts)
                item_search_tokens = self._tokenize(raw_corpus)
                item_search_text = " ".join(item_search_tokens)

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
                    "search_tokens": item_search_tokens,
                    "search_text": item_search_text,
                    "cc": cc  # Store numeric CC for late-binding financial logic
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

    def _tokenize(self, text: str) -> List[str]:
        """
        Cleans and tokenizes text for search indexing.
        Why: Standardizing both the catalog text and user query by removing accents, special 
        characters (like Y/O), and casing ensures that AI search logic is highly tolerant 
        of typos and variations in input. This boosts search recall.
        """
        if not text:
            return []
        
        # Lowercase
        text = str(text).lower()
        
        # Remove accents
        text = ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
        
        # Replace y/o with space
        text = text.replace('y/o', ' ')
        
        # Replace all non-alphanumeric (including slashes) with space
        text = re.sub(r'[^a-z0-9\s]', ' ', text)
        
        # Tokenize and remove stop words
        tokens = text.split()
        stop_words = {"quiero", "una", "un", "moto", "motos", "busco", "la", "el", "de", "las", "los", "con", "en", "para", "y", "o"}
        return [t for t in tokens if t not in stop_words]

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
        Search for items using rich search index, fuzzy matching, and token tolerance.
        Why: Replacing naive substring matching with full-corpus token evaluation allows 
        queries like "moto automatica 125cc" to match against deeply nested technical specs,
        dramatically improving conversion and accuracy.
        """
        import difflib
        
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        clean_query = " ".join(query_tokens)
        scored_results = []
        
        logger.info(f"🔎 DEBUG SEARCH: Original='{query}' Clean='{clean_query}' Tokens={query_tokens}")
        
        for item in self._items:
            score = 0
            
            name = item.get("name", "").lower()
            name_clean = " ".join(self._tokenize(name))
            item_tokens = item.get("search_tokens", [])
            item_search_text = item.get("search_text", "")
            
            # Detect matches in different areas for the adaptor
            name_match = clean_query in name_clean
            corpus_match = clean_query in item_search_text
            
            # 1. Exact Substring (Highest Confidence)
            if name_match:
                score += 100
            elif corpus_match:
                score += 85  # Exact substring in other fields (category/specs/tags)
            
            # 2. Token Match
            # Checks if query tokens exist in the rich searchable corpus (item_tokens)
            matches = 0
            if len(query_tokens) > 0:
                for t in query_tokens:
                    if t in item_tokens:
                        matches += 1
                    else:
                        # Fuzzy matches for tokens (e.g., "raidr" -> "raider")
                        fuzzy_hit = False
                        for target_token in set(item_tokens):
                            if difflib.SequenceMatcher(None, t, target_token).ratio() > 0.8:
                                fuzzy_hit = True
                                break
                        if fuzzy_hit:
                            matches += 0.8 # Slightly less than exact token match

                if matches >= len(query_tokens):
                    score += 90 
                elif matches > 0:
                    score += (matches / len(query_tokens)) * 70

            # 3. Fuzzy Overall Name Match (Typos: "Raidr" -> "Raider")
            ratio = difflib.SequenceMatcher(None, clean_query, name_clean).ratio()
            if ratio > 0.6: # Reasonable similarity threshold
                score += ratio * 60

            # --- CAPA DE ADAPTADOR: Intent Scoring Bonus (1.5x) ---
            # Why: Apply a 50% multiplier if the query matches category tags or aliases
            # while protecting "identity" searches (exact name match).
            score = self._apply_scoring_adaptor(item, query_tokens, score, name_match)

            if score > 30: # Lowered threshold as requested
                scored_results.append((score, item))
        
        # Sort by score descending
        scored_results.sort(key=lambda x: x[0], reverse=True)
        
        if scored_results:
             logger.info(f"✅ Top Result: {scored_results[0][1]['name']} (Score: {scored_results[0][0]})")
        
        # Return top 3 unique items with truncated fields (Prompt Optimization)
        # Why: Reducing the payload to 3 results and 4 fields (Name, Price, Image, Summary)
        # prevents prompt inflation and keeps the context window focused.
        unique_results = []
        seen_ids = set()
        
        # Access config_service for registration costs
        from app.services.config_service import config_service
        
        for _, item in scored_results:
            if item["id"] not in seen_ids:
                # --- PRICE CONSOLIDATION (Audit v6.8.0) ---
                # Mandato de Oficio: Summation occurs in backend. AI is prohibited.
                base_price = item.get("price", 0)
                cc = item.get("cc")
                category = item.get("category")
                
                # Fetch registration cost from memory-cached config (O(1))
                reg_cost = config_service.get_registration_cost(cc=cc, category=category)
                total_price = base_price + reg_cost
                
                # Build formatted price with mandatory legal disclaimer
                # Strict Rule: No assumptions, logic handles reg_cost=0 naturally.
                formatted_w_soat = f"${total_price:,.0f} (incluye SOAT, Matrícula, y tramites)".replace(",", ".")
                
                # Truncate according to objective: Name, Price, Category, Image URL, and 10-word summary
                truncated_item = {
                    "name": item.get("name"),
                    "price": formatted_w_soat, 
                    "raw_price": total_price, 
                    "formatted_price": formatted_w_soat,
                    "category": item.get("category", "Moto"),
                    "image_url": item.get("image_url"),
                    "summary": self._summarize(item.get("description", ""))
                }
                unique_results.append(truncated_item)
                seen_ids.add(item["id"])
                
        return unique_results[:3]

    def search(self, query: str) -> List[Dict[str, Any]]:
        """
        Alias for search_items to maintain backward compatibility 
        and satisfy the contract expected by ai_brain.py.
        """
        return self.search_items(query)

    def _summarize(self, text: str, max_words: int = 10) -> str:
        """Helper to truncate description to a 10-word summary."""
        if not text:
            return ""
        # Clean markdown or biological tags if any
        clean_text = re.sub(r'<[^>]+>', '', str(text))
        words = clean_text.split()
        if len(words) <= max_words:
            return clean_text
        return " ".join(words[:max_words]) + "..."

    def _apply_scoring_adaptor(self, item: Dict[str, Any], query_tokens: List[str], current_score: float, is_identity_match: bool) -> float:
        """
        Independent adapter layer to apply intent-based bonuses.
        IMPLEMENTS: business_logic.priority_model contract.
        """
        item_name = item.get("name", "").lower()
        
        # 1. HARD-LOCK: "trabajo/domicilios" -> TVS Sport 100 priority force
        work_keywords = ["trabajo", "domicilio", "domicilios", "mensajería", "mensajeria", "moto para cargar"]
        is_work_intent = any(tk.lower() in work_keywords for tk in query_tokens)
        
        if is_work_intent and "tvs sport 100" in item_name:
            # Absolute priority as per contract (id: work_bike_priority_lock)
            new_score = current_score + 10000.0
            logger.info(f"🚀 HARD-LOCK: Priority Boost for {item['name']} (Work Intent Detected)")
            return new_score

        if is_identity_match:
            # Identity search should not be inflated by generic tags
            return current_score

        # 2. Existing Semantic Bonus (1.5x)
        tags = item.get("search_tags", [])
        intent_match = any(token in tags for token in query_tokens)
        
        if intent_match:
            # Apply the 50% Intent Bonus
            new_score = current_score * 1.5
            logger.debug(f"⚡ Intent Bonus Applied to {item['name']}: {current_score} -> {new_score}")
            return new_score

        return current_score

    def refresh(self) -> None:
        """Refresh catalog from Firestore."""
        logger.info("🔄 Refreshing catalog...")
        self.load_catalog()

# Global service instance
catalog_service = CatalogService()
