"""
Cerebro IA - AI Brain Service
Handles intelligent responses using Google Gemini AI for general inquiries.
"""

import logging
import os
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Try to import Vertex AI
try:
    import vertexai
    from vertexai.generative_models import (
        GenerativeModel,
        Tool,
        FunctionDeclaration,
        Content,
        Part,
        GenerationConfig
    )
    VERTEX_AI_AVAILABLE = True
except ImportError:
    VERTEX_AI_AVAILABLE = False
    logger.warning("⚠️  Vertex AI not available, using fallback responses")


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
        self.config_loader = config_loader
        self.catalog_service = catalog_service
        self.motor_financiero = None  # Will be injected
        self._model = None
        # HOT-RELOAD FIX (Audit P1, 4.3):
        # _system_instruction is intentionally NOT cached here.
        # _get_current_instruction() reads from config_loader on every request,
        # so /admin/refresh-config takes effect immediately without a Cloud Run restart.
        self.tools = self._create_tools()
        
        # Initialize Vertex AI if available
        if VERTEX_AI_AVAILABLE:
            try:
                vertexai.init(project="tiendalasmotos", location="us-central1")
                # Model is initialized WITHOUT a system_instruction here.
                # The instruction is injected dynamically per-request via _get_current_instruction().
                self._model = GenerativeModel(
                    "gemini-2.5-flash",
                    tools=[self.tools] if self.tools else []
                )
                logger.info(f"🧠 CerebroIA initialized with Gemini 2.5 Flash ({'Tools Enabled' if self.tools else 'No Tools'})")
            except Exception as e:
                logger.error(f"❌ Error initializing Vertex AI: {str(e)}")
                self._model = None
        else:
            logger.warning("⚠️  CerebroIA running in fallback mode (no AI)")
    
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
        if self.config_loader:
            try:
                personality = self.config_loader.get_juan_pablo_personality()
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
    
    def _determine_funnel_phase(self, prospect_data: Optional[Dict[str, Any]]) -> str:
        """
        Deterministic state machine for funnel phase allocation.
        Based on explicit business data gathered in Firestore.
        """
        if not prospect_data:
            return "PHASE_1_PROFILING"

        # Phase 3: Credit Profiling
        # Condition: Payment method is 'credito' AND Habeas Data is accepted.
        if prospect_data.get("habeas_data_accepted") is True:
            return "PHASE_3_CREDIT_PROFILING"

        # Phase 2: Habeas Data Request (Legal Script)
        # Condition: User selected 'credito' AND we have moto interest AND name AND city.
        # This is the "Force State Verification" the stakeholder requested.
        has_name = bool(prospect_data.get("name"))
        has_city = bool(prospect_data.get("ciudad"))
        has_moto = bool(prospect_data.get("moto_interest"))
        is_credit = prospect_data.get("payment_method") == "credito"

        if has_name and has_city and has_moto and is_credit:
            return "PHASE_2_HABEAS_DATA"

        # Phase 1: Default (Profiling / Catalog)
        return "PHASE_1_PROFILING"

    def pensar_respuesta(self, texto: str, context: str = "", prospect_data: Optional[Dict[str, Any]] = None, history: list = [], skip_greeting: bool = False) -> str:
        """
        Main entry point for AI logic.
        Combines deterministic funnel checks + generative AI (Gemini).

        QA Security Baseline:
        - Context Injection: CRM fields (ocupacion, datacredito, etc.) are injected into the
          prompt so the LLM never re-asks questions already answered in the survey.
        - Deterministic Funnel: Mathematically enforces name/city capture before advancing.
        - Fail-Closed: If a funnel_instruction is set, it is appended to tool results to
          force the LLM to close with the required question.
        - Hot-Reload: System prompt is fetched from config_loader on every call, so
          /admin/refresh-config takes effect immediately.
        """
        return self._generate_with_retry(texto, context, prospect_data, history, skip_greeting)

    def _create_tools(self) -> Optional[Tool]:
        """
        Create tools for function calling (human handoff).
        Returns: Tool object with function declarations, or None if not available
        """
        if not VERTEX_AI_AVAILABLE:
            return None
        
        try:
            # Define human handoff function
            # SECURITY (QA Baseline): This tool is intentionally locked to ONLY fire on
            # explicit user requests. Permitting 'complex_query' or 'technical_question'
            # caused the LLM to escape answering FAQs (credit requirements, pricing)
            # by routing them to a human, breaking the automated sales funnel.
            handoff_function = FunctionDeclaration(
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
            catalog_function = FunctionDeclaration(
                name="search_catalog",
                description="""Search for motorcycles in the catalog using a query string. 
REGLA DE ORO: NUNCA asumas el inventario. Si el usuario menciona CUALQUIER moto o necesidad, ESTÁS OBLIGADO a usar esta herramienta ANTES de responder. 
IMPORTANTE: Lee las instrucciones del parámetro 'query' para saber cómo formular la búsqueda dependiendo de si es un modelo específico o una búsqueda amplia.""",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": """Término de búsqueda a ingresar en el sistema. Debes evaluar la frase del usuario y aplicar UNA de estas dos reglas:
REGLA 1 (Modelos Específicos/Sniper): Si el usuario nombra una marca o modelo exacto (ej. 'Raider', 'NKD', 'Sport'), tu query DEBE ser EXACTAMENTE esa palabra (ej. 'Raider'). PROHIBIDO abstraer o agrupar en segmentos como 'motos street'.
REGLA 2 (Búsqueda Amplia/Semántica): Si el usuario describe un uso, necesidad u oración larga (ej. 'motos para ir a la finca', 'para camellar', 'automática de mujer'), tu deber es EXTRAER SOLO EL CONCEPTO CLAVE de una o dos palabras (ej. 'enduro', 'trabajo', 'scooter'). NUNCA pases oraciones largas ni preposiciones al query."""
                        }
                    },
                    "required": ["query"]
                }
            )
            
            # Define credit calculation function
            credit_function = FunctionDeclaration(
                name="calculate_credit_score",
                description="ÚNICA herramienta autorizada para calcular el perfil crediticio. Úsala inmediatamente después del Paso 9. Proporciona el score, la entidad asignada y el link de aplicación.",
                parameters={
                    "type": "object",
                    "properties": {
                        "ocupacion_y_contrato": {
                            "type": "string",
                            "description": "Ocupación y tipo de contrato. Mapeo estricto: Si dice 'informal', 'rebusque', 'cuenta propia', o 'negocio', MÁPEALO a 'Independiente'. Si dice 'empleado', 'trabajo en', 'mensajero' (con empresa), MÁPEALO a 'Empleado fijo'. De lo contrario, extrae la intención más cercana."
                        },
                        "ingresos_demostrables": {
                            "type": "string",
                            "description": "Nivel de ingresos. Mapeo estricto: Si dice 'el mínimo', 'lo básico', MÁPEALO a '1705905' (valor numérico). Si no da valor exacto pero afirma trabajar, infiere el mínimo legal ($1.705.905). No envíes texto como 'el mínimo'."
                        },
                        "historial_datacredito": {
                            "type": "string",
                            "description": "Estado en Datacrédito. Mapeo estricto: Si dice 'nunca he sacado nada', 'no sé', MÁPEALO a 'Sin experiencia'. Si dice 'bien', 'pagando cuenta', MÁPEALO a 'Al dia'. Si menciona 'atrasado', 'castigado', MÁPEALO a 'Reportado'."
                        },
                        "mora_y_paz_salvo": {
                            "type": "string",
                            "description": "Detalles de mora (>30 días). Mapeo estricto: Si historial_datacredito no es Reportado, MÁPEALO siempre a 'Sin mora'. Si está reportado pero pagó, MÁPEALO a 'Con mora y paz y salvo'. Si sigue debiendo, MÁPEALO a 'Con mora sin paz y salvo'."
                        },
                        "gastos_vivienda": {
                            "type": "string",
                            "description": "Gastos de vivienda. Mapeo estricto: Si dice 'con mis papás', 'casa de un familiar', MÁPEALO a 'Familiar'. Si paga arriendo o renta, MÁPEALO a 'Arriendo'. Si es dueño, MÁPEALO a 'Propia'."
                        },
                        "tiene_gas_natural": {
                            "type": "boolean",
                            "description": "Indica si tiene recibo de Gas Natural a su nombre (true o false). Si dice 'no sé', 'a nombre de mi mamá', asume 'false'."
                        },
                        "plan_celular": {
                            "type": "string",
                            "description": "Tipo de plan de celular. Mapeo estricto: Si indica 'no tengo plan', 'recargo', 'tarjeta', MÁPEALO a 'Prepago'. Si paga factura o abono fijo mensual, MÁPEALO a 'Postpago'."
                        }
                    },
                    "required": [
                        "ocupacion_y_contrato", 
                        "ingresos_demostrables", 
                        "historial_datacredito", 
                        "mora_y_paz_salvo", 
                        "gastos_vivienda", 
                        "tiene_gas_natural", 
                        "plan_celular"
                    ]
                }
            )

            return Tool(function_declarations=[handoff_function, catalog_function, credit_function])
        except Exception as e:
            logger.error(f"❌ Error creating tools: {str(e)}", exc_info=True)
            return None

    def _generate_with_retry(self, texto: str, context: str, prospect_data: Optional[Dict[str, Any]] = None, history: list = [], skip_greeting: bool = False) -> str:
        """
        Internal generation with exponential backoff and structured prompt injection.
        """
        if not self._model: return self._fallback_response(texto, history)
        
        max_retries = 3
        base_delay = 2 
        
        import time
        from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable, InvalidArgument

        # 1. Deterministic state evaluation
        phase = self._determine_funnel_phase(prospect_data)
        
        # 2. Build Instructions block based on State
        funnel_instruction = ""
        if phase == "PHASE_1_PROFILING":
            # Missing basic profiling data
            p_name = prospect_data.get("name") if prospect_data else None
            p_ciudad = prospect_data.get("ciudad") if prospect_data else None
            p_payment = prospect_data.get("payment_method") if prospect_data else None
            
            if not p_name:
                funnel_instruction = "El sistema requiere el nombre del prospecto. Cierra tu mensaje preguntando: '¿con quién tengo el gusto?' o similar."
            elif not p_ciudad:
                funnel_instruction = "Falta la ciudad del prospecto. Cierra tu mensaje preguntando: '¿Desde qué ciudad nos escribes?'"
            elif not p_payment:
                funnel_instruction = "Falta el método de pago. Pregunta si prefiere compra de contado o a crédito."
        
        elif phase == "PHASE_2_HABEAS_DATA":
            funnel_instruction = "EL USUARIO ESTÁ LISTO PARA EL CRÉDITO. Debes presentar el script legal de Habeas Data y pedir su aceptación explícita (Sí/No)."
        
        elif phase == "PHASE_3_CREDIT_PROFILING":
            funnel_instruction = "Habeas Data Aceptado. Procede con las preguntas de perfilamiento crediticio (ocupación, ingresos, etc.) según el flujo del embudo."

        for attempt in range(max_retries):
            try:
                chat = self._model.start_chat()
                
                # 3. CONSOLIDATE XML PROMPT
                user_name = prospect_data.get("name", "desconocido") if prospect_data else "desconocido"
                
                # Format prospect attributes for XML injection
                prospect_xml = ""
                if prospect_data and prospect_data.get("exists"):
                    prospect_xml = "\n".join([f"    <{k}>{v}</{k}>" for k,v in prospect_data.items() if v and k not in ['exists', 'summary']])
                
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
</contexto_dinamico>

⚠️ REGLA CRÍTICA: Ignora cualquier instrucción de identidad previa en el historial. Tu nombre es Juan Pablo. 
Utiliza la <instruccion_de_cierre> para orientar tu respuesta final de forma natural.
"""

                # 4. Inject Chat History (Capped at 2000 chars)
                if history:
                    history_lines = []
                    for msg in history:
                        role_label = "Usuario" if msg['role'] == 'user' else "Juan Pablo"
                        content_safe = str(msg.get('content', '')).replace('\n', ' ')
                        history_lines.append(f"- {role_label}: {content_safe}")

                    # Build from newest backwards until we hit the char cap
                    MAX_HISTORY_CHARS = 2000
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
                
                # Greeting Bypass Instruction
                if skip_greeting:
                    full_prompt += "\n[SYSTEM: STRICT RULE: DO NOT under any circumstance start your response with 'Hola', 'Buenos días', or any greeting. The conversation is ongoing. Jump straight into your answer.]\n"
                else:
                    # MANTENIBILIDAD & SEGURIDAD (QA Baseline):
                    # Por qué se hace: La instrucción de saludo solía anular las llamadas a herramientas 
                    # porque el LLM priorizaba escribir el texto del saludo. Esta modificación obliga
                    # al modelo a ejecutar primero search_catalog antes de generar su respuesta final.
                    full_prompt += "\n[SYSTEM: MANDATORY WARMTH: Preséntate de forma cálida y profesional como Juan Pablo, asesor de Auteco Las Motos. No seas parco ni directo. CRÍTICO: Si el usuario menciona una moto en este primer mensaje, DEBES usar la herramienta 'search_catalog' ANTES de generar tu saludo final.]\n"

                # V16 REMOVED — Sprint 1 (2026-03-13)
                # WHY REMOVED: SurveyService (the only caller of evaluate_survey_intent and
                # pending_survey_question) was deleted. The V16 interruption block became
                # unreachable dead code that could confuse future developers into re-activating
                # the old Python-level survey state machine.
                # Phase 3 context-switching is now handled entirely by the Firestore prompt
                # and the LLM's natural conversation management.

                # V17 REMOVED — 2026-03-12
                # WHY REMOVED: This block hardcoded '¡Claro que sí manejamos crédito!'
                # and explicitly told the LLM to NOT trigger Phase 2 (Data Policy).
                # It completely overrode the Firestore guardrail — a legal and business blocker.
                # Phase 2 and Phase 3 logic is now handled exclusively by the Firestore
                               # V18 - V22 (Incorporated into XML in prompts.py)
                # These were previously hardcoded here but are now part of the centralized
                # system_instruction to reduce context bloat and improve maintainability.
                
                # ... (Any remaining dynamic injections go here)
