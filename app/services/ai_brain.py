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

logger = logging.getLogger(__name__)

# Use the new unified google-genai SDK
try:
    from google import genai
    from google.genai import types
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    logger.warning("⚠️  google-genai SDK not available, using fallback responses")

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
                "moto_interes": {
                    "type": "STRING",
                    "description": "La primera moto o estilo por el que preguntó el usuario."
                },
                "moto_ofrecida": {
                    "type": "STRING",
                    "description": "La moto del catálogo (TVS/Victory) que el bot ofreció."
                },
                "moto_aceptada": {
                    "type": "STRING",
                    "description": "La moto que el usuario aceptó explícitamente comprar o conocer más (Inmutable contra competencia)."
                },
                "habeas_data": {
                    "type": "BOOLEAN",
                    "description": "Indica si el usuario aceptó el tratamiento de datos (mapeado de afirmaciones o emojis)."
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
                }
            }
        }
    },
    "required": ["summary", "extracted"]
}


class CerebroIA:
    """
    AI Brain for intelligent conversation handling.
    
    Uses Google Gemini 2.0 Flash model via Vertex AI to generate
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
                self._model_id = "gemini-2.5-flash" # Use stable versioning
                
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
                # Note: google-genai SDK maps some errors to APIError or ClientError
                # We look for 429 (Resource Exhausted) and 503 (Service Unavailable)
                err_str = str(e).lower()
                is_quota_error = "429" in err_str or "resource_exhausted" in err_str
                is_service_error = "503" in err_str or "service_unavailable" in err_str
                
                if (is_quota_error or is_service_error) and attempt < max_retries:
                    wait_time = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(f"⏳ [EXP BACKOFF] Attempt {attempt+1} failed ({type(e).__name__}). Retrying in {wait_time:.2f}s...")
                    await asyncio.sleep(wait_time)
                    continue
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

        # Phase 3: Credit Profiling
        # Condition: Payment method is 'credito' AND Habeas Data is accepted AND sent.
        # MANDATO v2: Verificación física del link de privacidad en el historial del chat.
        conversation_text = ""
        if history:
            for m in history:
                # Extract text from Content parts
                if hasattr(m, 'parts'):
                    parts_text = "".join([getattr(p, 'text', '') for p in m.parts if hasattr(p, 'text')])
                    conversation_text += parts_text + " "
        
        has_sent_link = "tiendalasmotos.com/politica-de-privacidad" in conversation_text.lower()
        
        # SI YA ACEPTÓ HABEAS DATA -> PHASE 3 (Profiling)
        is_accepted = prospect_data.get("habeas_data") is True
        is_sent = prospect_data.get("habeas_data_sent") is True
        
        if is_accepted and is_sent and has_sent_link:
            has_name = bool(prospect_data.get("nombre") or prospect_data.get("name"))
            has_city = bool(prospect_data.get("ciudad") or prospect_data.get("city"))
            if not has_name or not has_city:
                # Regla v1.3.2: No avanzar a perfilamiento sin nombre ni ciudad (Guardrail de Vitrina)
                logger.warning(f"⚠️ Prospecto aceptó Habeas Data pero falta nombre o ciudad. Re-enrutando a Phase 1.")
                return "PHASE_1_PROFILING"
            return "PHASE_3_CREDIT_PROFILING"

        # Phase 2: Habeas Data Request (Legal Script)
        # Condition: User selected 'credito' AND we have name AND city AND moto_confirmada is True.
        # CRITICAL FIX: Extraction of moto_interest is not enough; explicit confirmation is required.
        has_name = bool(prospect_data.get("nombre") or prospect_data.get("name"))
        has_city = bool(prospect_data.get("ciudad") or prospect_data.get("city"))
        moto_confirmada = prospect_data.get("moto_confirmada") is True
        is_credit = bool(prospect_data.get("forma_pago") == "credito" or prospect_data.get("payment_method") == "credito")

        # --- BLOQUEO PROTOCOLO COMPETENCIA (Directiva 2026) ---
        # Bloqueamos el avance a fase legal si la moto es de la competencia.
        moto_interes = str(prospect_data.get("moto_interes", "")).lower()
        competitors = ["boxer", "nkd", "yamaha", "suzuki", "honda", "akt", "pulsar", "victory", "tvs Apache"] # Apache can be our but Pulsar is competitor? Actually Pulsar is Bajaj.
        # User defined Boxer, NKD, Yamaha explicitly.
        competitor_keywords = ["boxer", "nkd", "yamaha", "suzuki", "honda", "bajaj", "hero"]
        
        is_competitor = any(comp in moto_interes for comp in competitor_keywords)
        alternative_interest = prospect_data.get("interest_confirmed_in_alternative") is True
        
        if is_competitor and not alternative_interest:
            logger.info(f"🚫 [PROTOCOL] Competitor brand detected: {moto_interes}. Blocking advance to Phase 2.")
            return "PHASE_1_PROFILING"

        # --- INTENCIÓN FINANCIERA (v1.3.1) ---
        is_financial_intent = False
        if history:
            finance_keywords = ["cuota", "credito", "crédito", "financiar", "mensualidad", "requisitos", "cuanto pago", "papeles"]
            last_msgs = [str(m.get("content", "")).lower() for m in reversed(history) if m.get("role") == "user"][:2]
            if any(any(kw in msg for kw in finance_keywords) for msg in last_msgs):
                logger.info("💰 [INTENT] Financial intent detected. Bypassing moto_confirmada for Phase 2.")
                is_financial_intent = True

        if has_name and has_city and (moto_confirmada or is_financial_intent) and is_credit:
            return "PHASE_2_HABEAS_DATA"

        # Phase 1: Default (Profiling / Catalog)
        return "PHASE_1_PROFILING"

    async def pensar_respuesta(self, texto: str, context: str = "", prospect_data: Optional[Dict[str, Any]] = None, history: list = [], skip_greeting: bool = False) -> str:
        """
        Main entry point for AI logic.
        Combines deterministic funnel checks + generative AI (Gemini).
        """
        raw_response = await self._generate_with_retry_async(texto, context, prospect_data, history, skip_greeting)
        
        # --- PHASE-GATE FÍSICO (Bypass de Habeas Data) ---
        # AUDIT P1 (2.2): Interceptor de Respuesta.
        # Si el usuario NO ha aceptado Habeas Data, bloqueamos cualquier pregunta de crédito.
        habeas_data_accepted = prospect_data.get("habeas_data", False) if prospect_data else False
        
        if not habeas_data_accepted and raw_response and not raw_response.startswith("HANDOFF_TRIGGERED:"):
            # REGLA DE NEGOCIO (Audit v2.0): Permitir "crédito" como explicación, bloquear solo perfilamiento.
            is_profiling = self._is_profiling_attempt(raw_response)
            
            if is_profiling:
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
                return transition_msg.strip()

        # FINAL SANITIZATION: Hardcoded Parrot Effect Killer
        if raw_response and not raw_response.startswith("HANDOFF_TRIGGERED:"):
            final_text = self.clean_parrot_phrases(raw_response)
            
            # PHASE 2 / LEGAL INJECTION (JSON Voorhees v2.1.0 programmatic insertion)
            if re.search(r'(?i)\b(autoriza|tratamiento de datos|habeas data|pol[íi]tica de privacidad|ley\s?1581|datos personales)\b', final_text):
                if "tiendalasmotos.com/politica-de-privacidad" not in final_text:
                    final_text += "\n\n📄 Conoce nuestra Política de Privacidad aquí: https://tiendalasmotos.com/politica-de-privacidad"
            
            # LAST-MILE CLEANUP: Remove any technical markdown residue
            final_text = self.clean_markdown_blocks(final_text)
            
            return final_text
            
        return self.clean_markdown_blocks(raw_response)

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
                        }
                    },
                    "required": ["ocupacion_y_contrato", "ingresos_demostrables", "historial_datacredito"]
                }
            )

            function_declarations = [handoff_function, catalog_function]
            
            # Stop-Gate Logic (Audit P2 1.1)
            phase = self._determine_funnel_phase(prospect_data)
            moto_confirmada = prospect_data.get("moto_confirmada") is True if prospect_data else False
            
            # REGLA v1.3.1: Desacople de Crédito (Mandatorio)
            # La herramienta de crédito debe estar disponible en las fases 1, 2 y 3
            # para cumplir con el protocolo de "Valor Primero" y la Phase 2.
            if phase in ["PHASE_1_PROFILING", "PHASE_2_HABEAS_DATA", "PHASE_3_CREDIT_PROFILING"]:
                function_declarations.append(credit_function)
                logger.info(f"🛠️ Toolset: [handoff, catalog, credit] (Phase: {phase})")
            else:
                logger.info(f"🛠️ Toolset: [handoff, catalog] (Phase: {phase})")

            return [types.Tool(function_declarations=function_declarations)]
        except Exception as e:
            logger.error(f"❌ Error creating tools: {str(e)}", exc_info=True)
            return []

    async def _generate_with_retry_async(self, texto: str, context: str, prospect_data: Optional[Dict[str, Any]] = None, history: list = [], skip_greeting: bool = False, forced_instruction: Optional[str] = None) -> str:
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
        
        # --- NEW ADAPTER LAYER: CRM ANCHOR CONTEXT (REF-004) ---
        # Moving the anchor logic from the router to the brain.
        # This keeps the 'texto' (raw user input) clean for the tool interceptor.
        anchor_context = ""
        if prospect_data and prospect_data.get("moto_interes"):
            moto_interes = prospect_data.get("moto_interes")
            # Anchor rule: If message is short (<60 chars) and doesn't imply a shift, reinforce preference.
            if len(texto) < 60 and not any(m in texto.lower() for m in ["otra", "cambiar", "no la"]):
                anchor_context = f"\n[CRM ANCHOR: El usuario está interesado en la {moto_interes}. Mantén el contexto sobre este modelo a menos que el usuario pida conocer otra motocicleta.]\n"
                logger.info(f"💉 Internal CRM Anchor Context injected: {moto_interes}")

        # 2. Build Instructions block based on State
        funnel_instruction = ""
        if phase == "PHASE_1_PROFILING":
            p_name = prospect_data.get("nombre") or prospect_data.get("name") if prospect_data else None
            p_ciudad = prospect_data.get("ciudad") or prospect_data.get("city") if prospect_data else None
            p_payment = prospect_data.get("forma_pago") or prospect_data.get("payment_method") if prospect_data else None
            
            # Sincronización Protegida: Confiamos en prospect_data actualizado por el socket síncrono.
            # Se eliminan detecciones manuales por Regex para evitar falsos positivos y bloqueos de lógica.
            pass

            # HARD-GATE DE IDENTIDAD (Requirement 2026.1): Prohibido preguntar si ya existe.
            # v1.3.0: Skip name request if moto is confirmed or in context
            moto_context = prospect_data.get("moto_interes") or prospect_data.get("moto_confirmada")
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
            funnel_instruction = "EL USUARIO ESTÁ LISTO PARA EL CRÉDITO. Debes presentar el script legal de Habeas Data y pedir su aceptación explícita (Sí/No)."
        
        elif phase == "PHASE_3_CREDIT_PROFILING":
            funnel_instruction = (
                "Habeas Data Aceptado. Procede con el perfilamiento. "
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
                
                full_prompt = f"""
{self._get_current_instruction()}

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
                if prospect_data and prospect_data.get("name"):
                    p_name = prospect_data.get("name")
                    full_prompt += f"\n[CRITICAL IDENTITY RULE: Estás hablando con {p_name}. Tu respuesta DEBE empezar con un saludo personalizado hacia él. Ignorar esto es un fallo de seguridad.]\n"
                
                full_prompt += "Juan Pablo:"
                
                # --- MAIN INFERENCE CALL (google-genai syntax) ---
                chat = self.client.aio.chats.create(model=self._model_id)

                # 💎 [FULL PROMPT AUDIT] (Requirement v2)
                # We log the consolidated prompt to verify that PII and Phase are correctly injected.
                audit_log = f"\n--- PROMPT AUDIT START ---\nPHASE: {phase}\nINSTRUCTION: {funnel_instruction}\nPROSPECT: {prospect_data}\nPROMPT: {full_prompt[:1500]}...\n--- PROMPT AUDIT END ---\n"
                logger.info(f"💎 [FULL PROMPT AUDIT] sending to Gemini for {prospect_data.get('name') if prospect_data else 'None'}: {audit_log}")

                try:
                    response = await self._call_gemini_with_retry_async(
                        chat.send_message,
                        full_prompt,
                        config=types.GenerateContentConfig(
                            temperature=0.2,
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
                    motorcycle_keywords = ["moto", "raider", "sport", "victory", "tvs", "mrx", "trabajo", "trabajar", "mensajeria", "domicilio", "carga"]
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
                                has_moto_interest = bool(prospect_data.get("moto_interes")) if prospect_data else False
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
                                cost = self._calculate_session_cost(usage)
                                prospect_data['total_tokens_consumed'] = prospect_data.get('total_tokens_consumed', 0) + tokens
                                prospect_data['session_cost_usd'] = prospect_data.get('session_cost_usd', 0.0) + cost
                                logger.info(f"📊 [TELEMETRY] Response: {tokens} tokens, Cost: ${cost} USD | Cumulative in session.")

                            return ai_response
                        except Exception as e:
                            logger.exception(f"⚠️ Error extracting text for {user_name}: {e}")
                            return self._fallback_response(texto, history)

                    # Execute function calls
                    logger.info(f"⚡ AI triggered {len(function_calls)} function call(s)")
                    response_parts = []
                    
                    for fc in function_calls:
                        f_name = fc.name
                        f_args = fc.args
                        
                        if f_name == "trigger_human_handoff":
                            reason = f_args.get("reason", "unknown")
                            return f"HANDOFF_TRIGGERED:{reason}"
                        
                        elif f_name == "search_catalog":
                            search_catalog_called = True
                            query = f_args.get("query", "")
                            search_results = "No se encontraron resultados."
                            try:
                                if self._catalog_service:
                                    import time
                                    # --- INTERCEPTOR DE NEGOCIO (JSON Voorhees v6.6.6) ---
                                    moto_interest_prev = prospect_data.get("moto_interes") if prospect_data else None
                                    skip_catalog = False
                                    if moto_interest_prev:
                                        import difflib
                                        ratio = difflib.SequenceMatcher(None, str(query).lower(), str(moto_interest_prev).lower()).ratio()
                                        if 0.35 <= ratio < 0.95:
                                            skip_catalog = True
                                            logger.info(f"🛡️ [INTERCEPTOR] Búsqueda de '{query}' bloqueada. Ratio: {ratio:.2f} (Drift Threshold). Protegiendo '{moto_interest_prev}'.")
                                    
                                    if skip_catalog:
                                        search_results = f"[SISTEMA: El usuario ya tiene en contexto la moto '{moto_interest_prev}'. REGLA OBLIGATORIA: NO listes otras motos ni ofrezcas más opciones. Enfócate en concretar la venta de '{moto_interest_prev}' (preguntar forma de pago o iniciar crédito).]"
                                    else:
                                        t_start = time.perf_counter()
                                        matches = self._catalog_service.search_items(query)
                                        t_end = time.perf_counter()
                                        latency = t_end - t_start
                                        logger.info(f"⏱️ [TELEMETRY] search_catalog latency: {latency:.4f}s for query: '{query}'")
                                        
                                        if matches:
                                            catalog_returned_results = True
                                            search_results = f"Encontré {len(matches)} motos relacionados:\n"
                                            for m in matches: 
                                                name = m.get('name', 'Moto')
                                                catalog_models_found.append(name)
                                                # Using .get for category and price for maximum robustness
                                                category = m.get('category', 'Moto')
                                                price = m.get('price', m.get('formatted_price', 'Consultar'))
                                                
                                                search_results += f"- {name} ({category}): {price}\n"
                                                if m.get('image_url'): search_results += f"  Image URL: {m['image_url']}\n"
                                                if m.get('link'): search_results += f"  Link: {m['link']}\n"
                                                if m.get('specs'): search_results += f"  Ficha Tecnica: {m['specs']}\n"
                                                
                                            competitor_brands = ["boxer", "nkd", "pulsar", "yamaha", "honda", "suzuki", "akt"]
                                            if any(b in query.lower() for b in competitor_brands):
                                                search_results = f"[SISTEMA: El usuario preguntó por la competencia. ESTÁS OBLIGADO a pivotar a nuestras alternativas...]\n\n" + search_results
                                        else:
                                            search_results = "No encontré motos en el catálogo para esa búsqueda."
                                else:
                                    search_results = "Error: Servicio de catálogo no disponible."
                            except Exception as e:
                                logger.exception(f"❌ Catalog error for query '{query}' (Prospect: {user_name}): {e}")
                                search_results = "Error consultando catálogo."
                                
                            # Personalización de resultados (v8.3)
                            if catalog_returned_results:
                                search_results = f"[SISTEMA: Estos son los resultados para {user_name}. Recomiéndale la mejor opción de forma cálida basándote en su perfil, no solo listes datos.]\n\n" + search_results
                            
                            search_results += f"\n\n{funnel_instruction}"
                            response_parts.append(types.Part.from_function_response(
                                name=f_name, 
                                response={"result": search_results}
                            ))

                        elif f_name == "calculate_credit_score":
                            logger.info(f"💰 AI calculating credit score...")
                            credit_res = "No disponible."
                            try:
                                if self.motor_financiero:
                                    res = self.motor_financiero.evaluar_perfil(
                                        ocupacion_y_contrato=f_args.get("ocupacion_y_contrato", ""),
                                        ingresos_demostrables=f_args.get("ingresos_demostrables", ""),
                                        historial_datacredito=f_args.get("historial_datacredito", ""),
                                        mora_y_paz_salvo=f_args.get("mora_y_paz_salvo", ""),
                                        gastos_vivienda=f_args.get("gastos_vivienda", ""),
                                        tiene_gas_natural=f_args.get("tiene_gas_natural", False),
                                        plan_celular=f_args.get("plan_celular", "No")
                                    )
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
                                    else:
                                        # [NO-BREAKDOWN RULE v1.3.2]
                                        # Consolidating output into a single formatted string.
                                        label = "Cuota Mensual Total"
                                        entity = res.get('entity', 'Crediorbe')
                                        
                                        # Resolve simulation if moto is in context
                                        moto_name = (prospect_data or {}).get("moto_interes", "")
                                        cuota_str = "$X.XXX"
                                        
                                        if moto_name and self.motor_financiero:
                                            # We attempt a quick lookup to get the price
                                            m_price = 0
                                            if self._catalog_service:
                                                m_results = self._catalog_service.search_items(moto_name)
                                                if m_results: 
                                                    m_price = m_results[0].get('raw_price', 0)
                                            
                                            if m_price > 0:
                                                # Use 0 initial as baseline for Crediorbe if not specified
                                                sim = self.motor_financiero.calcular_cuota(
                                                    precio=m_price,
                                                    inicial=0,
                                                    plazo_meses=24,
                                                    entidad=entity
                                                )
                                                cuota_val = sim.get('cuota_mensual', 0)
                                                cuota_str = f"${cuota_val:,.0f}"

                                        credit_res = (
                                            f"✅ Score: {res['score']} | {res['strategy']}\n"
                                            f"{label}: {cuota_str} (Incluye SOAT, Matrícula, Seguros y FNG a 24 meses con {entity})\n"
                                            f"Link de Pre-aprobación: {res['link_url']}"
                                        )
                                else:
                                    credit_res = "Error: Motor financiero no conectado."
                            except Exception as e:
                                logger.exception(f"❌ Credit error for prospect {user_name}: {e}")
                                credit_res = "Error calculando el crédito."

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

    async def generate_summary(self, conversation_text: str, last_bot_question: str = "", session_id: str = "unknown", previous_moto_interes: str = "") -> Dict[str, Any]:
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
            1. habeas_data (STRICT NEGATIVE BIAS): 
               - Solo mapea a `true` si el usuario da una respuesta afirmativa DIRECTA y EXPLÍCITA (ej: "Sí", "Acepto", "Dale", "Listo", "👍") tras el script legal.
               - Si el usuario responde con otra pregunta (ej: "¿qué requisitos hay?") o ambigüedad, DEBE ser `false`.
               - NUNCA asumas aceptación por el simple hecho de continuar la charla.
            2. moto_aceptada:
               - Este campo es INMUTABLE contra la competencia. Solo guarda modelos de Tienda Las Motos que el usuario haya aceptado explícitamente comprar o ver.
               - PROHIBIDO guardar marcas de la competencia como Bajaj, Yamaha, Honda, Suzuki, AKT.
               - Si el usuario menciona una marca de la competencia, déjalo en blanco.
            3. moto_interes: La primera moto por la que preguntó el usuario.
            4. moto_ofrecida: La moto que el bot recomendó del catálogo (sustituye a moto_offered).
            5. Resumen: Un resumen ejecutivo de la situación del cliente enfocado en su perfil crediticio y moto de interés.
            6. moto_confirmada: 
               - Solo marca como `true` si el usuario da una respuesta de aceptación o interés EXPLÍCITO hacia la moto ofrecida (ej: "me interesa", "me gusta esa", "esa es", "sí/si", "👍").
               - Si el usuario simplemente pregunta por el precio o características sin confirmar interés, déjalo en `false`.

            HISTORIAL DE CHAT:
            {conversation_text}

            ÚLTIMA PREGUNTA DEL BOT:
            {last_bot_question}
            
            [REGLA DE PERSISTENCIA - MOTO DE INTERÉS]
            Moto actual en base de datos: {previous_moto_interes if previous_moto_interes else 'Ninguna'}
            MANDATO: Si la moto actual NO es 'Ninguna', DEBES volver a incluirla en el campo 'moto_interes' del JSON de respuesta, A MENOS que el usuario pida explícitamente cambiarla en este último chat. BAJO NINGUNA CIRCUNSTANCIA debes dejarla vacía o reemplazarla si el usuario solo está respondiendo a una pregunta o no menciona motos.
            """

            # 1. Prepare Content for google-genai
            # Prompt and history consolidated
            logger.info(f"🔍 [AUDIT PII] conversation_text enviado a Gemini: {conversation_text}")
            
            # 2. Generation with Structured Output (Response Schema)
            response = self._call_gemini_with_retry(
                self.client.models.generate_content,
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

