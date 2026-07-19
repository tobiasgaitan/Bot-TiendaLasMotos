"""
Cerebro IA - AI Brain Service
Handles intelligent responses using Google Gemini AI for general inquiries.
"""

import logging
import os
import re
import json
import time
import asyncio
import random
from typing import Optional, Dict, Any, List, Union
from datetime import datetime

from app.utils.json_processor import clean_json_voorhees
from app.core.exceptions import HabeasDataBypassInterrupt

logger = logging.getLogger(__name__)

# Use the new unified google-genai SDK
try:
    from google import genai
    from google.genai import types
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    logger.warning("⚠️  google-genai SDK not available, using fallback responses")

# [BOT-TRACE-201] Langfuse Observability
from app.utils.observability import observe, langfuse_context, LANGFUSE_AVAILABLE


# Unused class kept for backward compatibility with tests/test_trace_propagation.py
class _LangfuseContextShim:
    def update_current_trace(self, **kwargs): pass
    def update_current_observation(self, **kwargs): pass
    def update_current_generation(self, **kwargs): pass



EXTRACTION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "summary": {
            "type": "STRING",
            "description": "Resumen de la sesión (máx 500 caracteres, sin Markdown)."
        },
        "extracted": {
            "type": "OBJECT",
            "properties": {
                "nombre": {
                    "type": "STRING",
                    "description": "Nombre del cliente (máx 50 caracteres, saneado)."
                },
                "ciudad": {
                    "type": "STRING",
                    "description": "Ciudad del cliente (máx 50 caracteres)."
                },
                "moto_interest": {
                    "type": "STRING",
                    "description": "La primera moto o estilo por el que preguntó el usuario."
                },
                "habeas_data_accepted": {
                    "type": "BOOLEAN",
                    "description": "Indica si el usuario aceptó el tratamiento de datos (mapeado de afirmaciones o emojis)."
                },
                "habeas_data_accepted_sent": {
                    "type": "BOOLEAN",
                    "description": "Indica si el bot ya envió el script legal y el enlace de la política de privacidad."
                },
                "forma_pago": {
                    "type": "STRING",
                    "description": "Método de pago preferido (ej. Crédito - 0 inicial, Contado, Financiado)."
                },
                "ocupacion": {
                    "type": "STRING",
                    "description": "Ocupación o tipo de contrato laboral si se mencionó (ej. Empleado, Independiente, Estudiante, Pensionado)."
                },
                "datacredito": {
                    "type": "STRING",
                    "description": "Estado o historial en Datacrédito si se mencionó (ej. Al día, Reportado, Sin experiencia, Castigado)."
                },
                "vivienda": {
                    "type": "STRING",
                    "description": "Tipo de vivienda o situación de gastos de vivienda si se mencionó (ej. Arriendo, Familiar, Propia)."
                },
                "servicios_publicos": {
                    "type": "STRING",
                    "description": "Si tiene servicios públicos como Gas Natural a su nombre o plan de celular si se mencionó."
                },
                "moto_confirmada": {
                    "type": "BOOLEAN",
                    "description": "Indica si el usuario aceptó explícitamente la moto ofrecida o mostró interés cerrado (Shadow State Sync)."
                },
                "cedula_usuario": {
                    "type": "STRING",
                    "description": "Número de cédula del usuario (extraer ÚNICAMENTE si el usuario lo escribe de forma explícita y voluntaria; bias negativo estricto: si no está seguro o no está presente, dejar vacío)."
                },
                "ponytail_status": {
                    "type": "STRING",
                    "description": "Estado del flujo Ponytail (cola de prioridad de lead). Valores permitidos: UNINITIATED | PENDING | IN_PROGRESS | COMPLETED | DEPRIORITIZED. Bias negativo estricto: si no hay certeza del estado, dejar vacío."
                },
                "ponytail_score": {
                    "type": "STRING",
                    "description": "Score Ponytail en rango [0-100] calculado a partir de interacciones tempranas (greetings, moto_interest, forma_pago). Bias negativo estricto: si no está seguro o no hay datos suficientes, dejar vacío."
                }
            },
            "required": ["nombre", "ciudad", "moto_interest", "habeas_data_accepted"]
        }
    },
    "required": ["summary", "extracted"]
}


class CerebroIA:
    """
    AI Brain for intelligent conversation handling.
    
    Uses Google Gemini 2.5 Flash model via Vertex AI to generate
    contextual responses for general inquiries about motorcycles,
    services, and dealership information.
    """
    
    def __init__(self, config_loader=None, catalog_service=None):
        """
        Initialize the AI brain.
        
        Args:
            config_loader: Optional ConfigLoader instance for dynamic personality
            catalog_service: Optional CatalogService instance for tool use
        """
        self._config_loader = config_loader
        self._catalog_service = catalog_service
        self._model_id = "gemini-2.5-flash" # Default stable versioning
        self.motor_financiero = None  # Will be injected
        self._model = None
        self._chat_history = {} # In-memory small cache for last turn context
        # HOT-RELOAD FIX (Audit P1, 4.3):
        # _system_instruction is intentionally NOT cached here.
        # _get_current_instruction() reads from config_loader on every request,
        # so /admin/refresh-config takes effect immediately without a Cloud Run restart.
        self.tools = self._create_tools()
        
        # Initialize GenAI Client if available
        if SDK_AVAILABLE:
            try:
                # Use unified google-genai client for Vertex AI
                self.client = genai.Client(
                    vertexai=True, 
                    project="tiendalasmotos", 
                    location="us-central1"
                )
                
                # [CONFIG INJECTION v1.3.2]
                self.privacy_policy_url = "https://tiendalasmotos.com/politica-de-privacidad"
                if self._config_loader:
                    try:
                        partners = self._config_loader.get_partners_config()
                        self.privacy_policy_url = partners.get("privacy_policy_url", self.privacy_policy_url)
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to load privacy link from loader: {e}")

                logger.info(f"🧠 CerebroIA initialized with google-genai Client ({'Tools Enabled' if self.tools else 'No Tools'})")
            except Exception as e:
                logger.exception(f"❌ Error initializing GenAI Client: {str(e)}")
                self.client = None
        else:
            self.client = None
            logger.warning("⚠️  CerebroIA running in fallback mode (no AI)")

    def _calculate_payment_helper(self, precio: float, inicial: float, plazo_meses: int, entidad: str = "Brilla de Gases", **kwargs) -> Dict[str, Any]:
        """
        Helper to delegate payment calculation to the financial motor,
        falling back to the canonical financial_service instance if the injected motor
        doesn't expose calculate_payment (e.g. when it's ScoringService).
        """
        # [REDUNDANT TRAMITES PURGE]
        # Since the catalog search returns raw_price/price which already includes the 
        # registration/SOAT/trámites cost, we subtract the catalog registration cost 
        # to get the base commercial price of the motorcycle.
        moto_cc = float(kwargs.get("moto_cc", 0.0) or 0.0)
        category = kwargs.get("category", "motos") or "motos"
        from app.services.config_service import config_service
        reg_cost = config_service.get_registration_cost(cc=moto_cc, category=category)
        base_price = max(precio - reg_cost, 0.0)

        service = self.motor_financiero
        if not service or not hasattr(service, "calculate_payment"):
            from app.services.financial_service import financial_service
            service = financial_service
            
        # Handle 'entity' vs 'entidad' parameter naming
        ent = entidad or kwargs.get("entity", "Brilla de Gases")
        # Extract and pass other kwargs safely (e.g. moto_cc, category)
        other_args = {k: v for k, v in kwargs.items() if k not in ("entidad", "entity")}
        return service.calculate_payment(
            precio=base_price,
            inicial=inicial,
            plazo_meses=plazo_meses,
            entidad=ent,
            **other_args
        )

    def _is_synonym_or_model_match(self, query: str, moto_interest: str, aliases: dict) -> bool:
        """
        Determines if a catalog search query matches the prospect's motorcycle of interest
        either through regional synonyms (aliases dictionary) or clean alphanumeric substring match.
        """
        q = str(query).lower().strip()
        m = str(moto_interest).lower().strip()
        
        if not q or not m:
            return False
            
        if q == m:
            return True
            
        # 1. Coincidencia por subcadena limpia (ej. "TVS Apache 160" y "Apache")
        q_alnum = "".join(c for c in q if c.isalnum())
        m_alnum = "".join(c for c in m if c.isalnum())
        if q_alnum and m_alnum:
            if q_alnum in m_alnum or m_alnum in q_alnum:
                return True
                
        # 2. Coincidencia por alias de catálogo (regionalismos)
        for category, syns in aliases.items():
            cat_lower = str(category).lower().strip()
            syns_lower = [str(s).lower().strip() for s in syns]
            
            # Check if query is category or in syns
            q_matches = (q == cat_lower or q in syns_lower)
            
            # Check if moto_interest matches the category or matches any synonym containing/contained in m
            m_matches = False
            if m == cat_lower:
                m_matches = True
            else:
                for syn in syns_lower:
                    if syn in m or m in syn:
                        m_matches = True
                        break
            
            if q_matches and m_matches:
                return True
                
        return False

    def _parse_raw_price(self, raw_price_val: Any, price_val: Any) -> float:
        """
        Parses price raw and fallback values robustly.
        Ensures formatted prices like '$9.969.000.*' are cleaned of non-numeric chars
        and successfully cast to float (e.g. 9969000.0) without ValueError.
        """
        if raw_price_val is not None:
            try:
                return float(raw_price_val)
            except (ValueError, TypeError):
                clean_raw = re.sub(r'[^\d]', '', str(raw_price_val).strip())
                if clean_raw:
                    try:
                        return float(clean_raw)
                    except (ValueError, TypeError):
                        pass

        if price_val:
            try:
                clean_p = re.sub(r'[^\d]', '', str(price_val).strip())
                return float(clean_p) if clean_p else 0.0
            except (ValueError, TypeError):
                pass

        return 0.0

    async def _call_gemini_with_retry_async(self, func, *args, **kwargs):
        """
        Resiliencia de Red (Async): Implementa reintentos con Exponential Backoff
        para errores 429 (ResourceExhausted) y 503 (ServiceUnavailable).
        """
        from google.genai.errors import APIError
        max_retries = 3
        base_delay = 2.0
        
        for attempt in range(max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                err_str = str(e).lower()
                is_quota_error = "429" in err_str or "resource_exhausted" in err_str
                is_service_error = "503" in err_str or "service_unavailable" in err_str
                
                if (is_quota_error or is_service_error) and attempt < max_retries:
                    wait_time = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(f"⏳ [EXP BACKOFF] Attempt {attempt+1} failed ({type(e).__name__}). Retrying in {wait_time:.2f}s...")
                    await asyncio.sleep(wait_time)
                    continue
                
                # [Zero-Silent-Failures] Final retry failure or non-retryable error
                logger.exception(f"🚨 [GEMINI ASYNC ERROR] Final failure in _call_gemini_with_retry_async: {e}")
                if hasattr(e, "response") and hasattr(e.response, "text"):
                    logger.error(f"🚨 [GEMINI HTTP DETAIL] Response text: {e.response.text}")
                elif hasattr(e, "message"):
                    logger.error(f"🚨 [GEMINI ERROR MESSAGE] Message: {e.message}")
                
                raise e

    def _calculate_session_cost(self, usage: Any) -> float:
        """
        Calcula el costo en USD basado en los tokens de Gemini 2.5 Flash.
        Precios estimados: $0.15/1M input, $0.60/1M output.
        """
        if not usage:
            return 0.0
        # Accessing usage metadata from google-genai response attributes
        i_tokens = getattr(usage, 'prompt_token_count', 0)
        o_tokens = getattr(usage, 'candidates_token_count', 0)
        cost = (i_tokens * 0.00000015) + (o_tokens * 0.0000006)
        return round(cost, 6)

    def _call_gemini_with_retry(self, func, *args, **kwargs):
        """
        Resiliencia de Red (Sync): Versión síncrona heredada.
        """
        from google.genai.errors import APIError
        max_retries = 2
        delay = 1.5
        for attempt in range(max_retries + 1):
            try:
                if hasattr(func, "__call__"):
                    return func(*args, **kwargs)
            except APIError as e:
                if attempt < max_retries:
                    logger.warning(f"⚠️ API failure (Attempt {attempt+1}/{max_retries+1}). Retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                raise e
            except Exception as e:
                raise e
    
    def _get_current_instruction(self) -> str:
        """
        HOT-RELOAD AWARE prompt loader (Audit P1, Finding 4.3).

        WHY: Caching the system_instruction in __init__ meant that patching Firestore
        via /admin/refresh-config had no effect until the Cloud Run process restarted.
        Now we read from config_loader on every request. The config_loader has its own
        TTL-based cache so there is no meaningful performance penalty.

        Fallback strategy:
        1. Firestore via ConfigLoader (dynamic, cache-busted by /admin/refresh-config)
        2. Local personality.json (robust offline fallback)
        3. Code constant in prompts.py (last resort)
        """
        # 1. ConfigLoader (Firestore)
        if self._config_loader:
            try:
                personality = self._config_loader.get_juan_pablo_personality()
                instruction = personality.get("system_instruction", "")
                if instruction:
                    logger.info("🧠 Loaded system instruction from Firestore Config")
                    return instruction
            except Exception as e:
                logger.warning(f"⚠️ Failed to load prompt from ConfigLoader: {e}")

        # 2. JSON File fallback
        try:
            import json
            json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "core", "personality.json")
            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    instruction = data.get("system_instruction", "")
                    if instruction:
                        logger.info("🧠 Loaded system instruction from personality.json")
                        return instruction
        except Exception as e:
            logger.warning(f"⚠️ Failed to load prompt from JSON: {e}")

        # 3. Code constant fallback
        from app.core.prompts import JUAN_PABLO_SYSTEM_INSTRUCTION
        logger.info("🧠 Loaded system instruction from code constant (Fallback)")
        return JUAN_PABLO_SYSTEM_INSTRUCTION

    def _assemble_skip_greeting_prompt(self, instruction: str, prospect_data: Optional[Dict[str, Any]] = None, texto: str = "") -> str:
        """
        Runtime Prompt Assembly helper to suppress/rewrite greeting rules when skip_greeting is True.
        """
        try:
            lines = instruction.splitlines()
            new_lines = []
            for line in lines:
                line_lower = line.lower()
                # If the line defines PASO 1 (Enganche) or similar, rewrite it to forbid greetings
                if ("paso 1" in line_lower or "paso1" in line_lower or "enganche de valor" in line_lower):
                    new_lines.append("- PASO 1 (Enganche de Valor): Tienes PROHIBIDO saludar, decir 'Hola', dar la bienvenida o presentarte como Juan Pablo. Inicia tu respuesta directamente presentando la motocicleta (información, Imagen y Precio).")
                # If the line orders greetings, welcoming, or presenting yourself, suppress or modify it
                elif "saludo" in line_lower or "saludar" in line_lower or "bienvenida" in line_lower or "presentarse" in line_lower or "preséntate" in line_lower:
                    if "eres" in line_lower and "juan pablo" in line_lower:
                        # Maintain identity but forbid greeting/presenting
                        new_lines.append(line + " (NOTA: Tienes PROHIBIDO saludar o presentarte en este mensaje, inicia directamente con la motocicleta).")
                    else:
                        # Suppress conflictive greeting rule
                        new_lines.append(f"# [REGLA SUPRIMIDA POR skip_greeting: {line}]")
                else:
                    new_lines.append(line)
            
            assembled = "\n".join(new_lines)
            # Append absolute unbreakable instruction
            assembled += (
                "\n\n⚠️ INSTRUCCIÓN INQUEBRANTABLE: skip_greeting es True. "
                "Tienes estrictamente PROHIBIDO saludar (ej. decir 'Hola', 'Buenos días', 'Buenas tardes'), "
                "dar la bienvenida o hacer presentaciones personales (ej. decir 'Soy Juan Pablo'). "
                "Inicia tu respuesta directamente con la presentación de la motocicleta."
            )

            # --- CORRECCIÓN COLISIÓN TRANSICIÓN CATEGORÍA A MODELO ---
            # Evitamos inyectar la instrucción de error de referencia si el usuario menciona
            # explícitamente una moto del catálogo en su mensaje, previniendo falsos negativos.
            moto_interest = prospect_data.get("moto_interest") if prospect_data else None
            if not moto_interest or not str(moto_interest).strip():
                has_explicit_model = False
                if self._catalog_service and texto:
                    t_norm = texto.lower().strip()
                    # Reutilizar el pool cached pre-hidratado llamando directamente a get_all_items()
                    items = self._catalog_service.get_all_items()
                    for item in items:
                        ref_val = str(item.get("ref", "")).lower().strip()
                        name_val = str(item.get("name", "")).lower().strip()
                        if (ref_val and ref_val in t_norm) or (name_val and name_val in t_norm):
                            has_explicit_model = True
                            break
                        
                        # Check search_tags / searchBy
                        search_tags = item.get("search_tags", []) or item.get("searchBy", [])
                        if isinstance(search_tags, list):
                            for tag in search_tags:
                                tag_norm = str(tag).lower().strip()
                                if tag_norm and tag_norm in t_norm:
                                    if len(tag_norm) > 3: # Evitar falsos positivos con palabras de ruido ultra cortas
                                        has_explicit_model = True
                                        break
                            if has_explicit_model:
                                break
                
                if not has_explicit_model:
                    # Inyectar instrucción de error de referencia
                    assembled += (
                        "\n\n[SISTEMA: ERROR DE REFERENCIA. El usuario no ha indicado un interés en una moto válida "
                        "y no existe un 'moto_interest' registrado. Indica amablemente que no conocemos ese modelo o referencia.]"
                    )
                else:
                    # Búsqueda prioritaria permitida sin inyectar error
                    assembled += (
                        "\n\n[SISTEMA: BÚSQUEDA PRIORITARIA. El usuario ha mencionado explícitamente el modelo en su mensaje. "
                        "Tienes permitido usar 'search_catalog' para ese modelo de manera prioritaria. Presenta la motocicleta con Imagen y Precio.]"
                    )
            
            return assembled
        except Exception as e:
            logger.exception(f"❌ Error during _assemble_skip_greeting_prompt: {e}")
            raise e
    
    def _extract_visual_blocks(self, text: str) -> List[str]:
        """Extrae líneas con precios ($), cuotas o imágenes Markdown (v1.3.2)."""
        extracted = []
        if not text:
            return extracted
            
        lines = text.split('\n')
        for line in lines:
            line_clean = line.strip()
            # Detectar imagen Markdown
            if "![" in line_clean and "](" in line_clean:
                extracted.append(line_clean)
            # Detectar precio o cuota (contiene $)
            elif "$" in line_clean:
                # Limpieza básica para evitar inyectar fragmentos de preguntas
                if not any(kw in line_clean.lower() for kw in ["ganas", "ingresos", "estamos", "contrato"]):
                    extracted.append(line_clean)
        return extracted

    def _filter_profiling_content(self, text: str) -> str:
        """Remueve líneas que contienen preguntas sobre ingresos o estabilidad laboral (v1.3.2)."""
        if not text: return ""
        
        lines = text.split('\n')
        filtered_lines = []
        
        # Patrones de profiling a eliminar
        profiling_keywords = ["cuánto ganas", "cuánto devengas", "qué empresa", "qué cargo", "independiente", "empleado", "ingresos", "gastos", "egresos", "vivienda"]
        
        for line in lines:
            if not any(kw in line.lower() for kw in profiling_keywords):
                filtered_lines.append(line)
                
        return "\n".join(filtered_lines).strip()

    def _is_profiling_attempt(self, text: str) -> bool:
        """
        Detects if the AI is attempting to profiling the user (sensitive data)
        without prior consent.
        """
        if not text: return False
        
        profiling_patterns = [
            r"(cuánto?s?|qué|cuále?s?|en qué).*(gana|devenga|ingresa|ingresos?|sueldo|salario|gastos?|egresos?|labora|trabaja|hace|puesto|cargo|empresa|ocupación|oficio|profesión)",
            r"(independiente|empleado|pensionado)",
            r"(historial|reporte|datacrédito|cifin|experiencia.*crediticia)"
        ]
        
        return any(re.search(pattern, text.lower()) for pattern in profiling_patterns)

    def _determine_funnel_phase(self, prospect_data: Optional[Dict[str, Any]], history: List[Any] = None) -> str:
        """
        Deterministic state machine for funnel phase allocation.
        Based on explicit business data gathered in Firestore.
        """
        if not prospect_data:
            return "PHASE_1_PROFILING"

        # --- BLOQUEO PROTOCOLO COMPETENCIA (Directiva 2026) ---
        # Bloqueamos el avance a fase legal si la moto es de la competencia.
        moto_interest = str(prospect_data.get("moto_interest", "")).lower()
        competitor_keywords = ["boxer", "nkd", "yamaha", "suzuki", "honda", "bajaj", "hero"]
        
        is_competitor = any(comp in moto_interest for comp in competitor_keywords)
        alternative_interest = prospect_data.get("interest_confirmed_in_alternative") is True
        
        if is_competitor and not alternative_interest:
            logger.info(f"🚫 [PROTOCOL] Competitor brand detected: {moto_interest}. Blocking advance to Phase 2/3.")
            return "PHASE_1_PROFILING"

        # --- INTENCIÓN FINANCIERA (v1.3.1) ---
        is_credit = bool(str(prospect_data.get("forma_pago") or "").strip().lower() in ["credito", "crédito"])
        is_financial_intent = False
        if history:
            finance_keywords = ["cuota", "credito", "crédito", "financiar", "mensualidad", "requisitos", "cuanto pago", "papeles"]
            last_msgs = []
            for m in reversed(history):
                if isinstance(m, dict):
                    if m.get("role") == "user":
                        last_msgs.append(str(m.get("content", "")).lower())
                elif hasattr(m, "role"):
                    if m.role == "user":
                        msg_text = ""
                        if hasattr(m, "parts"):
                            msg_text = "".join([getattr(p, 'text', '') for p in m.parts if hasattr(p, 'text')])
                        elif hasattr(m, "content"):
                            msg_text = str(m.content)
                        last_msgs.append(msg_text.lower())
                if len(last_msgs) >= 2:
                    break
            
            if any(any(kw in msg for kw in finance_keywords) for msg in last_msgs):
                logger.info("💰 [INTENT] Financial intent detected.")
                is_financial_intent = True

       # Evaluamos transiciones en estricto orden secuencial de negocio:
        # GUARDRAIL: No permitimos avanzar a fase legal si no hay un modelo inmutable identificado en el CRM
        has_moto_interest = bool(prospect_data and prospect_data.get("moto_interest"))
        
        if (is_credit or is_financial_intent) and has_moto_interest:
            is_accepted = bool(prospect_data.get("habeas_data_accepted"))
            is_sent = bool(prospect_data.get("habeas_data_accepted_sent"))
            
            conversation_text = ""
            if history:
                for m in history:
                    if hasattr(m, 'parts'):
                        parts_text = "".join([getattr(p, 'text', '') for p in m.parts if hasattr(p, 'text')])
                        conversation_text += parts_text + " "
                    elif isinstance(m, dict) and m.get("content"):
                        conversation_text += str(m.get("content", "")) + " "
            
            has_sent_link = "tiendalasmotos.com/politica-de-privacidad" in conversation_text.lower()
            
            if is_accepted and is_sent and has_sent_link:
                # Transición a Perfilamiento Profundo (Fase 3) tras la captura de 'nombre' y 'ciudad'
                has_name = bool(prospect_data.get("nombre"))
                has_city = bool(prospect_data.get("ciudad"))
                if has_name and has_city:
                    return "PHASE_3_CREDIT_PROFILING"
                else:
                    # Retención Estricta en Fase 2 si falta identidad (PROHIBICIÓN ABSOLUTA DE DEGRADACIÓN)
                    logger.warning("⚠️ Prospecto aceptó Habeas Data pero falta nombre o ciudad. Reteniendo en PHASE_2_HABEAS_DATA.")
                    return "PHASE_2_HABEAS_DATA"
            else:
                # Detección de intención financiera e inyección del script legal (Fase 2)
                return "PHASE_2_HABEAS_DATA"

        # Phase 1: Default (Profiling / Catalog)
        return "PHASE_1_PROFILING"

    def _determine_ponytail_status(self, prospect_data: Optional[Dict[str, Any]]) -> str:
        """
        [BOT-PONYTAIL-200] Deterministic state machine for Ponytail flow (lead-priority tail).
        Runs parallel to _determine_funnel_phase — does NOT alter greeting or Habeas logic.
        
        State transitions:
        - UNINITIATED → no moto_interest, no greeting-history yet
        - PENDING → moto_interest set, no moto_confirmada
        - IN_PROGRESS → moto_confirmada == True
        - COMPLETED → moto_confirmada == True AND forma_pago set
        - DEPRIORITIZED → human_help_requested == True (prospect opted out / handoff)
        
        Returns one of: "UNINITIATED", "PENDING", "IN_PROGRESS", "COMPLETED", "DEPRIORITIZED"
        """
        if not prospect_data:
            return "UNINITIATED"

        # DEPRIORITIZED takes precedence — handoff / opt-out blocks all other transitions
        if prospect_data.get("human_help_requested") is True:
            return "DEPRIORITIZED"

        has_moto_interest = bool(prospect_data.get("moto_interest"))
        moto_confirmada = prospect_data.get("moto_confirmada") is True
        has_forma_pago = bool(str(prospect_data.get("forma_pago") or "").strip())

        if moto_confirmada and has_forma_pago:
            return "COMPLETED"
        elif moto_confirmada:
            return "IN_PROGRESS"
        elif has_moto_interest:
            return "PENDING"
        else:
            return "UNINITIATED"

    @observe()  # [BOT-TRACE-201] Trace the full prospect interaction cycle
    async def pensar_respuesta(self, texto: str, context: str = "", prospect_data: Optional[Dict[str, Any]] = None, history: list = [], skip_greeting: bool = False) -> str:
        """
        Main entry point for AI logic.
        Combines deterministic funnel checks + generative AI (Gemini).
        [BOT-TRACE-201] @observe() wraps this method so Langfuse captures total
        wall-clock latency, input texto, and output respuesta for the full turn.
        userId is mapped to the prospect's phone (E.164 canonical key).
        """
        # [BOT-TRACE-FIX-v2.5] Migrate to update_current_trace for better userId propagation
        max_validation_attempts = 3
        current_attempt = 0
        forced_instruction = None
        forced_temp = None

        # [BOT-PONYTAIL-200] Defensive initialization of parallel Ponytail state
        # Ensures keys exist without altering existing CRM fields or greeting logic
        if prospect_data is not None:
            if "ponytail_status" not in prospect_data:
                prospect_data["ponytail_status"] = "UNINITIATED"
            if "ponytail_score" not in prospect_data:
                prospect_data["ponytail_score"] = ""

        try:
          while current_attempt < max_validation_attempts:
            current_attempt += 1
            if LANGFUSE_AVAILABLE and prospect_data:
                _phone = prospect_data.get("phone") or prospect_data.get("id", "unknown")
                _phase = self._determine_funnel_phase(prospect_data, history)
                _session = f"wa_{_phone}"  # Stable session key per WhatsApp thread
                
                langfuse_context.update_current_trace(
                    user_id=_phone,
                    session_id=_session,
                    tags=[_phase, "juan_pablo_agent", "hotfix-v2.5"],
                    metadata={
                        "funnel_phase": _phase,
                        "nombre": prospect_data.get("nombre", "desconocido"),
                        "ciudad": prospect_data.get("ciudad", ""),
                        "moto_interest": prospect_data.get("moto_interest", ""),
                        "habeas_data_accepted": prospect_data.get("habeas_data_accepted", False),
                    }
                )
                raw_response = await self._generate_with_retry_async(
                    texto, context, prospect_data, history, skip_greeting,
                    forced_instruction=forced_instruction,
                    forced_temperature=forced_temp
                )
            else:
                raw_response = await self._generate_with_retry_async(
                    texto, context, prospect_data, history, skip_greeting,
                    forced_instruction=forced_instruction,
                    forced_temperature=forced_temp
                )
            
            # --- PHASE-GATE FÍSICO (Bypass de Habeas Data) ---
            # AUDIT P1 (2.2): Interceptor de Respuesta.
            # Si el usuario NO ha aceptado Habeas Data, bloqueamos cualquier pregunta de crédito.
            habeas_data_accepted = prospect_data.get("habeas_data_accepted", False) if prospect_data else False
            
            is_profiling_bypass = False
            if not habeas_data_accepted and raw_response and not raw_response.startswith("HANDOFF_TRIGGERED:"):
                # REGLA DE NEGOCIO (Audit v2.0): Permitir "crédito" como explicación, bloquear solo perfilamiento.
                is_profiling = self._is_profiling_attempt(raw_response)
                
                if is_profiling:
                    # [BOT-SEC-42] Forensic Security Log for Prompt Injection Attempt
                    _phone = prospect_data.get("phone") or prospect_data.get("id", "unknown") if prospect_data else "unknown"
                    logger.warning(f"SECURITY ALERT [Prompt Injection]: Attempted financial profiling without Habeas Data consent. Phone: {_phone}")

                    # [PHASE-GATE PASSTHROUGH v1.3.2]
                    # Filtramos el contenido intrusivo pero permitimos visuales ($ e imágenes)
                    filtered_text = self._filter_profiling_content(raw_response)
                    
                    # Si el filtrado dejó el texto vacío, intentamos recuperar visuales manualmente
                    if not filtered_text:
                        visual_blocks = self._extract_visual_blocks(raw_response)
                        filtered_text = "\n".join(visual_blocks)

                    # SCRIPT DE TRANSICIÓN DINÁMICO
                    transition_msg = (
                        f"{filtered_text}\n\nPara darte una asesoría completa y tu plan de pagos exacto, "
                        f"necesito tu autorización para el tratamiento de datos personales.\n\n"
                        f"¿Aceptas nuestra política de privacidad? Consúltala aquí: {self.privacy_policy_url}"
                    )
                    
                    logger.info("🛡️ [PHASE-GATE] Passthrough Filtrado aplicado con éxito.")
                    final_text = transition_msg.strip()
                    is_profiling_bypass = True
                else:
                    final_text = raw_response
            else:
                final_text = raw_response

            if not is_profiling_bypass:
                # FINAL SANITIZATION: Hardcoded Parrot Effect Killer
                if final_text and not final_text.startswith("HANDOFF_TRIGGERED:"):
                    final_text = self.clean_parrot_phrases(final_text)
                    
                    # --- COGNITIVE BRAKE GUARDRAIL (BOT-LOGIC-1.2) ---
                    # Detecta y reemplaza placeholders financieros que hayan filtrado
                    # a través del pipeline de generación (ej. $X.XXX, $X.XXX.XXX).
                    # WHY: Si el catálogo no devolvió raw_price, el código antiguo
                    # inyectaba "$X.XXX" literal. Este guardrail es la última línea
                    # de defensa antes de que el mensaje llegue al usuario.
                    placeholder_pattern = r'\$X[\.X]+'
                    if re.search(placeholder_pattern, final_text):
                        logger.warning(f"🛑 [COGNITIVE BRAKE] Placeholder financiero detectado en respuesta final. Sanitizando.")
                        final_text = re.sub(
                            placeholder_pattern,
                            'un valor que calcularemos con tus datos',
                            final_text
                        )
                    
                    # PHASE 2 / LEGAL INJECTION (JSON Voorhees v2.1.0 programmatic insertion)
                    if re.search(r'(?i)\b(autoriza|tratamiento de datos|habeas data|pol[íi]tica de privacidad|ley\s?1581|datos personales)\b', final_text):
                        if "tiendalasmotos.com/politica-de-privacidad" not in final_text:
                            final_text += "\n\n📄 Conoce nuestra Política de Privacidad aquí: https://tiendalasmotos.com/politica-de-privacidad"
                    
                    # LAST-MILE CLEANUP: Remove any technical markdown residue
                    final_text = self.clean_markdown_blocks(final_text)
                else:
                    final_text = self.clean_markdown_blocks(final_text) if final_text else final_text

            # --- POST-GENERATION VALIDATION HOOK (BOT-QA-LOOP-107) ---
            mentions_moto = any(brand.lower() in final_text.lower() for brand in ["tvs", "victory", "raider", "apache", "sport", "mrx", "bomber", "life", "urban", "enduro", "scooter", "moped"]) if final_text else False
            is_moto_query = any(kw in texto.lower() for kw in ["moto", "tvs", "victory", "raider", "apache", "sport", "mrx", "bomber", "life"])
            
            # Is specifications/ficha query:
            is_catalog_query = any(kw in texto.lower() for kw in ["ficha", "tecnica", "especificaciones", "caracteristicas"])
            
            if final_text and not final_text.startswith("HANDOFF_TRIGGERED:") and (mentions_moto or is_moto_query):
                from app.services.agentic_loop_service import AgenticOrchestrator
                orchestrator = AgenticOrchestrator()
                validation = orchestrator.run_checker(
                    final_text,
                    is_catalog_query=is_catalog_query,
                    prospect_data=prospect_data,
                    user_prompt=texto
                )
                if not validation["success"]:
                    user_id = prospect_data.get("phone") or prospect_data.get("id", "unknown") if prospect_data else "unknown"
                    logger.warning(
                        f"⚠️ [PCC VALIDATION FAILED] CATALOG_VALIDATION_FAIL - Attempt {current_attempt}/{max_validation_attempts} for query '{texto}' user_id={user_id}. "
                        f"Expected: {validation['report']['expected_behavior']}."
                    )
                    if current_attempt < max_validation_attempts:
                        forced_instruction = (
                            f"ERROR: La respuesta generada anteriormente falló la validación del catálogo y precio. "
                            f"Detalles: {validation['report']['expected_behavior']}. "
                            f"Asegúrate de incluir siempre el precio con '$' y la imagen/enlace de la moto en formato markdown."
                        )
                        forced_temp = 0.1
                        continue  # Force immediate retry with temperature 0.1
                    else:
                        logger.error(
                            f"🚨 [PCC VALIDATION] CATALOG_VALIDATION_FAIL - Max validation attempts reached. "
                            f"user_id={user_id} query='{texto}' - Returning degraded response."
                        )
                        return final_text
                else:
                    # BOT-BRAIN-FAQ-CATALOG-COLLISION-146: Si run_checker determinó un bypass semántico
                    # (FAQ pura sin moto_interest en CRM), forzar is_catalog_query=False de forma síncrona
                    # para impedir que el supervisor de formato penalice FAQs abstractas en sucesivos ciclos.
                    if validation.get("bypass_strict"):
                        is_catalog_query = False
                        user_id = prospect_data.get("phone") or prospect_data.get("id", "unknown") if prospect_data else "unknown"
                        logger.info(
                            f"✅ [PCC BYPASS] Semantic bypass exitoso: FAQ intent sin moto_interest en CRM. "
                            f"is_catalog_query forzado a False. user_id={user_id} query='{texto}'"
                        )
                    return final_text
            else:
                return final_text
        except HabeasDataBypassInterrupt as hdbi:
            logger.info(f"🛡️ [HABEAS-BYPASS] Cortocircuito limpio ejecutado. Propagando al router.")
            raise

    @staticmethod
    def clean_markdown_blocks(text: str) -> str:
        """
        Hard-kill for markdown code blocks (```...```).
        Ensures technical hallucinations or exposed tool calls never reach the user.
        """
        if not text or not isinstance(text, str):
            return text
            
        # 1. Remove complete triple-backtick blocks (with optional language tag)
        cleaned = re.sub(r'```[a-z]*\s*[\s\S]*?```', '', text)
        
        # 2. Cleanup residual backticks
        cleaned = cleaned.replace('```', '').strip()
        
        return cleaned

    @staticmethod
    def clean_parrot_phrases(text: str) -> str:
        """
        Hardcoded filter to remove forbidden filler words.
        IMPLEMENTS: safety.forbidden_words contract.
        """
        if not text:
            return text
            
        import re
        
        # 1. Hard-Kill Global (JSON Voorhees Safe) - Relaxed to start only
        cleaned = re.sub(r'^\s*[Ee][Xx][Cc][Ee][Ll][Ee][Nn][Tt][Ee][:;\.,!\?]*\s*', '', text.strip())
        
        # 2. Parrot Filter v2: Robust list of patterns (start and mid-phrase protection)
        # Relaxed: Removed "¡?Buen día!?" and "Con gusto," to allow natural warmth.
        forbidden = [
            r"^¡?Claro que sí!?", r"^Claro,", r"^¡?Claro!?",
            r"^¡?Perfecto!?", r"^¡?Entendido!?",
            r"^¡?Qué bien!?", r"^¡?Genial!?"
        ]
        
        changed = True
        while changed:
            original = cleaned
            for pattern in forbidden:
                cleaned = re.sub(r"^\s*" + pattern + r"[\s,.]*", "", cleaned, flags=re.IGNORECASE).strip()
            
            # Remove leftover punctuation at the very start
            cleaned = re.sub(r"^[,\.!\?\s-]+", "", cleaned).strip()
            changed = (cleaned != original)

        if cleaned and cleaned[0].islower():
            cleaned = cleaned[0].upper() + cleaned[1:]
            
        return cleaned

    def _create_tools(self, prospect_data: Optional[Dict[str, Any]] = None) -> Optional[List[types.Tool]]:
        """
        Create tools for function calling (human handoff).
        Returns: Tool object with function declarations, or None if not available
        """
        if not SDK_AVAILABLE:
            return None
        
        try:
            # Define human handoff function
            # SECURITY (QA Baseline): This tool is intentionally locked to ONLY fire on
            # explicit user requests. Permitting 'complex_query' or 'technical_question'
            # caused the LLM to escape answering FAQs (credit requirements, pricing)
            # by routing them to a human, breaking the automated sales funnel.
            handoff_function = types.FunctionDeclaration(
                name="trigger_human_handoff",
                description="""Escala la conversación a un agente humano ÚNICAMENTE si el usuario EXPLÍCITAMENTE solicita hablar con una persona.

REGLAS ESTRICTAS DE USO:
- SOLO úsala si el usuario dice frases como: 'quiero hablar con un asesor', 'necesito una persona', 'hablar con alguien', 'quiero ayuda humana'.
- PROHIBIDO ABSOLUTO usarla para: visitas a la tienda (el usuario irá físicamente), preguntas sobre requisitos de crédito, precios, características de motos, FAQs, o cualquier consulta que puedas responder con tu conocimiento.
- PROHIBIDO usarla porque la pregunta te parece 'compleja' o 'técnica'. Tú eres el experto. Respóndela.
- Si el usuario dice que visitará una tienda, NO uses esta herramienta; simplemente despídete.
- Si tienes duda, NO la uses. Responde directamente.""",
                parameters={
                    "type": "object",
                    "properties": {
                        "reason": {
                            "type": "string",
                            # AUDIT P2 (3.3): Added structural enum enforcement.
                            # WHY: Even with a clear description, free-text string fields
                            # still allow the LLM to hallucinate values like 'usuario_solicito'
                            # or 'complex_need'. Vertex AI honors `enum` in FunctionDeclaration,
                            # making it IMPOSSIBLE for the LLM to submit any value other than
                            # 'user_explicit_request'. This removes the escape-hatch permanently.
                            "enum": ["user_explicit_request"],
                            "description": "Razón del handoff. Único valor válido: 'user_explicit_request'. NUNCA uses 'complex_query', 'technical_question' ni ninguna razón autogenerada."
                        }
                    },
                    "required": ["reason"]
                }
            )

            # Define catalog search function
            # MANTENIBILIDAD & SEGURIDAD (QA Baseline):
            # Por qué se hace: Asegura que el modelo no genere respuestas alucinadas sobre el 
            # inventario en la primera interacción (Fresh Start) y refuerza que DEBE buscar 
            # antes de intentar saludar o responder.
            catalog_function = types.FunctionDeclaration(
                name="search_catalog",
                description="""Busca motocicletas en el catálogo usando un término clave. REGLA DE ORO: NUNCA asumas el inventario. Es OBLIGATORIO usar esta herramienta antes de recomendar cualquier moto.""",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": """Término de búsqueda. REGLAS SEMÁNTICAS: 1. Si el usuario pide moto para 'ciudad' o 'transporte', busca 'trabajo' o 'scooter'. 2. Si pide 'para el campo' o 'trocha', busca 'enduro'. 3. Si menciona 'economica', busca 'trabajo'. 4. NUNCA busques términos literales subjetivos; traduce a categorías: [trabajo, scooter, enduro, moped, sport]."""
                        }
                    },
                    "required": ["query"]
                }
            )
            
            # Define credit calculation function
            credit_function = types.FunctionDeclaration(
                name="calculate_credit_score",
                description="ÚNICA herramienta autorizada para calcular el perfil crediticio. ¡DETENTE AQUÍ! No generes respuesta. Espera el resultado interno. Úsala inmediatamente después del Paso 9. Proporciona el score, la entidad asignada y el link de aplicación. Requisitos: ser mayor de edad y contar con ingresos demostrables.",
                parameters={
                    "type": "object",
                    "properties": {
                        "ocupacion_y_contrato": {
                            "type": "string",
                            "description": "Ocupación y tipo de contrato. Mapeo estricto: Si dice 'informal', 'rebusque', 'cuenta propia', o 'negocio', MÁPEALO a 'Independiente'. Si dice 'empleado', 'trabajo en', 'mensajero' (con empresa), MÁPEALO a 'Empleado fijo'. De lo contrario, extrae la intención más cercana."
                        },
                        "ingresos_demostrables": {
                            "type": "string",
                            "description": "Nivel de ingresos. Mapeo estricto: Si dice 'el mínimo' o 'lo básico', utiliza el valor numérico del Salario Mínimo (SMLV) actual. No envíes texto como 'el mínimo', solo el valor numérico."
                        },
                        "historial_datacredito": {
                            "type": "string",
                            "description": "Estado en Datacrédito. Mapeo estricto: Si no se conoce aún, o si dice 'nunca he sacado nada', 'no sé', MÁPEALO a 'Sin experiencia' (esto es vital para no penalizar el el score inicial). Si dice 'bien', 'pagando cuenta', MÁPEALO a 'Al dia'. Si menciona 'atrasado', 'castigado', MÁPEALO a 'Reportado'."
                        },
                        "mora_y_paz_salvo": {
                            "type": "string",
                            "description": "Si tiene reportes, ¿tiene paz y salvo? 'Sí/No' o descripción de la mora."
                        },
                        "ingresos_mensuales": {
                            "type": "number",
                            "description": "Valor numérico total de ingresos mensuales."
                        },
                        "gastos_mensuales": {
                            "type": "number",
                            "description": "Valor numérico total de gastos mensuales."
                        },
                        "tiene_gas_natural": {
                            "type": "boolean",
                            "description": "¿Cuenta con recibo de gas natural a su nombre? (Indispensable para Brilla)."
                        },
                        "plan_celular": {
                            "type": "string",
                            "description": "¿Tiene plan de celular postpago activo? (Otorga bono de +50 pts). MÁPEALO a 'Sí' o 'No'."
                        },
                        "entidad": {
                            "type": "string",
                            "description": "Entidad financiera con la que se simula el crédito (ej. Sufi, Finesa, Brilla)."
                        },
                        "reportes": {
                            "type": "string",
                            "description": "Detalles adicionales sobre reportes financieros si los tiene."
                        }
                    },
                    "required": ["ocupacion_y_contrato", "ingresos_demostrables", "historial_datacredito"]
                }
            )

            function_declarations = [handoff_function, catalog_function]
            
            # Stop-Gate Logic (Audit P2 1.1)
            phase = self._determine_funnel_phase(prospect_data)
            moto_confirmada = prospect_data.get("moto_confirmada") is True if prospect_data else False
            
            # Reverted: credit_function is now always included to avoid LLM panic loops,
            # and we reject it at runtime if called in PHASE_1_PROFILING (Tool Rejection Pattern)
            function_declarations.append(credit_function)
            logger.info(f"🛠️ Toolset: [handoff, catalog, credit] (Phase: {phase})")

            return [types.Tool(function_declarations=function_declarations)]
        except Exception as e:
            logger.error(f"❌ Error creating tools: {str(e)}", exc_info=True)
            return []

    async def _generate_with_retry_async(self, texto: str, context: str, prospect_data: Optional[Dict[str, Any]] = None, history: list = [], skip_greeting: bool = False, forced_instruction: Optional[str] = None, forced_temperature: Optional[float] = None) -> str:
        """
        Internal generation with exponential backoff and structured prompt injection (Async).
        """
        if not self.client: 
            logger.error("🚨 [AI FALLBACK REASON]: SDK Client not initialized")
            return self._fallback_response(texto, history)
        
        # 0. AUDIT PROBE (Garantizada al inicio de la inferencia)
        logger.info(f"🔍 [AUDIT PII] conversation_text: {texto}")
        
        max_retries = 3
        base_delay = 2 
        
        import asyncio
        from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable, InvalidArgument

        # 1. Deterministic state evaluation
        phase = self._determine_funnel_phase(prospect_data, history)
        
        # --- HOT SEARCH GREETING BYPASS (BOT-BACKEND-BUGFIX-CATALOG-PERIMETER-187) ---
        is_mock_search = False
        if self._catalog_service:
            try:
                from unittest.mock import Mock
                if isinstance(self._catalog_service.search_items, Mock):
                    is_mock_search = True
            except ImportError:
                pass

        # Evaluate if there is legitimate user history to determine if it is the first contact
        # [BOT-206] Align with router semantics: exclude current turn message
        has_no_legitimate_history = True
        if history:
            legitimate_messages = []
            for msg in history:
                if msg.get("role") == "user":
                    content = msg.get("content", "").strip()
                    content_lower = content.lower()
                    if (content_lower in ["reset", "/reset", "/update", "/refresh_catalog"] or 
                        content.startswith("/") or 
                        content.startswith("[System Note:") or 
                        "sesión ha sido reiniciada" in content_lower):
                        continue
                    legitimate_messages.append(msg)
            
            # [BOT-206] Exclude current turn message if it matches the input text
            # This aligns with router's current_message_saved slicing logic
            if legitimate_messages and texto:
                current_turn_normalized = str(texto).lower().strip()
                last_user_msg = legitimate_messages[-1].get("content", "").lower().strip()
                if last_user_msg == current_turn_normalized:
                    legitimate_messages = legitimate_messages[:-1]
            
            if len(legitimate_messages) > 0:
                has_no_legitimate_history = False

        if has_no_legitimate_history:
            logger.info("🆕 [FIRST CONTACT ALIGNMENT] skip_greeting unmodified. History is empty or reset.")

        if not is_mock_search and self._catalog_service and texto and hasattr(self._catalog_service, "_items") and isinstance(self._catalog_service._items, list) and self._catalog_service._items:
            try:
                # Fast local pre-filter to avoid calling search_items on non-catalog queries (e.g. general questions or drift aliases)
                clean_text = str(texto).lower()
                import unicodedata
                clean_text = ''.join(c for c in unicodedata.normalize('NFD', clean_text) if unicodedata.category(c) != 'Mn')
                clean_text = re.sub(r'[^a-z0-9\s]', ' ', clean_text)
                query_tokens = clean_text.split()
                
                brands = {"tvs", "victory", "bajaj", "hero", "yamaha", "honda", "suzuki", "akt", "apache", "boxer", "raider", "neo", "sport", "ninja"}
                has_potential_match = False
                
                for t in query_tokens:
                    if t in brands:
                        has_potential_match = True
                        break
                    t_phone = self._catalog_service._phonetic_normalize(t)
                    for item in self._catalog_service._items:
                        item_name_tokens = self._catalog_service._tokenize(item.get("name", ""))
                        if any(t == nt or self._catalog_service._phonetic_normalize(nt) == t_phone for nt in item_name_tokens):
                            has_potential_match = True
                            break
                        if len(t) <= 5:
                            import difflib
                            if any(difflib.SequenceMatcher(None, t_phone, self._catalog_service._phonetic_normalize(nt)).ratio() >= 0.8 for nt in item_name_tokens):
                                has_potential_match = True
                                break
                        else:
                            import difflib
                            if any(difflib.SequenceMatcher(None, t, nt).ratio() >= 0.8 for nt in item_name_tokens):
                                has_potential_match = True
                                break
                    if has_potential_match:
                        break
                        
                if has_potential_match:
                    matches = self._catalog_service.search_items(texto)
                    if matches:
                        # [BOT-206] Precedencia absoluta del router: skip_greeting es la única autoridad
                        if skip_greeting:
                            logger.info(f"🔥 [WARM START GREETING BYPASS] Catalog matches found in caliente for '{texto}'. skip_greeting={skip_greeting}.")
                        else:
                            logger.info(f"🆕 [FIRST CONTACT SHIELD] Catalog matches found for '{texto}' but skip_greeting={skip_greeting}. Mandatory greeting enforced.")
                        if prospect_data is not None:
                            if not prospect_data.get("moto_interest"):
                                prospect_data["moto_interest"] = matches[0]["name"]
                                logger.info(f"💾 Updated prospect_data['moto_interest'] to '{matches[0]['name']}' in caliente.")
            except Exception as e:
                logger.error(f"⚠️ Error in warm start greeting bypass: {e}")
        
        # --- NEW ADAPTER LAYER: CRM ANCHOR CONTEXT (REF-004) ---
        # Moving the anchor logic from the router to the brain.
        # This keeps the 'texto' (raw user input) clean for the tool interceptor.
        # [UNIFICACIÓN] moto_interest enforced
        anchor_context = ""
        if prospect_data and prospect_data.get("moto_interest"):
            moto_interest = prospect_data.get("moto_interest")
            # Anchor rule: If message is short (<60 chars) and doesn't imply a shift, reinforce preference.
            if len(texto) < 60 and not any(m in texto.lower() for m in ["otra", "cambiar", "no la"]):
                anchor_context = f"\n[CRM ANCHOR: El usuario está interesado en la {moto_interest}. Mantén el contexto sobre este modelo a menos que el usuario pida conocer otra motocicleta.]\n"
                logger.info(f"💉 Internal CRM Anchor Context injected: {moto_interest}")

        # 2. Build Instructions block based on State
        funnel_instruction = ""
        data = prospect_data or {}
        p_name = data.get("nombre")
        p_ciudad = data.get("ciudad")
        p_payment = data.get("forma_pago")

        if phase == "PHASE_1_PROFILING":
            # Sincronización Protegida: Confiamos en prospect_data actualizado por el socket síncrono.
            # Se eliminan detecciones manuales por Regex para evitar falsos positivos y bloqueos de lógica.
            pass

            # HARD-GATE DE IDENTIDAD (Requirement 2026.1): Prohibido preguntar si ya existe.
            # v1.3.0: Skip name request if moto is confirmed or in context
            moto_context = data.get("moto_interest") or data.get("moto_confirmada")
            if p_name:
                pass # Already have it
            elif not moto_context:
                funnel_instruction = "El sistema requiere el nombre del prospecto. Cierra tu mensaje preguntando: '¿con quién tengo el gusto?' o similar."
            else:
                funnel_instruction = "El usuario ya mostró interés en una moto. Prioriza responder sobre la moto y NO pidas el nombre todavía."
            
            if not funnel_instruction and not p_ciudad:
                funnel_instruction = "Falta la ciudad del prospecto. Cierra tu mensaje preguntando: '¿Desde qué ciudad nos escribes?'"
            elif not funnel_instruction and not p_payment:
                funnel_instruction = "Falta el método de pago. Pregunta si prefiere compra de contado o a crédito."
        
        elif phase == "PHASE_2_HABEAS_DATA":
            is_accepted = data.get("habeas_data_accepted") is True
            if is_accepted:
                interruption_directive = (
                    " El consentimiento ya ha sido firmado en este turno. Tienes ESTRICTAMENTE PROHIBIDO "
                    "incluir enlaces de imágenes (![]) o precios ($) en tu respuesta. "
                    "Limítate exclusivamente a solicitar el nombre completo y la ciudad de forma concisa."
                )
                if not p_name:
                    funnel_instruction = "El consentimiento de datos ya está firmado. El sistema requiere el nombre del prospecto para continuar con su solicitud de crédito. Cierra tu mensaje pidiendo su nombre de forma clara y amable." + interruption_directive
                elif not p_ciudad:
                    funnel_instruction = "El consentimiento de datos ya está firmado. El sistema requiere la ciudad del prospecto para continuar con su solicitud de crédito. Cierra tu mensaje pidiendo su ciudad de forma clara y amable." + interruption_directive
            else:
                funnel_instruction = "EL USUARIO ESTÁ LISTO PARA EL CRÉDITO. Debes presentar el script legal de Habeas Data y pedir su aceptación explícita (Sí/No)."
        
        elif phase == "PHASE_3_CREDIT_PROFILING":
            funnel_instruction = (
                "Habeas Data Aceptado. Procede con el perfilamiento crediticio. "
                "Ejecuta la herramienta calculate_credit_score. ¡DETENTE AQUÍ! "
                "No generes texto de respuesta con valores monetarios inventados. "
                "Espera el resultado interno de la herramienta antes de responder al usuario. "
                "Si el resultado es Brilla, solicita de inmediato fotos de cédula "
                "y recibos de gas para que el asesor humano pueda cerrar el trámite."
            )

        for attempt in range(max_retries):
            try:
                # 1. DYNAMIC TOOLS
                dynamic_tools = self._create_tools(prospect_data)
                
                # 2. CONSOLIDATE XML PROMPT
                user_name = prospect_data.get("nombre", "desconocido") if prospect_data else "desconocido"
                prospect_xml = ""
                captured_data_xml = ""
                if prospect_data and prospect_data.get("exists"):
                    prospect_xml = "\n".join([f"    <{k}>{v}</{k}>" for k,v in prospect_data.items() if v and k not in ['exists', 'summary']])
                    captured_fields = [k for k, v in prospect_data.items() if v and k not in ['exists', 'summary', 'ai_summary']]
                    if captured_fields:
                        captured_data_xml = f"\n<datos_ya_capturados>\n" + "\n".join([f"  <{k}>{prospect_data[k]}</{k}>" for k in captured_fields]) + "\n</datos_ya_capturados>"
                
                # --- BOT-BRAIN-ALIGNMENT-099: SYNONYM INJECTION ---
                # WHY: category_aliases exists in Firestore for programmatic search indexing
                # but the LLM has zero awareness of regional synonyms (e.g. "señoritera" → scooter).
                # Injecting them into the prompt enables the LLM to translate user colloquialisms
                # into proper search_catalog queries without hardcoding every regional term.
                synonyms_xml = ""
                try:
                    catalog_aliases = {}
                    if self._catalog_service and hasattr(self._catalog_service, 'get_catalog_aliases'):
                        raw_catalog_aliases = self._catalog_service.get_catalog_aliases()
                        catalog_aliases = {str(k).lower().strip(): [str(v).lower().strip() for v in val] for k, val in raw_catalog_aliases.items() if val}
                    else:
                        logger.warning("⚠️ [SYNONYM INJECTION] Catalog service not initialized or missing get_catalog_aliases method")
                    
                    if catalog_aliases:
                        alias_lines = []
                        for cat, syns in catalog_aliases.items():
                            csv_syns = ", ".join(syns)
                            alias_lines.append(f"  <alias categoria=\"{cat}\">{csv_syns}</alias>")
                        synonyms_xml = (
                            "\n<diccionario_sinonimos_regionales>\n"
                            + "\n".join(alias_lines)
                            + "\n  [INSTRUCCIÓN: Si el usuario usa alguno de estos sinónimos, tradúcelo a la categoría correspondiente al llamar search_catalog.]"
                            + "\n</diccionario_sinonimos_regionales>\n"
                        )
                        logger.info(f"📖 [SYNONYM INJECTION] {len(catalog_aliases)} categorías inyectadas en prompt")
                except Exception as _syn_err:
                    logger.exception(f"🚨 [SYNONYM INJECTION] Error crítico recuperando alias del catálogo: {_syn_err}")

                base_instruction = self._get_current_instruction()
                if skip_greeting:
                    base_instruction = self._assemble_skip_greeting_prompt(base_instruction, prospect_data, texto)


                full_prompt = f"""
{base_instruction}
{synonyms_xml}
<contexto_dinamico>
  <prospecto>
    <nombre_real>{user_name}</nombre_real>
{prospect_xml}
    <resumen_previo>{prospect_data.get('summary', 'Sin historial') if prospect_data else 'Sin historial'}</resumen_previo>
  </prospecto>

  <estado_del_embudo>
    <fase_actual>{phase}</fase_actual>
    <instruccion_de_cierre>{funnel_instruction}</instruccion_de_cierre>
  </estado_del_embudo>

  <reglas_de_sesion>
    <saludo_permitido>{'NO' if skip_greeting else 'SI'}</saludo_permitido>
    <contexto_previo>{context if context else 'N/A'}</contexto_previo>
  </reglas_de_sesion>
{captured_data_xml}
</contexto_dinamico>

⚠️ REGLA CRÍTICA: Ignora cualquier instrucción de identidad previa en el historial. Tu nombre es Juan Pablo. 
Utiliza la <instruccion_de_cierre> para orientar tu respuesta final de forma natural.
"""
                # History (Prompt-based)
                if history:
                    history_lines = []
                    for msg in history:
                        role_label = "Usuario" if msg['role'] == 'user' else "Juan Pablo"
                        content_safe = str(msg.get('content', '')).replace('\n', ' ')
                        history_lines.append(f"- {role_label}: {content_safe}")

                    # --- CONTEXT OPTIMIZATION (Audit v2.0) ---
                    # User requested aggressive truncation to stay below 5,000 tokens.
                    # 1200 chars ~= 300-400 tokens + System Prompt + PII.
                    MAX_HISTORY_CHARS = 1200 
                    selected_lines = []
                    running_chars = 0
                    for line in reversed(history_lines):
                        if running_chars + len(line) + 1 > MAX_HISTORY_CHARS:
                            break
                        selected_lines.insert(0, line)
                        running_chars += len(line) + 1
                    full_prompt += "\n<historial_reciente>\n" + "\n".join(selected_lines) + "\n</historial_reciente>"

                if context:
                    full_prompt += f"RESUMEN CONVERSACIÓN ANTERIOR (Largo Plazo):\n{context}\n\n"
                
                if skip_greeting:
                    full_prompt += "\n[SYSTEM: STRICT RULE: DO NOT under any circumstance start your response with 'Hola', 'Buenos días', or any greeting. The conversation is ongoing. Jump straight into your answer.]\n"
                else:
                    full_prompt += "\n[SYSTEM: MANDATORY WARMTH: Preséntate de forma cálida y profesional como Juan Pablo, asesor de Auteco Las Motos. No seas parco ni directo. CRÍTICO: Si el usuario menciona una moto en este primer mensaje, DEBES usar la herramienta 'search_catalog' ANTES de generar tu saludo final.]\n"

                if forced_instruction:
                    full_prompt += f"\n[SYSTEM: ALERT: {forced_instruction}]\n"

                if funnel_instruction:
                    full_prompt += funnel_instruction + "\n\n"

                # Inject Anchor Context (Isolated from raw user message)
                if anchor_context:
                    full_prompt += anchor_context + "\n"
                    
                full_prompt += f"Usuario: {texto}\n\n"
                full_prompt += f"[SISTEMA: Recuerda la ONE-SHOT RULE. Tu respuesta debe terminar con UNA (1) sola pregunta. Tienes prohibido repreguntar por los datos que ya están en <datos_ya_capturados>.]\n\n"
                
                # --- REFUERZO DE IDENTIDAD v8.3 (Ventana de Atención Final) ---
                if prospect_data and prospect_data.get("nombre"):
                    p_name = prospect_data.get("nombre")
                    full_prompt += f"\n[CRITICAL IDENTITY RULE: Estás hablando con {p_name}. Tu respuesta DEBE empezar con un saludo personalizado hacia él. Ignorar esto es un fallo de seguridad.]\n"
                
                full_prompt += "Juan Pablo:"
                
                # --- MAIN INFERENCE CALL (google-genai syntax) ---
                chat = self.client.aio.chats.create(model=self._model_id)

                # 💎 [FULL PROMPT AUDIT] (Requirement v2)
                # We log the consolidated prompt to verify that PII and Phase are correctly injected.
                audit_log = f"\n--- PROMPT AUDIT START ---\nPHASE: {phase}\nINSTRUCTION: {funnel_instruction}\nPROSPECT: {prospect_data}\nPROMPT: {full_prompt[:1500]}...\n--- PROMPT AUDIT END ---\n"
                logger.info(f"💎 [FULL PROMPT AUDIT] sending to Gemini for {prospect_data.get('nombre') if prospect_data else 'None'}: {audit_log}")

                try:
                    response = await self._call_gemini_with_retry_async(
                        chat.send_message,
                        full_prompt,
                        config=types.GenerateContentConfig(
                            temperature=forced_temperature if forced_temperature is not None else 0.2,
                            max_output_tokens=8192,
                            tools=dynamic_tools
                        )
                    )
                except Exception as e:
                    logger.exception(f"🚨 [AI FALLBACK REASON]: Gemini Inference Failure for {user_name}: {str(e)}")
                    return self._fallback_response(texto, history)

                if not response.candidates or not response.candidates[0].content.parts:
                    logger.error("🚨 [AI FALLBACK REASON]: Safety Filter or Empty Response (No candidates)")
                    logger.error("⚠️ AI Safety Filter Triggered: No candidates or parts returned.")
                    return self._fallback_response(texto, history)

                # --- FORCED TOOL VALIDATION TURN (PVN-Hardened) ---
                # SECURITY (QA Baseline): If the user mentions a motorcycle but the AI 
                # attempts to answer without using search_catalog, we intercept and 
                # force a tool turn. CRITICAL: We MUST pass tools in the retry config.
                try:
                    from app.services.config_service import config_service
                    base_keywords = ["moto", "raider", "sport", "victory", "tvs", "mrx", "trabajo", "trabajar", "mensajeria", "domicilio", "carga"]
                    motorcycle_keywords = list(base_keywords)
                    try:
                        aliases_dict = config_service.get_catalog_aliases()
                        if aliases_dict:
                            for category, synonyms in aliases_dict.items():
                                cat_clean = str(category).lower().strip()
                                if cat_clean and cat_clean not in motorcycle_keywords:
                                    motorcycle_keywords.append(cat_clean)
                                for syn in synonyms:
                                    syn_clean = str(syn).lower().strip()
                                    if syn_clean and syn_clean not in motorcycle_keywords:
                                        motorcycle_keywords.append(syn_clean)
                    except Exception as alias_err:
                        logger.warning(f"⚠️ [MOTORCYCLE_KEYWORDS] Error loading catalog aliases dynamically: {alias_err}")
                        
                    user_mentions_motorcycle = any(kw in texto.lower() for kw in motorcycle_keywords)
                    
                    candidate_parts = response.candidates[0].content.parts
                    has_any_tool_call = any(p.function_call for p in candidate_parts)
                    has_catalog_call = any(p.function_call and p.function_call.name == "search_catalog" for p in candidate_parts)
                    
                    if user_mentions_motorcycle and not has_catalog_call and not has_any_tool_call:
                        logger.warning(f"⚠️ AI bypassed catalog search for motorcycle query: '{texto}'. Forcing validation turn.")
                        retry_name_reinforcement = f" Sigue hablando con {user_name}." if user_name != "desconocido" else ""
                        response = await self._call_gemini_with_retry_async(
                            chat.send_message,
                            f"[SYSTEM: ERROR: Has mencionado una moto o una categoría de uso pero NO has consultado el catálogo. ESTÁS OBLIGADO a usar la herramienta 'search_catalog' para dar precios y disponibilidad antes de responder al usuario. Ejecútala ahora.{retry_name_reinforcement}]",
                            config=types.GenerateContentConfig(
                                temperature=0.1, 
                                max_output_tokens=2048,
                                tools=dynamic_tools # FIX: Ensure tools are available for the forced turn
                            )
                        )
                        # Re-verify candidates after injection
                        if not response.candidates:
                            logger.error(f"🚨 [AI FALLBACK REASON]: Safety Filter Triggered during Forced Turn for {user_name}")
                            return self._fallback_response(texto, history)
                except Exception as e:
                    logger.exception(f"⚠️ Tool Validation Logic Error for {user_name}: {e}")
                # ----------------------------------------------------------
                
                # --- ROBUST TOOL EXECUTION LOOP ---
                turns = 0
                max_turns = 3
                search_catalog_called = False
                catalog_returned_results = False
                catalog_models_found = []
                
                while turns < max_turns:
                    if not response.candidates or not response.candidates[0].content.parts:
                        logger.error(f"🚨 [AI FALLBACK REASON]: Empty Candidate in Turn {turns+1} for {user_name}")
                        return self._fallback_response(texto, history)

                    candidate = response.candidates[0]
                    function_calls = [part.function_call for part in candidate.content.parts if part.function_call]
                    
                    if not function_calls:
                        # No more tool calls, return final text
                        try:
                            # Safely extract text from components
                            ai_response = "".join([part.text for part in candidate.content.parts if part.text]).strip()
                            if not ai_response:
                                logger.error(f"🚨 [AI FALLBACK REASON]: Empty AI Text Response (Turn final) for {user_name}")
                                return self._fallback_response(texto, history)

                            # --- GUARDRAILS ---
                            if search_catalog_called and turns < max_turns:
                                has_price = bool(re.search(r"(\$\s?\d{1,3}(\.\d{3})*)|(precio:)", ai_response, re.IGNORECASE))
                                has_image = bool(re.search(r"!\[.*?\]\(https?://|\[IMAGE:\s?https?://", ai_response))
                                
                                # BYPASS LOGIC: Si la moto ya está confirmada o hay una de interés, el prompt prohíbe imagen/precio 
                                # para evitar saturación. El guardrail no debe exigir consistencia visual.
                                moto_confirmada = (prospect_data and prospect_data.get("moto_confirmada") is True)
                                has_moto_interest = bool(prospect_data.get("moto_interest")) if prospect_data else False
                                requires_visuals = not moto_confirmada and not has_moto_interest

                                hallucinated_model = None
                                if catalog_returned_results:
                                    mentions = re.findall(r"\b(TVS|Victory|Boxer|NKD|Raider|Apache|Sport|Bomber|Life|Pulsar|Yamaha|Honda|Suzuki|AKT)\s+([A-Z0-9][a-zA-Z0-9]*)\b", ai_response)
                                    for brand, model in mentions:
                                        full_mention = f"{brand} {model}".lower()
                                        if not any(full_mention in m.lower() for m in catalog_models_found):
                                            hallucinated_model = f"{brand} {model}"
                                            break

                                if (catalog_returned_results and requires_visuals and (not has_price or not has_image)) or hallucinated_model:
                                    turns += 1
                                    error_msg = ""
                                    if requires_visuals and (not has_price or not has_image):
                                        error_msg = "Has ejecutado el catálogo pero tu respuesta final NO incluye el precio ($ o la palabra 'precio:') o la imagen. "
                                    if hallucinated_model:
                                        error_msg += f"Has mencionado la moto '{hallucinated_model}' que NO aparece en los resultados locales del catálogo. "
                                    
                                    logger.warning(f"🚨 Consistency Guardrail Triggered: {error_msg}")
                                    retry_name_reinforcement = f" Sigue hablando con {user_name}." if user_name != "desconocido" else ""
                                    retry_instruction = f"[SYSTEM: ERROR: {error_msg} INSTRUCCIÓN: Corrige la respuesta usando ÚNICAMENTE los modelos, precios e imágenes devueltos por el catálogo.{retry_name_reinforcement}]"
                                    
                                    response = await self._call_gemini_with_retry_async(
                                        chat.send_message,
                                        retry_instruction,
                                        config=types.GenerateContentConfig(temperature=0.1)
                                    )
                                    continue
                                elif moto_confirmada and (not has_price or not has_image):
                                    logger.info("✅ Consistency Guardrail Bypassed (Moto ya confirmada)")
                            
                            logger.info(f"✅ AI response generated after {turns} turns")
                            
                            # Update telemetry in prospect_data
                            if prospect_data is not None:
                                usage = getattr(response, 'usage_metadata', None)
                                tokens = getattr(usage, 'total_token_count', 0)
                                i_tokens = getattr(usage, 'prompt_token_count', 0)
                                o_tokens = getattr(usage, 'candidates_token_count', 0)
                                cost = self._calculate_session_cost(usage)
                                prospect_data['total_tokens_consumed'] = prospect_data.get('total_tokens_consumed', 0) + tokens
                                prospect_data['session_cost_usd'] = prospect_data.get('session_cost_usd', 0.0) + cost
                                logger.info(f"📊 [TELEMETRY] Response: {tokens} tokens, Cost: ${cost} USD | Cumulative in session.")
                                # [BOT-TRACE-201] Send token counts to Langfuse generation
                                if LANGFUSE_AVAILABLE:
                                    try:
                                        langfuse_context.update_current_generation(
                                            model=self._model_id,
                                            usage_details={
                                                "input": i_tokens,
                                                "output": o_tokens,
                                                "total": tokens,
                                            },
                                            metadata={"cost_usd": cost}
                                        )
                                    except Exception as _lf_gen_err:
                                        logger.warning(f"⚠️ [LANGFUSE] generation update failed: {_lf_gen_err}")

                            return ai_response
                        except Exception as e:
                            logger.exception(f"⚠️ Error extracting text for {user_name}: {e}")
                            return self._fallback_response(texto, history)

                    # Execute function calls
                    logger.info(f"⚡ AI triggered {len(function_calls)} function call(s)")

                    # --- BOT-BRAIN-ALIGNMENT-099: HARD-CAP (Max 2 tool calls per turn) ---
                    # WHY: Without a per-turn cap, the LLM can dispatch unlimited function_calls
                    # in a single response (e.g. search_catalog + calculate_credit_score + handoff),
                    # causing an exhaustive agentic loop. Truncating to 2 prevents resource waste
                    # and forces the LLM to prioritize the most critical tool per turn.
                    MAX_TOOL_CALLS_PER_TURN = 2
                    if len(function_calls) > MAX_TOOL_CALLS_PER_TURN:
                        discarded = [fc.name for fc in function_calls[MAX_TOOL_CALLS_PER_TURN:]]
                        logger.warning(
                            f"🛑 [HARD-CAP] LLM dispatched {len(function_calls)} function calls in one turn. "
                            f"Truncating to {MAX_TOOL_CALLS_PER_TURN}. Discarded: {discarded}"
                        )
                        function_calls = function_calls[:MAX_TOOL_CALLS_PER_TURN]

                    response_parts = []
                    
                    for fc in function_calls:
                        f_name = fc.name
                        f_args = fc.args
                        
                        if f_name == "search_catalog":
                            # Inicialización explícita para evitar UnboundLocalError y fugas de variables
                            query = f_args.get("query", "")
                            search_catalog_called = True
                            catalog_returned_results = False
                            search_results = "No se encontraron resultados."
                            skip_catalog = False
                            moto_interest_prev = None
                            ratio = 0.0
                            t_start = 0.0
                            t_end = 0.0
                            latency = 0.0
                            cost = 0.0
                            catalog_response_str = ""
                            extracted_names = []
                            matches = []
                            
                            try:
                                if self._catalog_service:
                                    import time
                                    # --- INTERCEPTOR DE NEGOCIO (JSON Voorhees v6.6.6) ---
                                    # [UNIFICACIÓN] moto_interest enforced
                                    moto_interest_prev = prospect_data.get("moto_interest") if prospect_data else None
                                    if moto_interest_prev is not None:
                                        # Obtener alias regionales de catálogo (Zero-Silent-Failures compliant)
                                        aliases = {}
                                        try:
                                            if self._catalog_service and hasattr(self._catalog_service, 'get_catalog_aliases'):
                                                raw_aliases = self._catalog_service.get_catalog_aliases()
                                                aliases = {str(k).lower().strip(): [str(v).lower().strip() for v in (val if isinstance(val, list) else [val])] for k, val in raw_aliases.items() if val}
                                            else:
                                                logger.warning("⚠️ [DRIFT INTERCEPTOR] Catalog service not initialized or missing get_catalog_aliases method")
                                        except Exception as e:
                                            logger.exception(f"🚨 [DRIFT INTERCEPTOR] Error recuperando alias de catálogo desde catalog_service: {e}")
                                            
                                        # Lógica de bifurcación para Cold Start vs Interés Previo
                                        if not str(moto_interest_prev).strip():
                                            # Cold Start: validar si 'query' es un alias válido en 'aliases'
                                            is_bypass = False
                                            q_norm = str(query).lower().strip()
                                            
                                            for category in aliases.keys():
                                                cat_norm = str(category).lower().strip()
                                                if self._is_synonym_or_model_match(q_norm, cat_norm, aliases):
                                                    is_bypass = True
                                                    break
                                            
                                            skip_catalog = False
                                            if is_bypass:
                                                logger.info(f"🔄 [INTERCEPTOR BYPASS COLD START] Búsqueda de alias '{query}' aprobada en Cold Start.")
                                        else:
                                            # Si hay correspondencia semántica o de modelo, hacemos bypass del interceptor
                                            if self._is_synonym_or_model_match(query, moto_interest_prev, aliases):
                                                skip_catalog = False
                                                logger.info(f"🔄 [INTERCEPTOR BYPASS] Búsqueda de '{query}' aprobada por coincidencia de sinónimos/modelos con '{moto_interest_prev}'.")
                                            else:
                                                import difflib
                                                ratio = difflib.SequenceMatcher(None, str(query).lower(), str(moto_interest_prev).lower()).ratio()
                                                if ratio < 0.30:
                                                    skip_catalog = True
                                                    logger.info(f"🛡️ [INTERCEPTOR] Búsqueda de '{query}' bloqueada. Ratio: {ratio:.2f} (Drift Threshold). Protegiendo '{moto_interest_prev}'.")
                                    
                                    if skip_catalog:
                                        search_results = f"[SISTEMA: El usuario ya tiene en contexto la moto '{moto_interest_prev}'. REGLA OBLIGATORIA: NO listes otras motos ni ofrezcas más opciones. Enfócate en concretar la venta de '{moto_interest_prev}' (preguntar forma de pago o iniciar crédito).]"
                                    else:
                                        t_start = time.perf_counter()
                                        
                                        # Llamada estructurada certificada en v9.9.7
                                        matches = self._catalog_service.search_items(query)
                                        
                                        t_end = time.perf_counter()
                                        latency = t_end - t_start
                                        logger.info(f"⏱️ [TELEMETRY] search_items latency: {latency:.4f}s for query: '{query}'")
                                        
                                        # Formateo de los resultados a Markdown con aserción estricta de llaves
                                        if matches:
                                            catalog_response_str = f"Encontré {len(matches)} motos relacionados:\n"
                                            for m in matches:
                                                # Validaciones estrictas de Anti-Null Masking
                                                name = m.get('name')
                                                # 'summary'/'descripcion' is optional, default: 'Sin descripción'
                                                summary = m.get('summary') or m.get('descripcion') or m.get('description') or 'Sin descripción'
                                                price = m.get('price') or m.get('formatted_price') or m.get('precio')
                                                
                                                if not name or not price:
                                                    # [BOT-BUG-040] Anti-Null Masking resiliente: omitir ítem corrupto
                                                    # WHY: Un solo ítem con llave vacía (ej. TVS APACHE 160 sin 'summary')
                                                    # NO debe destruir la iteración completa del catálogo.
                                                    logger.warning(
                                                        f"⚠️ [NULL MASKING DETECTED] Ítem de catálogo omitido por llave crítica nula o vacía: "
                                                        f"name={name!r}, price={price!r}. "
                                                        f"Raw item keys: {list(m.keys())}"
                                                    )
                                                    continue
                                                
                                                catalog_response_str += f"- {name} ({m.get('category', 'Moto')}): {price}\n"
                                                
                                                image_val = m.get('image_url') or m.get('imagen_url')
                                                if image_val:
                                                    catalog_response_str += f"  Image URL: {image_val}\n"
                                                if m.get('link'):
                                                    catalog_response_str += f"  Link: {m['link']}\n"
                                                
                                                # Aserción obligatoria de Ficha Tecnica
                                                catalog_response_str += f"Ficha Tecnica: {summary}\n"
                                                
                                            # Pivotar a la competencia si aplica
                                            competitor_brands = []
                                            try:
                                                from app.core.config_loader import ConfigLoader
                                                config_loader = ConfigLoader()
                                                catalog_config = config_loader.get_catalog_config()
                                                competitor_brands = catalog_config.get("competitor_brands")
                                            except Exception as e:
                                                logger.error(f"⚠️ Error loading competitor brands in AI Brain: {e}")
                                                
                                            if not competitor_brands or not isinstance(competitor_brands, list):
                                                competitor_brands = ["boxer", "nkd", "pulsar", "yamaha", "honda", "suzuki", "akt"]
                                                
                                            competitor_brands_norm = [str(b).lower().strip() for b in competitor_brands if b]
                                            if any(b in query.lower() for b in competitor_brands_norm):
                                                catalog_response_str = f"[SISTEMA: El usuario preguntó por la competencia. ESTÁS OBLIGADO a pivotar a nuestras alternativas...]\n\n" + catalog_response_str
                                                
                                            catalog_returned_results = True
                                            search_results = catalog_response_str
                                            
                                            # Extraer nombres para guardrail de alucinaciones
                                            catalog_models_found.extend([
                                                m.get('name', '').strip()
                                                for m in matches
                                                if m.get('name')
                                            ])
                                        else:
                                            catalog_response_str = "No encontré motos en el catálogo para esa búsqueda."
                                            search_results = catalog_response_str
                                            
                                        # [BOT-TRACE-201] Report tool latency to Langfuse as a child span metadata
                                        if LANGFUSE_AVAILABLE:
                                            try:
                                                langfuse_context.update_current_observation(
                                                    metadata={
                                                        "tool": "search_catalog",
                                                        "query": query,
                                                        "latency_s": round(latency, 4),
                                                        "result_length": len(catalog_response_str),
                                                    },
                                                    name="search_catalog_tool"
                                                )
                                            except Exception as _lf_tel_err:
                                                logger.warning(f"⚠️ [LANGFUSE] search_catalog observation failed: {_lf_tel_err}")
                                                
                                else:
                                    search_results = "Error: Servicio de catálogo no disponible."
                                    
                            except Exception as e:
                                # [BOT-BUG-040] Degradación controlada: log forense SIN re-raise
                                # WHY: Un error de catálogo (ej. ítem corrupto) no debe matar el God Node.
                                # El orquestador debe seguir operativo con un resultado degradado.
                                logger.exception(
                                    f"❌ [BOT-BUG-040] Catalog error for query '{query}' (Prospect: {user_name}): {e}. "
                                    f"Response body: {getattr(e, 'response', None)!r}. "
                                    f"Degrading to fallback search_results."
                                )
                                search_results = f"[SISTEMA: Error temporal consultando el catálogo para '{query}'. Pídele al usuario que intente de nuevo.]"
                                
                            # Personalización de resultados (v8.3)
                            if catalog_returned_results:
                                search_results = f"[SISTEMA: Estos son los resultados para {user_name}. Recomiéndale la mejor opción de forma cálida basándote en su perfil, no solo listes datos.]\n\n" + search_results
                                # [BOT-206] Precedencia absoluta del router: skip_greeting es la única autoridad para suprimir saludo
                                if skip_greeting:
                                    search_results += "\n\n[SYSTEM: BYPASS GREETING: Un elemento del catálogo ha sido recuperado en caliente. Tienes ESTRICTAMENTE PROHIBIDO saludar, dar la bienvenida, decir 'Hola' o presentarte. Empieza tu respuesta directamente con la información de la motocicleta.]"
                                else:
                                    logger.info(f"🆕 [FIRST CONTACT SHIELD] Tool search_catalog returned results but skip_greeting={skip_greeting}. Mandatory greeting enforced.")
                                if prospect_data is not None and matches and not prospect_data.get("moto_interest"):
                                    prospect_data["moto_interest"] = matches[0]["name"]
                                    logger.info(f"💾 Updated prospect_data['moto_interest'] to '{matches[0]['name']}' in tool execution.")
                            
                            search_results += f"\n\n{funnel_instruction}"
                            response_parts.append(types.Part.from_function_response(
                                name=f_name, 
                                response={"result": search_results}
                            ))

                        elif f_name == "calculate_credit_score":
                            logger.info(f"💰 AI calculating credit score...")
                            # --- TOOL REJECTION PATTERN (BOT-ARCH-STATE-101) ---
                            # Si calculate_credit_score es invocada prematuramente en PHASE_1_PROFILING,
                            # retornamos un JSON/dict de error indicando al LLM que la acción está denegada
                            # y obligándolo a usar search_catalog y mostrar precio/imagen.
                            if phase == "PHASE_1_PROFILING":
                                reject_msg = (
                                    "Acción denegada: La herramienta calculate_credit_score no puede ser utilizada en PHASE_1_PROFILING. "
                                    "OBLIGATORIO: Debes identificar primero la moto de interés mediante la herramienta search_catalog, "
                                    "y mostrar el precio exacto y el enlace de imagen al usuario antes de poder realizar cualquier perfilamiento de crédito. "
                                    "El estudio de crédito está estrictamente denegado en esta fase inicial."
                                )
                                logger.warning(f"🛑 [TOOL REJECTION] calculate_credit_score invoked in PHASE_1_PROFILING. Rejecting for LLM.")
                                response_parts.append(types.Part.from_function_response(
                                    name=f_name,
                                    response={"error": reject_msg}
                                ))
                                continue

                            credit_res = "No disponible."
                            try:
                                # [BOT-BRAIN-FINANCE-086] Bifurcación lineal: consentimiento Habeas Data
                                is_accepted = (prospect_data or {}).get("habeas_data_accepted") is True

                                if is_accepted and self.motor_financiero:
                                    # [BOT-BRAIN-FINANCE-091] Check if we should call calculate_score/determine_strategy directly
                                    is_scoring_service = False
                                    try:
                                        from app.services.scoring_service import ScoringService
                                        if isinstance(self.motor_financiero, ScoringService):
                                            is_scoring_service = True
                                    except ImportError:
                                        pass

                                    if is_scoring_service or not hasattr(self.motor_financiero, "evaluate_profile"):
                                        # Mapear la llamada síncrona/bloqueante usando await (asyncio.to_thread) hacia calculate_score y determine_strategy
                                        # de ScoringService, respetando las llaves del EXTRACTION_SCHEMA de Firestore ('ocupacion', 'datacredito')
                                        ocupacion_val = f_args.get("ocupacion") or f_args.get("ocupacion_y_contrato") or (prospect_data or {}).get("ocupacion", "")
                                        datacredito_val = f_args.get("datacredito") or f_args.get("historial_datacredito") or (prospect_data or {}).get("datacredito", "")
                                        ingresos_val = str(f_args.get("ingresos_demostrables") or (prospect_data or {}).get("ingresos_demostrables", ""))
                                        plan_celular_val = f_args.get("plan_celular") or (prospect_data or {}).get("plan_celular", "No")
                                        tiene_gas_val = f_args.get("tiene_gas_natural", False) or (prospect_data or {}).get("tiene_gas_natural", False)
                                        mora_y_paz_val = f_args.get("mora_y_paz_salvo", "") or (prospect_data or {}).get("mora_y_paz_salvo", "")

                                        score = await asyncio.to_thread(
                                            self.motor_financiero.calculate_score,
                                            ocupacion_y_contrato=ocupacion_val,
                                            historial_datacredito=datacredito_val,
                                            ingresos_demostrables=ingresos_val,
                                            plan_celular=plan_celular_val
                                        )

                                        strategy_info = await asyncio.to_thread(
                                            self.motor_financiero.determine_strategy,
                                            score=score,
                                            tiene_gas_natural=tiene_gas_val,
                                            historial_datacredito=datacredito_val,
                                            mora_y_paz_salvo=mora_y_paz_val
                                        )

                                        link_url = "#"
                                        try:
                                            partners = self._config_loader.get_partners_config() if self._config_loader else {}
                                            if partners and strategy_info.get("link_key"):
                                                link_url = partners.get(strategy_info["link_key"], "#")
                                        except Exception as e:
                                            logger.exception(f"[BOT-ARQ-E2E-095] Fallo al obtener partners config. Error: {e}")

                                        requires_documents = False
                                        if strategy_info.get("entity") in ["Brilla de Gases", "Brilla"]:
                                            link_url = None
                                            requires_documents = True

                                        res = {
                                            "score": score,
                                            "strategy": strategy_info["strategy"],
                                            "entity": strategy_info["entity"],
                                            "rate_key": strategy_info["rate_key"],
                                            "link_url": link_url,
                                            "requires_aval": strategy_info["requires_aval"],
                                            "is_fallback": strategy_info.get("is_fallback", False),
                                            "requires_documents": requires_documents,
                                            "explanation": f"Basado en tu perfil (Score: {score}), la mejor opción es {strategy_info.get('entity', 'N/A')}.",
                                            "entidad": f_args.get("entidad"),
                                            "reportes": f_args.get("reportes")
                                        }
                                    else:
                                        # Legacy call to evaluate_profile (keeps tests/mocks passing perfectly)
                                        res = self.motor_financiero.evaluate_profile(
                                            ocupacion_y_contrato=f_args.get("ocupacion_y_contrato", ""),
                                            ingresos_demostrables=f_args.get("ingresos_demostrables", ""),
                                            historial_datacredito=f_args.get("historial_datacredito", ""),
                                            mora_y_paz_salvo=f_args.get("mora_y_paz_salvo", ""),
                                            gastos_vivienda=f_args.get("gastos_vivienda", ""),
                                            tiene_gas_natural=f_args.get("tiene_gas_natural", False),
                                            plan_celular=f_args.get("plan_celular", "No"),
                                            entidad=f_args.get("entidad"),
                                            reportes=f_args.get("reportes")
                                        )

                                    # [BOT-PONYTAIL-200] Compute ponytail_score from credit score
                                    # Clamped to [0-100] and stored as STRING in prospect_data
                                    # This runs in parallel to the existing credit flow — no mutation of
                                    # historical CRM fields (moto_interest, habeas_data_accepted, etc.)
                                    try:
                                        raw_score = res.get("score", 0)
                                        if isinstance(raw_score, (int, float)):
                                            ponytail_score_val = max(0, min(100, int(round(float(raw_score)))))
                                            if prospect_data is not None:
                                                prospect_data["ponytail_score"] = str(ponytail_score_val)
                                                prospect_data["ponytail_status"] = self._determine_ponytail_status(prospect_data)
                                                logger.info(f"🐴 [PONYTAIL] Score computed: {ponytail_score_val}, Status: {prospect_data['ponytail_status']}")
                                    except Exception as e:
                                        logger.warning(f"⚠️ [PONYTAIL] Failed to compute ponytail_score: {e}")

                                    if res.get('entity') == "Brilla de Gases":
                                        credit_res = (
                                            f"✅ RESULTADO: {res['score']} Puntos\n"
                                            f"- ESTRATEGIA: {res['strategy']}\n"
                                            f"- ENTIDAD: Brilla de Gases\n"
                                            f"\n[SISTEMA: MANDATO CRÍTICO: El usuario es APTO para Brilla. "
                                            f"Como NO hay link digital, ESTÁS OBLIGADO a solicitar en este "
                                            f"mensaje las FOTOS de: 1. Cédula original y 2. Los dos últimos "
                                            f"recibos del gas natural. No cierres la sesión sin pedir esto.]"
                                        )
                                    elif res.get('entity') == "Crediorbe":
                                        # [INTERCEPCIÓN CREDIORBE — BOT-FIN-104]
                                        res['link_url'] = None
                                        
                                        moto_name = (prospect_data or {}).get("moto_interest", "")
                                        cuota_line = ""
                                        
                                        if moto_name and self.motor_financiero:
                                            # We attempt a quick lookup to get the price
                                            m_price = 0
                                            moto_cc = 0.0
                                            category = "motos"
                                            if self._catalog_service:
                                                m_results = self._catalog_service.search_items(moto_name)
                                                if m_results: 
                                                    first_match = m_results[0]
                                                    m_price = self._parse_raw_price(
                                                        first_match.get('raw_price'),
                                                        first_match.get('price')
                                                    )
                                                    moto_cc = float(first_match.get("cc", 0.0) or 0.0)
                                                    category = first_match.get("category", "motos") or "motos"
                                            
                                            if m_price <= 0:
                                                import traceback
                                                stack = "".join(traceback.format_stack())
                                                logger.warning(
                                                    f"⚠️ [NULL MASKING DETECTED] Ambos campos raw_price y price están ausentes o vacíos para '{moto_name}'.\nTraceback:\n{stack}"
                                                )
                                                raise ValueError(f"Precio no disponible para la simulación financiera de la moto '{moto_name}'.")

                                            # Use 0 initial as baseline for Crediorbe if not specified
                                            sim = self._calculate_payment_helper(
                                                precio=m_price,
                                                inicial=0,
                                                plazo_meses=24,
                                                entidad="Crediorbe",
                                                moto_cc=moto_cc,
                                                category=category
                                            )
                                            cuota_val = sim.get('cuota_mensual', 0)
                                            if cuota_val > 0:
                                                cuota_line = f"Cuota Mensual Total: ${cuota_val:,.0f} (Incluye SOAT, Matrícula, Seguros y FNG a 24 meses con Crediorbe)\n"
                                            else:
                                                logger.warning(f"⚠️ [COGNITIVE BRAKE] cuota_val=0 for {moto_name}. Omitting cuota line.")

                                        credit_res = (
                                            f"✅ Score: {res['score']} | {res['strategy']}\n"
                                            f"{cuota_line}"
                                            f"\n[SISTEMA: MANDATO DE CONTINGENCIA DE CREDIORBE: "
                                            f"El link digital de Crediorbe ha sido bloqueado. ESTÁS OBLIGADO a "
                                            f"solicitar una foto de la cédula del usuario y coordinar el agendamiento "
                                            f"de una cita presencial en nuestras sedes físicas de Riohacha, Santa Marta o Zona Bananera. "
                                            f"No envíes ningún enlace digital.]"
                                        )
                                    else:
                                        # [COGNITIVE BRAKES v1.2 — BOT-LOGIC-1.2]
                                        # Consolidating output. PROHIBIDO emitir placeholders ($X.XXX).
                                        entity = res.get('entity', 'Brilla de Gases')
                                        
                                        # Resolve simulation if moto is in context
                                        moto_name = (prospect_data or {}).get("moto_interest", "")
                                        cuota_line = ""  # Omitted by default (Cognitive Brake)
                                        
                                        if moto_name and self.motor_financiero:
                                            # We attempt a quick lookup to get the price
                                            m_price = 0
                                            moto_cc = 0.0
                                            category = "motos"
                                            if self._catalog_service:
                                                m_results = self._catalog_service.search_items(moto_name)
                                                if m_results: 
                                                    first_match = m_results[0]
                                                    m_price = self._parse_raw_price(
                                                        first_match.get('raw_price'),
                                                        first_match.get('price')
                                                    )
                                                    moto_cc = float(first_match.get("cc", 0.0) or 0.0)
                                                    category = first_match.get("category", "motos") or "motos"
                                            
                                            if m_price <= 0:
                                                import traceback
                                                stack = "".join(traceback.format_stack())
                                                logger.warning(
                                                    f"⚠️ [NULL MASKING DETECTED] Ambos campos raw_price y price están ausentes o vacíos para '{moto_name}'.\nTraceback:\n{stack}"
                                                )
                                                raise ValueError(f"Precio no disponible para la simulación financiera de la moto '{moto_name}'.")

                                            # Use 0 initial as baseline for Crediorbe if not specified
                                            sim = self._calculate_payment_helper(
                                                precio=m_price,
                                                inicial=0,
                                                plazo_meses=24,
                                                entidad=entity,
                                                moto_cc=moto_cc,
                                                category=category
                                            )
                                            cuota_val = sim.get('cuota_mensual', 0)
                                            if cuota_val > 0:
                                                cuota_line = f"Cuota Mensual Total: ${cuota_val:,.0f} (Incluye SOAT, Matrícula, Seguros y FNG a 24 meses con {entity})\n"
                                            else:
                                                logger.warning(f"⚠️ [COGNITIVE BRAKE] cuota_val=0 for {moto_name}. Omitting cuota line.")

                                        credit_res = (
                                            f"✅ Score: {res['score']} | {res['strategy']}\n"
                                            f"{cuota_line}"
                                            f"Link de Pre-aprobación: {res['link_url']}"
                                        )
                                elif is_accepted and not self.motor_financiero:
                                    credit_res = "Error: Motor financiero no conectado."
                                else:
                                    # --- RAMA CIEGA: Sin Habeas Data → simulación ciega + HabeasDataBypassInterrupt ---
                                    # [BOT-BRAIN-FINANCE-086] Flujo lineal directo (elimina colisión PermissionError)
                                    _phone = (prospect_data or {}).get("phone") or (prospect_data or {}).get("id", "unknown")
                                    logger.warning(
                                        f"SECURITY ALERT [Habeas Data Gate]: Financial profiling without consent. Phone: {_phone}"
                                    )
                                    logger.info(f"[BOT-FINANCE-BYPASS] Ejecutando simulación ciega preventiva ante ausencia de Habeas Data para {user_name}")
                                    m_price = 0.0
                                    moto_cc = 0.0
                                    category = "motos"
                                    moto_name = (prospect_data or {}).get("moto_interest", "")
                                    if moto_name and self._catalog_service:
                                        m_results = self._catalog_service.search_items(moto_name)
                                        if m_results:
                                            first_match = m_results[0]
                                            m_price = self._parse_raw_price(
                                                first_match.get('raw_price'),
                                                first_match.get('price')
                                            )
                                            moto_cc = float(first_match.get("cc", 0.0) or 0.0)
                                            category = first_match.get("category", "motos") or "motos"

                                    if m_price <= 0:
                                        logger.warning(f"⚠️ [Catalog Lock] No se pudo encontrar el precio real para la moto '{moto_name}'. Evitando simulación inventada.")
                                        raise ValueError(f"Precio no disponible para la simulación financiera de la moto '{moto_name}'.")

                                    if self.motor_financiero:
                                        inicial_val = m_price * 0.10
                                        sim = self._calculate_payment_helper(
                                            precio=m_price,
                                            inicial=inicial_val,
                                            plazo_meses=24,
                                            entidad="Brilla de Gases",
                                            moto_cc=moto_cc,
                                            category=category
                                        )
                                        cuota_val = sim.get('cuota_mensual', 0.0)
                                        credit_res = (
                                            f"Si te interesa a crédito con la inicial de ${inicial_val:,.0f}, "
                                            f"las cuotas a 24 meses serían aproximadamente de ${cuota_val:,.0f} "
                                            f"(incluye SOAT y Matrícula). *Nota: Este es un valor aproximado.*"
                                        )
                                    else:
                                        credit_res = "Estimación de cuota base no disponible temporalmente."

                                    credit_res += (
                                        "\n\nPara hacer el estudio formal de tu crédito y darte las opciones de financiación, "
                                        "¿me autorizas el tratamiento de tus datos personales de acuerdo con nuestra política de privacidad? "
                                        "(Política: https://tiendalasmotos.com/politica-de-privacidad). Solo confírmame con un 'Sí' o con un emoji de pulgar arriba (👍)."
                                    )

                                    credit_res_for_llm = credit_res + f"\n\n{funnel_instruction}"
                                    response_parts.append(types.Part.from_function_response(
                                        name="calculate_credit_score",
                                        response={"result": credit_res_for_llm}
                                    ))
                                    raise HabeasDataBypassInterrupt(credit_res)
                            except HabeasDataBypassInterrupt:
                                raise
                            except Exception as e:
                                logger.exception(f"❌ Credit error for prospect {user_name}: {e}")
                                credit_res = "Error calculando el crédito."

                            is_accepted = (prospect_data or {}).get("habeas_data_accepted") is True
                            if not is_accepted:
                                # [CORRECCIÓN QUIRÚRGICA: PASO 4 CON EMOJI INMUTABLE 👍]
                                _phone = (prospect_data or {}).get("phone") or (prospect_data or {}).get("id", "unknown")
                                logger.warning(f"SECURITY ALERT [Habeas Data Gate]: Financial profiling without consent. Phone: {_phone}")
                                logger.info(f"[BOT-FINANCE-BYPASS] Ejecutando simulación ciega preventiva ante ausencia de Habeas Data para {user_name}")
                                
                                m_price = 0.0
                                moto_cc = 0.0
                                category = "motos"
                                moto_name = (prospect_data or {}).get("moto_interest", "")
                                if moto_name and self._catalog_service:
                                    m_results = self._catalog_service.search_items(moto_name)
                                    if m_results:
                                        first_match = m_results[0]
                                        m_price = self._parse_raw_price(first_match.get('raw_price'), first_match.get('price'))
                                        moto_cc = float(first_match.get("cc", 0.0) or 0.0)
                                        category = first_match.get("category", "motos") or "motos"

                                if m_price <= 0:
                                    logger.warning(f"⚠️ [Catalog Lock] No se pudo encontrar el precio real para la moto '{moto_name}'. Evitando simulación inventada.")
                                    raise ValueError(f"Precio no disponible para la simulación financiera de la moto '{moto_name}'.")

                                if self.motor_financiero:
                                    inicial_val = m_price * 0.10
                                    sim = self._calculate_payment_helper(
                                        precio=m_price,
                                        inicial=inicial_val,
                                        plazo_meses=24,
                                        entidad="Brilla de Gases",
                                        moto_cc=moto_cc,
                                        category=category
                                    )
                                    cuota_val = sim.get('cuota_mensual', 0.0)
                                    credit_res = (
                                        f"Si te interesa a crédito con la inicial de ${inicial_val:,.0f}, "
                                        f"las cuotas a 24 meses serían aproximadamente de ${cuota_val:,.0f} "
                                        f"(incluye SOAT y Matrícula). *Nota: Este es un valor aproximado.*"
                                    )
                                else:
                                    credit_res = "Estimación de cuota base no disponible temporalmente."

                                credit_res += (
                                    "\n\nPara hacer el estudio formal de tu crédito y darte las opciones de financiación, "
                                    "¿me autorizas el tratamiento de tus datos personales de acuerdo con nuestra política de privacidad? "
                                    "(Política: https://tiendalasmotos.com/politica-de-privacidad). Solo confírmame con un 'Sí' o con un emoji de pulgar arriba (👍)."
                                )

                                credit_res_for_llm = credit_res + f"\n\n{funnel_instruction}"
                                response_parts.append(types.Part.from_function_response(
                                    name="calculate_credit_score",
                                    response={"result": credit_res_for_llm}
                                ))
                                raise HabeasDataBypassInterrupt(credit_res)

                            credit_res += f"\n\n{funnel_instruction}"
                            response_parts.append(types.Part.from_function_response(
                                name=f_name,
                                response={"result": credit_res}
                            ))

                    if response_parts:
                        turns += 1
                        response = await self._call_gemini_with_retry_async(
                            chat.send_message,
                            response_parts,
                            config=types.GenerateContentConfig(temperature=0.2)
                        )
                    else:
                        break
                
                logger.error(f"🚨 [AI FALLBACK REASON]: Tool loop exited without generating text in {turns} turns for {user_name}")
                return self._fallback_response(texto, history)
            
            except InvalidArgument as e:
                logger.exception(f"❌ Invalid Argument (400) in AI attempt {attempt+1} for prospect {prospect_data.get('nombre', 'Unknown')}: {e}")
                break
                
            except (ResourceExhausted, ServiceUnavailable) as e:
                wait_time = base_delay * (2 ** attempt)
                logger.warning(f"⏳ API Limit (429/503). Retrying in {wait_time}s... (Attempt {attempt+1}/{max_retries})")
                await asyncio.sleep(wait_time)
                
            except HabeasDataBypassInterrupt:
                raise
            except Exception as e:
                error_type = type(e).__name__
                logger.exception(f"🚨 [AI FALLBACK REASON]: {error_type} - {e} | Prospect: {prospect_data.get('nombre', 'Unknown')}")
                break
        
        logger.error(f"🚨 [AI FALLBACK REASON]: Maximum retries ({max_retries}) reached without success for {prospect_data.get('nombre', 'Unknown') if prospect_data else 'Unknown'}")
        return self._fallback_response(texto, history)

    async def detect_sentiment(self, text: str) -> str:
        """
        Analiza el sentimiento del mensaje del usuario usando el nuevo SDK (Async).
        """
        if not SDK_AVAILABLE or not self.client:
            return "NEUTRAL"
        try:
            response = await self.client.aio.models.generate_content(
                model=self._model_id,
                contents=f"Analyze the sentiment of this text. Output ONLY one word: POSITIVE, NEUTRAL, NEGATIVE, or ANGRY.\nText: {text}",
                config=types.GenerateContentConfig(temperature=0.1)
            )
            return response.text.strip().upper()
        except Exception as e:
            logger.exception(f"Error detecting sentiment for text '{text[:50]}...': {e}")
            return "NEUTRAL"

    async def generate_summary(self, conversation_text: str, last_bot_question: str = "", session_id: str = "unknown", previous_moto_interest: str = "") -> Dict[str, Any]:
        """
        Summarize the conversation and extract structured prospect data (Async).
          forzar al modelo de Gemini a generar un JSON garantizado y determinista, en lugar
          de Prompt Engineering + Regex (que era frágil e inseguro ante alucinaciones).
        - Impacto: Asegura que campos críticos del negocio como el perfil de crédito
          (ocupación, datacredito) no se pierdan o malformen, permitiendo que `memory_service`
          los guarde correctamente en Firestore.
        """
        if not self.client:
            logger.error("❌ Gemini Client not initialized. Cannot generate summary.")
            return {"summary": "", "extracted": {}}

        
        try:
            prompt = f"""
            Eres el "Extractor PII Juan Pablo". Tu única tarea es extraer información del historial de chat
            y devolverla en un JSON válido según el esquema proporcionado.

            REGLAS DE EXTRACCIÓN CRÍTICAS:
            1. habeas_data_accepted (STRICT NEGATIVE BIAS): 
               - Solo mapea a `true` si el usuario da una respuesta afirmativa DIRECTA y EXPLÍCITA (ej: "Sí", "Acepto", "Dale", "Listo", "👍") tras el script legal.
               - Si el usuario responde con otra pregunta (ej: "¿qué requisitos hay?") o ambigüedad, DEBE ser `false`.
               - NUNCA asumas aceptación por el simple hecho de continuar la charla.
            2. moto_interest:
               - La moto o estilo (TVS/Victory del catálogo de Tienda Las Motos) por la que preguntó el usuario o en la que mostró interés.
               - Este campo es INMUTABLE contra la competencia. Solo guarda modelos de Tienda Las Motos.
               - PROHIBIDO guardar marcas de la competencia como Bajaj, Yamaha, Honda, Suzuki, AKT. Si el usuario menciona una marca de la competencia, déjalo vacío o no la extraigas.
            3. Resumen: Un resumen ejecutivo de la situación del cliente enfocado en su perfil crediticio y moto de interés.
            4. moto_confirmada: 
               - Solo marca como `true` si el usuario da una respuesta de aceptación o interés EXPLÍCITO hacia la moto del catálogo (ej: "me interesa", "me gusta esa", "esa es", "sí/si", "👍").
               - Si el usuario simplemente pregunta por el precio o características sin confirmar interés, déjalo en `false`.

            HISTORIAL DE CHAT:
            {conversation_text}

            ÚLTIMA PREGUNTA DEL BOT:
            {last_bot_question}
            
            [REGLA DE PERSISTENCIA - MOTO DE INTERÉS]
            Moto actual en base de datos: {previous_moto_interest if previous_moto_interest else 'Ninguna'}
            MANDATO: Si la moto actual NO es 'Ninguna', DEBES volver a incluirla en el campo 'moto_interest' del JSON de respuesta, A MENOS que el usuario pida explícitamente cambiarla en este último chat. BAJO NINGUNA CIRCUNSTANCIA debes dejarla vacía o reemplazarla si el usuario solo está respondiendo a una pregunta o no menciona motos.
            """

            # 1. Prepare Content for google-genai
            # Prompt and history consolidated
            logger.info(f"🔍 [AUDIT PII] conversation_text enviado a Gemini: {conversation_text}")
            
            # 2. Generation with Structured Output (Response Schema)
            response = await self._call_gemini_with_retry_async(
                self.client.aio.models.generate_content,
                model=self._model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=2048,
                    response_mime_type="application/json",
                    response_schema=EXTRACTION_SCHEMA
                )
            )
            
            import json
            import re
            
            raw_response = response.text.strip()
            
            # Sonda de Observabilidad RAW (Hotfix v6)
            logger.info(f"🧠 [RAW LLM SUMMARY OUTPUT]: {raw_response}")
            
            # ATOMIC JSON EXTRACTION (Protocolo JSON Voorhees)
            # We process the raw output through clean_json_voorhees to ensure
            # it's healthy for Firestore persistence.
            result, is_valid = clean_json_voorhees(
                raw_response, 
                session_id=session_id, 
                last_intent="summary_extraction"
            )
            
            if not is_valid:
                logger.error(f"❌ JSON Voorhees flagged invalid response. Raw: {raw_response[:200]}")
            
            if "summary" not in result: result["summary"] = "Error en procesamiento de resumen"
            if "extracted" not in result: result["extracted"] = {}

            # PERSISTENCIA SÍNCRONA: Validar presencia física de la URL en el historial
            has_link = "tiendalasmotos.com/politica-de-privacidad" in conversation_text.lower()
            if has_link:
                result["extracted"]["habeas_data_accepted_sent"] = True
            else:
                result["extracted"]["habeas_data_accepted_sent"] = False
            
            logger.info(f"📝 Generated summary (Voorhees Cleaned) with {len(result.get('extracted', {}))} fields | Valid: {is_valid}")
            
            # --- ROI TELEMETRY ---
            usage = getattr(response, 'usage_metadata', None)
            tokens = getattr(usage, 'total_token_count', 0)
            cost = self._calculate_session_cost(usage)
            logger.info(f"📊 [TELEMETRY] Summary Session: {tokens} tokens, Cost: ${cost} USD")
            
            result["telemetry"] = {
                "tokens": tokens,
                "cost": cost
            }
            return result
            
        except Exception as e:
            logger.exception(f"❌ Error generating summary for session {session_id}: {str(e)}")
            return {
                "summary": conversation_text[:200] + "..." if len(conversation_text) > 200 else conversation_text,
                "extracted": {}
            }

    def _fallback_response(self, texto: str, history: list = []) -> str:
        """
        Clean, generic fallback response to avoid hallucinations.
        Uses history to allow basic continuity if AI fails.
        """
        return "¡Qué pena! Se me quedó colgado el sistema del concesionario un segundo y no me cargó tu mensaje. 😅 ¿Me lo repites para seguir ayudándote?"

    # evaluate_survey_intent() REMOVED — Sprint 1 (2026-03-13)
    # WHY: SurveyService (the Python-level state machine) was deleted in a previous sprint.
    # evaluate_survey_intent() was its sole caller and is now unreachable dead code.
    # The LLM handles survey context-switching naturally via the Firestore system prompt.
    # Leaving this function was a liability: it could be accidentally re-activated and
    # would re-introduce the Python-bypasses-LLM antipattern we just fixed.

