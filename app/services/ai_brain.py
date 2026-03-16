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
        # Condition: User selected 'credito' AND we have name AND city AND moto_confirmada is True.
        # CRITICAL FIX: Extraction of moto_interest is not enough; explicit confirmation is required.
        has_name = bool(prospect_data.get("name"))
        has_city = bool(prospect_data.get("ciudad"))
        moto_confirmada = prospect_data.get("moto_confirmada") is True
        is_credit = prospect_data.get("payment_method") == "credito"

        if has_name and has_city and moto_confirmada and is_credit:
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

                # V18 - V22 (Incorporated into XML in prompts.py)
                # These were previously hardcoded here but are now part of the centralized
                # system_instruction to reduce context bloat and improve maintainability.
                
                if funnel_instruction:
                    full_prompt += funnel_instruction + "\n\n"
                    
                full_prompt += f"Usuario: {texto}\n\nJuan Pablo:"
                
                # 1. Send initial message
                response = chat.send_message(
                    full_prompt,
                    generation_config=GenerationConfig(temperature=0.2, max_output_tokens=8192)
                )
                
                # --- ROBUST TOOL EXECUTION LOOP ---
                # handles multiple tool-call/response cycles (e.g., comparisons)
                turns = 0
                max_turns = 3
                
                while turns < max_turns:
                    candidate = response.candidates[0]
                    function_calls = [part.function_call for part in candidate.content.parts if part.function_call]
                    
                    if not function_calls:
                        # No more tool calls, return final text
                        try:
                            ai_response = response.text.strip()
                            if not ai_response:
                                logger.warning("⚠️ Empty AI response (valid text but no content)")
                                return self._fallback_response(texto, history)
                            logger.info(f"✅ AI response generated after {turns} turns ({len(ai_response)} chars)")
                            return ai_response
                        except Exception as e:
                            logger.warning(f"⚠️ Empty reasoning response caught. Fallback injected. Error: {e}")
                            return "Lo siento, tuve un problema procesando esa información. ¿Podrías repetirme qué buscas para darte la mejor asesoría?"

                    logger.info(f"⚡ AI triggered {len(function_calls)} function call(s) (Turn {turns+1})")
                    response_parts = []
                    
                    for function_call in function_calls:
                        function_name = function_call.name
                        
                        # A) Human Handoff
                        if function_name == "trigger_human_handoff":
                            reason = function_call.args.get("reason", "unknown")
                            logger.warning(f"🚨 AI triggered human handoff | Reason: {reason}")
                            return f"HANDOFF_TRIGGERED:{reason}"
                        
                        # B) Catalog Search
                        elif function_name == "search_catalog":
                            query = function_call.args.get("query", "")
                            logger.info(f"🔎 AI searching catalog for: '{query}'")
                            
                            search_results = "No se encontraron resultados."
                            try:
                                if self.catalog_service:
                                    matches = self.catalog_service.search_items(query)
                                    if matches:
                                        search_results = f"Encontré {len(matches)} motos relacionadas:\n"
                                        for m in matches: 
                                            search_results += f"- {m['name']} ({m['category']}): {m['formatted_price']}\n"
                                            if m.get('image_url'):
                                                search_results += f"  Image URL: {m['image_url']}\n"
                                            if m.get('link'):
                                                search_results += f"  Link: {m['link']}\n"
                                            if m.get('specs'):
                                                specs = str(m['specs'])
                                                search_results += f"  Ficha Tecnica: {specs}\n"
                                                
                                        # -- CONTEXT INJECTOR PARA COMPETENCIA --
                                        competitor_brands = ["boxer", "nkd", "pulsar", "yamaha", "honda", "suzuki", "akt"]
                                        query_lower = query.lower()
                                        if any(brand in query_lower for brand in competitor_brands):
                                            pivot_warning = f"[SISTEMA: El usuario preguntó por la competencia. ESTÁS OBLIGADO a iniciar tu respuesta con: 'Te cuento que no manejamos la marca que mencionas, pero te tengo una excelente alternativa...']\n\n"
                                            search_results = pivot_warning + search_results
                                            logger.info(f"💉 Competitor pivot context injected into catalog results for query: '{query}'")

                                    else:
                                        search_results = "No encontré motos que coincidan con esa búsqueda. Intenta con otra categoría o nombre."
                                else:
                                    search_results = "Error: Servicio de catálogo no disponible."
                            except Exception as e:
                                logger.error(f"❌ Tool Execution Error (Catalog): {e}", exc_info=True)
                                search_results = "Tuve un problema consultando el catálogo momentáneamente. ¿Me podrías preguntar de nuevo?"
                            
                            # -- RECENCY BIAS FIX PARA EL EMBUDO --
                            search_results += f"\n\n{funnel_instruction}"
                            
                            tool_response_part = Part.from_function_response(
                                name=function_name,
                                response={"content": search_results}
                            )
                            response_parts.append(tool_response_part)

                        # C) Credit Calculation
                        elif function_name == "calculate_credit_score":
                            # Extraction and scores
                            ocupacion = function_call.args.get("ocupacion_y_contrato", "")
                            ingresos = function_call.args.get("ingresos_demostrables", "")
                            datacredito = function_call.args.get("historial_datacredito", "")
                            mora = function_call.args.get("mora_y_paz_salvo", "")
                            vivienda = function_call.args.get("gastos_vivienda", "")
                            gas = function_call.args.get("tiene_gas_natural", False)
                            celular = function_call.args.get("plan_celular", "")
                            
                            logger.info(f"💰 AI calculating credit score: Ocupacion={ocupacion}")
                            
                            credit_result = "No disponible."
                            try:
                                if self.motor_financiero:
                                    result = self.motor_financiero.evaluar_perfil(
                                        ocupacion_y_contrato=ocupacion,
                                        ingresos_demostrables=ingresos,
                                        historial_datacredito=datacredito,
                                        mora_y_paz_salvo=mora,
                                        gastos_vivienda=vivienda,
                                        tiene_gas_natural=gas,
                                        plan_celular=celular
                                    )
                                    credit_result = f"""
✅ Análisis de Crédito Completado:
- Score: {result['score']}/1000
- Estrategia: {result['strategy']}
- Entidad Recomendada: {result['entity']}
- Link de Solicitud: {result['link_url']}
- Explicación: {result['explanation']}

INSTRUCCIÓN PARA EL BOT: Usa esta información para responder al usuario. Si hay link, invítalo a dar clic.
                                    """.strip()
                                else:
                                    credit_result = "Error: Motor financiero no conectado."
                            except Exception as e:
                                logger.error(f"❌ Tool Execution Error (Credit): {e}", exc_info=True)
                                credit_result = "Error calculando el crédito."
                            
                            credit_result += f"\n\n{funnel_instruction}"

                            tool_response_part = Part.from_function_response(
                                name=function_name,
                                response={"content": credit_result}
                            )
                            response_parts.append(tool_response_part)

                    # Send responses back for next turn
                    if response_parts:
                        turns += 1
                        try:
                            response = chat.send_message(response_parts)
                        except InvalidArgument as e:
                            logger.error(f"❌ InvalidArgument in turn {turns}: {e}")
                            return "Tuve un problema procesando esa consulta compleja. ¿Me podrías preguntar algo más específico? 😅"
                    else:
                        break # Safety

                # End of loop
                return self._fallback_response(texto, history)
            
            except InvalidArgument as e:
                logger.error(f"❌ Invalid Argument (400) in AI attempt {attempt+1}: {e}")
                break
                
            except (ResourceExhausted, ServiceUnavailable) as e:
                wait_time = base_delay * (2 ** attempt)
                logger.warning(f"⏳ API Limit (429/503). Retrying in {wait_time}s... (Attempt {attempt+1}/{max_retries})")
                time.sleep(wait_time)
                
            except Exception as e:
                logger.error(f"❌ Error in AI attempt {attempt+1}: {e}", exc_info=True)
                break
        
        logger.error("❌ Failed to generate AI response after retries")
        return self._fallback_response(texto, history)

    def detect_sentiment(self, text: str) -> str:
        """
        Analyze sentiment of the user message.
        """
        if not self._model: return "NEUTRAL"
        try:
            chat = self._model.start_chat()
            response = chat.send_message(
                f"Analyze the sentiment of this text. Output ONLY one word: POSITIVE, NEUTRAL, NEGATIVE, or ANGRY.\nText: {text}"
            )
            return response.text.strip().upper()
        except:
            return "NEUTRAL"

    def generate_summary(self, conversation_text: str, last_bot_question: str = "") -> Dict[str, Any]:
        """
        Summarize the conversation and extract structured prospect data.

        Args:
            conversation_text: The raw conversation string to analyze.
            last_bot_question: AUDIT P2 (3.2 — Context Injection) — The last question the bot
                asked before the user's current reply. Injecting this anchors the extractor:
                when the only context is 'User: Orihueca' without knowing the bot asked about
                city, the LLM has no anchor to know which field that answer belongs to.
                Example: If last_bot_question='desde qué ciudad', the extractor correctly
                maps 'Orihueca' -> city instead of moto_interest.

        MANTENIBILIDAD & SEGURIDAD (QA Baseline):
        - Por qué se hace: Utilizamos `response_schema` nativo (Structured Outputs) para
          forzar al modelo de Gemini a generar un JSON garantizado y determinista, en lugar
          de Prompt Engineering + Regex (que era frágil e inseguro ante alucinaciones).
        - Impacto: Asegura que campos críticos del negocio como el perfil de crédito
          (ocupación, datacrédito) no se pierdan o malformen, permitiendo que `memory_service`
          los guarde correctamente en Firestore.
        """
        if not self._model:
            return {"summary": "", "extracted": {}}

        
        try:
            # AUDIT P2 (3.2): Inject last bot question as an anchor for field attribution.
            # Without this anchor, a user replying 'Orihueca' to 'desde qué ciudad' could be
            # mapped to moto_interest because the extractor reads the conversation linearly
            # without knowing which question triggered the response.
            question_context = ""
            if last_bot_question:
                question_context = f"""
⚠️ CONTEXTO CRÍTICO DE EXTRACCIÓN:
La Última pregunta que hizo el bot fue: "{last_bot_question}"
USA ESTE CONTEXTO para determinar a qué campo pertenece la respuesta más reciente del usuario.
Si la respuesta del usuario es claramente una ubicación geográfica y el bot acaba de preguntar
por la ciudad, mápeala a `city` y NO a `moto_interest`.
"""

            prompt = f"""
Eres Juan Pablo, el asistente virtual experto de Auteco Las Motos.
Tu misión es resumir la conversación con el cliente y extraer datos clave.

Analiza esta conversación y extrae la información indicada en el esquema JSON proporcionado.
Extrae ÚNICAMENTE información que el cliente haya mencionado explícitamente en la conversación.

REGLA DE ORO DE ESTABILIDAD: 
Si el mensaje del usuario es solo una reacción (ej: "👍", "Ok", "Vale", "Sí") o no contiene entidades nuevas para extraer, 
DEBES DEVOLVER EXACTAMENTE un objeto JSON vacío para el campo 'extracted': {{"summary": "...", "extracted": {{}} }}.
NUNCA devuelvas texto plano ni markdown fuera del JSON.

{question_context}
Conversación a analizar:
---
{conversation_text}
---
"""
            extraction_schema = {
                "type": "OBJECT",
                "properties": {
                    "summary": {
                        "type": "STRING",
                        "description": "Un resumen conciso (1-2 oraciones) del tema principal y datos clave de la conversación."
                    },
                    "extracted": {
                        "type": "OBJECT",
                        "properties": {
                            "name": {
                                "type": "STRING",
                                "description": "Nombre si se mencionó. IGNORA el nombre 'Juan Pablo', 'Auteco' o referencias al bot. SOLO extrae si el usuario se presenta a sí mismo."
                            },
                            "payment_method": {
                                "type": "STRING",
                                "description": "Método de pago si se mencionó (ej. crédito, contado, brilla, no sé)."
                            },
                            "city": {
                                "type": "STRING",
                                # AUDIT P2 (3.1 — Cross-Protection): Added moto exclusion.
                                # WHY: The inverse of the moto_interest bug. If the user answered
                                # a moto question with a model name, the extractor could store
                                # 'MRX' or 'Boxer' in the city field. Explicit exclusion prevents
                                # both fields from absorbing each other's entity type.
                                "description": "Ciudad de residencia o ubicación si el cliente la menciona. EXCLUSIÓN: NUNCA extraigas marcas ni modelos de motos (ej. Boxer, Pulsar, MRX, Raider) como ciudad. Solo valores geográficos válidos."
                            },
                            "moto_competidor": {
                                "type": "STRING",
                                "description": "Marcas o modelos de la COMPETENCIA mencionados por el usuario (ej. Boxer, NKD, Pulsar, Yamaha, AKT). Si el usuario inicialmente mostró interés en una marca que no manejamos, extráela aquí."
                            },
                            "moto_auteco": {
                                "type": "STRING",
                                "description": "Marcas o modelos de AUTECO (TVS, Victory, Kymco, KTM) mencionados, buscados o RECOMENDADOS por el bot durante un pivote (ej. MRX 150, Raider, Black). Si el bot sugirió una alternativa de nuestro catálogo, extráela aquí."
                            },
                            "moto_interest": {
                                "type": "STRING",
                                "description": "Modelo de moto principal para el interés del cliente. Prioriza el modelo de Auteco si ya hubo un pivote o recomendación clara. REGLAS: IGNORA ciudades y términos financieros."
                            },
                            "moto_confirmada": {
                                "type": "BOOLEAN",
                                "description": "true SOLO si el usuario confirma EXPLÍCITAMENTE que quiere esa moto o que quiere iniciar el crédito con ese modelo (ej. 'Quiero esta', 'Sí, esa me sirve', 'Iniciemos crédito con la Raider'). Si pide ver otras o solo pregunta pero no confirma, pon false."
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
                                "description": "Tipo de vivienda si vive con familiares, arrendado o es propia. (ej. Arriendo, Familiar, Propia)."
                            },
                            "ingresos": {
                                "type": "STRING",
                                "description": "Ingresos mensuales demostrables (ej. 1705905, un minimo, 2 millones)."
                            },
                            "gastos": {
                                "type": "STRING",
                                "description": "Gastos mensuales fijos, como arriendo o cuotas (ej. 500mil, 1 millon)."
                            },
                            "gas_natural": {
                                # AUDIT P2 (3.1 — Type Mismatch Fix): Changed STRING -> BOOLEAN.
                                # WHY: calculate_credit_score uses gas_natural as a boolean flag
                                # in the financial scoring matrix. Storing it as a STRING ('Si'/'No')
                                # meant memory_service had to guess-convert the value, introducing
                                # a silent data-quality risk. Using BOOLEAN at extraction time
                                # ensures the downstream credit tool gets a clean true/false.
                                "type": "BOOLEAN",
                                "description": "true si la persona tiene o paga recibo de gas natural a su nombre. false si no. Solo extrae si se menciona explícitamente."
                            },
                            "plan_celular": {
                                "type": "STRING",
                                "description": "Tipo de plan de telefonia movil (ej. Prepago, Postpago)."
                            },
                            "habeas_data_sent": {
                                "type": "BOOLEAN",
                                "description": "true si el bot ENVIÓ el script de Habeas Data en este turno o antes. false si no."
                            },
                            "habeas_data_accepted": {
                                "type": "BOOLEAN",
                                "description": "true si el usuario ACEPTÓ explícitamente el Habeas Data (ej. 'si acepto', 'autorizo'). false si no."
                            }
                        }
                    }
                },
                "required": ["summary", "extracted"]
            }

            from vertexai.generative_models import GenerationConfig
            
            # MANTENIBILIDAD & SEGURIDAD (QA Baseline):
            # Exigimos explícitamente max_output_tokens=1024 para prevenir interrupciones y permitir
            # que el modelo asuma el schema de extracción complejo sin truncamiento.
            # Nota: Usamos generate_content porque el resumen es una tarea stateless.
            response = self._model.generate_content(
                prompt,
                generation_config=GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=1024,
                    response_mime_type="application/json",
                    response_schema=extraction_schema
                )
            )
            
            import json
            import re
            
            raw_response = response.text.strip()
            
            # Robust JSON Extraction Logic (QA Security & Stability Baseline)
            # 1. Clean markdown artifacts (e.g., ```json ... ```)
            raw_response = re.sub(r'```(?:json)?\s*', '', raw_response)
            raw_response = re.sub(r'\s*```', '', raw_response).strip()
            
            try:
                # Stage 1: Standard JSON parse
                result = json.loads(raw_response)
            except json.JSONDecodeError:
                logger.warning("⚠️ Native JSON parse failed, attempting extraction/repair.")
                try:
                    # Stage 2: Extract block using the first { and last } boundaries
                    # This handles conversational prefixes or suffixes that Gemini might add.
                    start_idx = raw_response.find('{')
                    end_idx = raw_response.rfind('}')
                    
                    if start_idx != -1 and end_idx != -1:
                        block = raw_response[start_idx:end_idx+1]
                        # Attempt to fix common "Unterminated string" error by closing quotes
                        if block.count('"') % 2 != 0: block += '"'
                        # Ensure braces are balanced (basic repair)
                        while block.count('{') > block.count('}'): block += '}'
                        
                        result = json.loads(block)
                    else:
                        raise ValueError("No matching JSON braces found in response")
                except Exception as repair_err:
                    logger.error(f"❌ JSON Repair failed: {repair_err}. Falling back to empty structure.")
                    result = {"summary": "Error parsing AI response", "extracted": {}}
            
            if "summary" not in result: result["summary"] = ""
            if "extracted" not in result: result["extracted"] = {}
            
            logger.info(f"📝 Generated summary with {len(result.get('extracted', {}))} extracted fields")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error generating summary: {str(e)}", exc_info=True)
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

