"""
Catalog Service
Manages motorcycle catalog from Firestore.
Provides in-memory access to catalog items with category filtering.
"""

import logging
import re
import unicodedata
from datetime import datetime
from typing import List, Dict, Any, Optional, Union

from google.cloud import firestore

from app.services.semantic_cache_service import SemanticCacheService

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
        self._cache_service = SemanticCacheService()
    
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
            try:
                from app.core.config_loader import ConfigLoader
                config_loader = ConfigLoader()
                catalog_config = config_loader.get_catalog_config()
                self._category_aliases = catalog_config.get("category_aliases", {})
            except Exception:
                logger.warning("⚠️ ConfigLoader not ready. Using empty category aliases.")
                self._category_aliases = {}

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
                
                # Price: price (canonical)
                price_val = data.get("price") or 0
                price = self._parse_price(price_val)
                
                # Category: categoria -> category -> machine_name -> 'general'
                category = data.get("categoria") or data.get("category") or data.get("machine_name") or "general"
                
                # [BOT-BE-4.2] Canonical Image Extraction — Schema-Hardened
                # ÚNICA fuente de verdad: la llave canónica 'imagen_url' post-migración.
                # Zero-Silent-Failure: ítems activos sin imagen_url son rechazados del catálogo
                # para proteger el Price Consistency Check (PCC Pro).
                raw_image_url = data.get("imagen_url", "")
                image_url = str(raw_image_url).strip() if raw_image_url else ""

                if not image_url:
                    logger.error(
                        f"❌ [PCC-GUARD] Ítem activo '{doc.id}' (ref='{ref}') omitido del catálogo: "
                        f"no posee la llave canónica 'imagen_url'. "
                        f"Ejecuta el script de normalización para corregir el esquema en Firestore."
                    )
                    continue

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

                # --- EXTRACCIÓN DE CILINDRAJE (Audit v6.9.0) ---
                # Why: DisplacementExtractorV2 - Robust extraction for registration costs.
                # Normalizes "159.7 CC", 159.7, or "CILINDRAJE" (Upper) into int(159).
                cc = self._extract_cc(data)

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
                bonus_amount = 0
                try:
                    bonus_amount = int(float(data.get("bonusAmount") or 0))
                except (ValueError, TypeError):
                    pass
                bonus_end_date = data.get("bonusEndDate")

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
                    "searchBy": search_tags,
                    "cc": cc,  # Store numeric CC for late-binding financial logic
                    "bonusAmount": bonus_amount,
                    "bonusEndDate": bonus_end_date
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
            
            # Hydrate cache
            self._hydrate_cache()
            
        except Exception as e:
            logger.error(f"❌ Error loading catalog: {str(e)}")
            self._items = []
            self._items_by_id = {}
            self._items_by_category = {}

    def _hydrate_cache(self) -> None:
        """
        Synchronously pre-warms the Semantic Cache with high-frequency queries
        to guarantee zero latency on common searches.
        """
        logger.info("💧 Hydrating Semantic Cache...")
        high_freq_queries = [
            "tvs sport",
            "motos de trabajo",
            "moto automatica",
            "scooter",
            "apache",
            "honda navi",
            "pulsar"
        ]
        
        self._cache_service.clear()
        
        for query in high_freq_queries:
            # Executing search_catalog naturally stores the result in the cache
            self.search_catalog(query)
            
        logger.info(f"✅ Semantic Cache hydrated with {len(high_freq_queries)} entries.")


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
        stop_words = {"quiero", "una", "un", "moto", "motos", "busco", "la", "el", "de", "las", "los", "con", "en", "para", "y", "o", "tienen", "tienes", "tiene", "contas", "disponible", "venden", "precio", "valor", "cuanto", "cuesta", "vale"}
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

    # [BOT-BE-4.2] _get_first_image eliminado — Dead Code Post-Migración.
    # La extracción de imagen ahora ocurre exclusivamente en load_catalog()
    # mediante lectura directa de la llave canónica 'imagen_url'.

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
            # --- IDENTITY DETECTION (v9.8.1) ---
            # Brand exclusion list to focus on model identity
            brands = {"tvs", "victory", "bajaj", "hero", "yamaha", "honda", "suzuki", "akt", "apache"}
            name_tokens = self._tokenize(name)
            # Core tokens: Not a brand, length >= 2, and not purely digits
            core_name_tokens = [t for t in name_tokens if t not in brands and len(t) >= 2 and not t.isdigit()]
            
            # Identity match if query contains any core model token or vice-versa
            name_match = any(t in query_tokens for t in core_name_tokens) if core_name_tokens else (clean_query in name_clean)
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
                
                bonus_info = self._get_active_bonus_info(item.get("bonusAmount"), item.get("bonusEndDate"))
                
                # Truncate according to objective: Name, Price, Category, Image URL, and 10-word summary
                truncated_item = {
                    "name": item.get("name"),
                    "price": formatted_w_soat, 
                    "raw_price": total_price, 
                    "formatted_price": formatted_w_soat,
                    "category": item.get("category", "Moto"),
                    "image_url": item.get("image_url"),
                    "searchBy": item.get("searchBy", []), # Include search tokens for Judge validation
                    "summary": self._summarize(item.get("description", ""))
                }
                
                if bonus_info:
                    truncated_item["bonusAmount"] = bonus_info["amount"]
                    truncated_item["bonusEndDate"] = bonus_info["end_date"]
                else:
                    truncated_item["bonusAmount"] = 0
                    truncated_item["bonusEndDate"] = None
                    
                unique_results.append(truncated_item)
                seen_ids.add(item["id"])
                
        return unique_results[:3]

# =========================================================================
    # PUBLIC API INTERFACES (CONTRACTS)
    # =========================================================================

    def search(self, query: str) -> List[Dict[str, Any]]:
        """
        Legacy/Internal entry point for motorcycle search.
        Maintains strict contract compatibility with whatsapp.py and JudgeService.
        """
        return self.search_items(query)

    def search_catalog(self, query: str) -> str:
        """
        AI Agent entry point for motorcycle search.
        Strictly matches the tool name defined in the Gemini SDK and ai_brain.py.
        Now returns Markdown directly from the Semantic Cache to bypass network latency
        and protect the Price Consistency Check (PCC).
        """
        cached_result, score = self._cache_service.get(query)
        if cached_result and score > 0.85:
            logger.info(f"⚡ Semantic Cache Hit (score: {score:.2f})")
            return cached_result
            
        matches = self.search_items(query)
        
        if matches:
            search_results = f"Encontré {len(matches)} motos relacionados:\n"
            for m in matches: 
                name = m.get('name', 'Moto')
                category = m.get('category', 'Moto')
                price = m.get('price', m.get('formatted_price', 'Consultar'))
                
                bonus_str = ""
                b_amt = m.get("bonusAmount", 0)
                b_end = m.get("bonusEndDate")
                if b_amt > 0 and b_end:
                    formatted_amt = f"${b_amt:,.0f}".replace(",", ".")
                    bonus_str = f" [BONO EXCLUSIVO DE CONTADO: {formatted_amt} válido hasta {b_end}]"
                
                search_results += f"- {name} ({category}): {price}{bonus_str}\n"
                if m.get('image_url'): search_results += f"  Image URL: {m['image_url']}\n"
                if m.get('link'): search_results += f"  Link: {m['link']}\n"
                if m.get('summary'): search_results += f"  Ficha Tecnica: {m['summary']}\n"
                
            competitor_brands = ["boxer", "nkd", "pulsar", "yamaha", "honda", "suzuki", "akt"]
            if any(b in query.lower() for b in competitor_brands):
                search_results = f"[SISTEMA: El usuario preguntó por la competencia. ESTÁS OBLIGADO a pivotar a nuestras alternativas...]\n\n" + search_results
        else:
            search_results = "No encontré motos en el catálogo para esa búsqueda."
            
        self._cache_service.set(query, search_results)
        return search_results

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

    def _get_active_bonus_info(self, bonus_amount: Any, bonus_end_date: Any) -> Optional[Dict[str, Any]]:
        """
        Validates the bonus and returns formatted amount and date if active.
        """
        try:
            amt = int(float(bonus_amount or 0))
            if amt <= 0:
                return None
        except (ValueError, TypeError):
            return None

        if not bonus_end_date:
            return None

        try:
            now = datetime.now()
            dt = None
            
            # 1. Handle objects with 'timestamp' or 'to_datetime' (like Firestore Timestamp or datetime)
            if hasattr(bonus_end_date, 'timestamp'):
                dt = bonus_end_date
                if hasattr(dt, 'to_datetime'):
                    dt = dt.to_datetime()
                if dt.tzinfo is not None:
                    # Make now tz-aware using the same timezone
                    now_tz = datetime.now(dt.tzinfo)
                    if now_tz <= dt:
                        pass
                    else:
                        return None
                else:
                    if now <= dt:
                        pass
                    else:
                        return None
                        
            # 2. Handle string formats
            elif isinstance(bonus_end_date, str):
                parsed = False
                for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%fZ"):
                    try:
                        dt_parsed = datetime.strptime(bonus_end_date.split('.')[0].replace('Z', ''), fmt[:len(bonus_end_date.split('.')[0].replace('Z', ''))])
                        if now <= dt_parsed:
                            dt = dt_parsed
                            parsed = True
                            break
                        else:
                            return None
                    except ValueError:
                        continue
                if not parsed:
                    match = re.match(r'(\d{4})-(\d{2})-(\d{2})', bonus_end_date)
                    if match:
                        dt = datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
                        dt = dt.replace(hour=23, minute=59, second=59)
                        if now <= dt:
                            pass
                        else:
                            return None
                    else:
                        return None
            # 3. Handle epoch timestamp
            elif isinstance(bonus_end_date, (int, float)):
                dt = datetime.fromtimestamp(bonus_end_date)
                if now <= dt:
                    pass
                else:
                    return None
            else:
                return None

            if dt:
                # Format date Y: YYYY-MM-DD
                date_str = dt.strftime("%Y-%m-%d")
                # Format amount X: e.g. $500.000 (Colombia format)
                amt_str = f"${amt:,.0f}".replace(",", ".")
                return {
                    "amount": amt,
                    "formatted_amount": amt_str,
                    "end_date": date_str,
                    "raw_end_date": bonus_end_date
                }
        except Exception as e:
            logger.error(f"⚠️ Error evaluating bonusEndDate '{bonus_end_date}': {str(e)}")
            return None
        return None

    def _is_bonus_active(self, bonus_amount: Any, bonus_end_date: Any) -> bool:
        """
        Validates if the bonus is greater than 0 and active (current date <= bonus_end_date).
        """
        return self._get_active_bonus_info(bonus_amount, bonus_end_date) is not None

    def _extract_cc(self, data: Dict[str, Any]) -> int:
        """
        [MANDATO v6.9.0] DisplacementExtractorV2
        Multi-layer extraction with case-insensitive search and float truncation.
        """
        def find_in_dict(d: Any, keys: List[str]) -> Any:
            if not isinstance(d, dict): return None
            # Case-insensitive mapping
            d_lower = {str(k).lower(): v for k, v in d.items()}
            for k in keys:
                if k in d_lower: return d_lower[k]
            return None

        try:
            # Phase 1: Search root
            cc_val = find_in_dict(data, ["displacement", "cilindraje", "cc"])
            
            # Phase 2: Search fichatecnica
            if cc_val is None:
                ft = data.get("fichatecnica") or data.get("ficha_tecnica") or {}
                cc_val = find_in_dict(ft, ["cilindraje", "displacement", "cc", "rango cilindraje"])

            if cc_val is None:
                return 0

            # Phase 3: Regex strict extraction (r'\d+(?:\.\d+)?')
            # Why: Ensures 159.7 CC -> 159.7 and prevents ValueError on int()
            match = re.search(r'\d+(?:\.\d+)?', str(cc_val))
            if match:
                # Phase 4: float -> int (Truncate as per Legal Requirement)
                return int(float(match.group(0)))
            
            return 0
        except Exception as e:
            logger.error(f"⚠️ Error extracting CC: {str(e)}")
            return 0

    def _apply_scoring_adaptor(self, item: Dict[str, Any], query_tokens: List[str], current_score: float, is_identity_match: bool) -> float:
        """
        Independent adapter layer to apply intent-based bonuses.
        IMPLEMENTS: business_logic.priority_model contract (Tiered Scoring v9.8.1).
        
        Priority Levels:
        1. IDENTITY (+20,000): Explicit model match.
        2. HARD-LOCK (+10,000): "TVS Sport 100" for work intent.
        3. SEMANTIC (1.5x): Keyword/Tag match.
        """
        item_name = item.get("name", "").lower()
        new_score = current_score
        
        # --- TIER 1: IDENTITY PRIORITY (+20,000) ---
        if is_identity_match:
            new_score += 20000.0
            logger.info(f"🆔 IDENTITY BOOST: +20k for {item['name']}")

        # --- TIER 2: HARD-LOCK (Intent-Based) ---
        # "trabajo/domicilios" -> TVS Sport 100 priority force
        work_keywords = ["trabajo", "domicilio", "domicilios", "mensajería", "mensajeria", "moto para cargar"]
        is_work_intent = any(tk.lower() in work_keywords for tk in query_tokens)
        
        if is_work_intent and "tvs sport 100" in item_name:
            # Absolute priority as per contract (id: work_bike_priority_lock)
            new_score += 10000.0
            logger.info(f"🚀 HARD-LOCK: +10k for {item['name']} (Work Intent Detected)")

        # --- TIER 3: SEMANTIC BONUS (1.5x) ---
        if not is_identity_match:
            tags = item.get("search_tokens", [])
            intent_match = any(token in tags for token in query_tokens)
            
            if intent_match:
                # Apply the 50% Intent Bonus
                new_score = new_score * 1.5
                logger.debug(f"⚡ Intent Bonus Applied to {item['name']}: {current_score} -> {new_score}")

        return new_score

    def refresh(self) -> None:
        """Refresh catalog from Firestore."""
        logger.info("🔄 Refreshing catalog...")
        self.load_catalog()

# Global service instance
catalog_service = CatalogService()
