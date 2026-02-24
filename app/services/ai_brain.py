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
        self.motor_financiero = None # Will be injected
        self._model = None
        self._system_instruction = self._get_system_instruction()
        self.tools = self._create_tools()
        
        # Initialize Vertex AI if available
        if VERTEX_AI_AVAILABLE:
            try:
                vertexai.init(project="tiendalasmotos", location="us-central1")
                # Initialize model WITH tools
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
    
    def _get_system_instruction(self) -> str:
        """
        Get system instruction with fallback strategy:
        1. Firestore Config (via ConfigLoader) - Dynamic
        2. Local JSON file - Robust Fallback
        3. Code Constant - Last Resort
        """
        instruction = ""
        
        # 1. Try ConfigLoader (Firestore)
        if self.config_loader:
            try:
                # FIX: Correct method name and dictionary access
                personality = self.config_loader.get_juan_pablo_personality()
                instruction = personality.get("system_instruction", "")
                if instruction:
                    logger.info("🧠 Loaded system instruction from Firestore Config")
                    return instruction
            except Exception as e:
                logger.warning(f"⚠️ Failed to load prompt from ConfigLoader: {e}")

        # 2. Try JSON File
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

        # 3. Fallback to constant
        from app.core.prompts import JUAN_PABLO_SYSTEM_INSTRUCTION
        logger.info("🧠 Loaded system instruction from code constant (Fallback)")
        return JUAN_PABLO_SYSTEM_INSTRUCTION

    def _default_instruction(self) -> str:
        return self._get_system_instruction()
    
    def pensar_respuesta(self, texto: str, context: str = "", prospect_data: Optional[Dict[str, Any]] = None, history: list = [], skip_greeting: bool = False) -> str:
        """
        Generate an intelligent response using Gemini AI with Retry Logic.
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
            handoff_function = FunctionDeclaration(
                name="trigger_human_handoff",
                description="Escalate conversation to a human agent when user requests human assistance or query is too complex",
                parameters={
                    "type": "object",
                    "properties": {
                        "reason": {
                            "type": "string",
                            "description": "Reason for handoff (e.g., 'user_request', 'complex_query', 'technical_question')"
                        }
                    },
                    "required": ["reason"]
                }
            )

            # Define catalog search function
            catalog_function = FunctionDeclaration(
                name="search_catalog",
                description="Search for motorcycles in the catalog using a query string. Use this to find prices, specs, and models.",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query (e.g., 'NKD 125', 'motos deportivas', 'precio de la Victory')"
                        }
                    },
                    "required": ["query"]
                }
            )
            
            # Define credit calculation function
            credit_function = FunctionDeclaration(
                name="calculate_credit_score",
                description="Calculate credit score and financing strategy based on user profile. Returns score, entity, and application link.",
                parameters={
                    "type": "object",
                    "properties": {
                        "ocupacion_y_contrato": {
                            "type": "string",
                            "description": "Ocupación y tipo de contrato (e.g., 'Empleado fijo', 'Independiente', 'Pensionado')"
                        },
                        "ingresos_demostrables": {
                            "type": "string",
                            "description": "Nivel de ingresos (e.g., 'Minimo', '1750905')"
                        },
                        "historial_datacredito": {
                            "type": "string",
                            "description": "Estado en Datacrédito (e.g., 'Al dia', 'Reportado', 'Sin experiencia')"
                        },
                        "mora_y_paz_salvo": {
                            "type": "string",
                            "description": "Detalles de mora (>30 días) y Paz y Salvo. Opciones: 'Sin mora', 'Con mora y paz y salvo', 'Con mora sin paz y salvo'"
                        },
                        "gastos_vivienda": {
                            "type": "string",
                            "description": "Gastos de vivienda (e.g., 'Familiar', 'Arriendo 500k')"
                        },
                        "tiene_gas_natural": {
                            "type": "boolean",
                            "description": "Indica si tiene recibo de Gas Natural a su nombre (true o false)"
                        },
                        "plan_celular": {
                            "type": "string",
                            "description": "Tipo de plan de celular (e.g., 'Postpago', 'Prepago')"
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
            logger.error(f"❌ Error creating tools: {str(e)}")
            return None

    def _generate_with_retry(self, texto: str, context: str, prospect_data: Optional[Dict[str, Any]] = None, history: list = [], skip_greeting: bool = False) -> str:
        """
        Internal generation with exponential backoff.
        """
        if not self._model: return self._fallback_response(texto, history)
        
        max_retries = 3
        base_delay = 2 
        
        import time
        from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable, InvalidArgument

        for attempt in range(max_retries):
            try:
                chat = self._model.start_chat()
                
                full_prompt = f"{self._system_instruction}\n\n"
                
                # Identity Guard
                full_prompt += "Your name is Juan Pablo. NEVER address the user as Juan Pablo.\n"
                
                # Inject prospect data for personalization
                if prospect_data and prospect_data.get("exists"):
                    full_prompt += "═══════════════════════════════════════════════════════════════════\n"
                    full_prompt += "INFORMACIÓN DEL PROSPECTO (CRM):\n"
                    if prospect_data.get("name"):
                        full_prompt += f"- Nombre: {prospect_data['name']}\n"
                    if prospect_data.get("moto_interest"):
                        full_prompt += f"- Interés en moto: {prospect_data['moto_interest']}\n"
                    if prospect_data.get("summary"):
                        full_prompt += f"- Resumen previo: {prospect_data['summary']}\n"
                    full_prompt += "\n⚠️ INSTRUCCIÓN: Usa esta información para personalizar tu saludo y respuesta.\n"
                    full_prompt += "Ejemplo: '¡Hola {nombre}! Vi que te interesa la {moto}...'\n"
                    full_prompt += "Verifica cortésmente si la información sigue vigente.\n"
                    full_prompt += "═══════════════════════════════════════════════════════════════════\n\n"
                
                # Inject Chat History (Recent Context)
                if history:
                    full_prompt += "📜 HISTORIAL RECIENTE (Últimos mensajes):\n"
                    for msg in history:
                        role_label = "Usuario" if msg['role'] == 'user' else "Juan Pablo"
                        content_safe = str(msg.get('content', '')).replace('\n', ' ')
                        full_prompt += f"- {role_label}: {content_safe}\n"
                    full_prompt += "═══════════════════════════════════════════════════════════════════\n\n"

                if context:
                    full_prompt += f"RESUMEN CONVERSACIÓN ANTERIOR (Largo Plazo):\n{context}\n\n"
                
                # Greeting Bypass Instruction
                if skip_greeting:
                    full_prompt += "\n[SYSTEM: Omit introductory greetings. Respond directly to the user's query as the conversation is ongoing. KEEP IT SHORT.]\n"

                full_prompt += f"Usuario: {texto}\n\nJuan Pablo:"
                
                # 1. Send initial message
                response = chat.send_message(
                    full_prompt,
                    generation_config=GenerationConfig(temperature=0.2, max_output_tokens=1000)
                )
                
                # 2. Check for Function Call(s)
                candidate = response.candidates[0]
                function_calls = [part.function_call for part in candidate.content.parts if part.function_call]
                
                if function_calls:
                    logger.info(f"⚡ AI triggered {len(function_calls)} function call(s)")
                    response_parts = []
                    
                    for function_call in function_calls:
                        function_name = function_call.name
                        
                        # A) Human Handoff
                        if function_name == "trigger_human_handoff":
                            reason = function_call.args.get("reason", "unknown")
                            logger.warning(f"🚨 AI triggered human handoff | Reason: {reason}")
                            # Special case: If handoff is triggered, we can stop immediately or process others.
                            # For safety, we'll return immediately as this overrides other actions.
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
                                            if m.get('specs'):
                                                specs = str(m['specs'])
                                                search_results += f"  Info: {specs}\n"
                                    else:
                                        search_results = "No encontré motos que coincidan con esa búsqueda. Intenta con otra categoría o nombre."
                                else:
                                    search_results = "Error: Servicio de catálogo no disponible."
                            except Exception as e:
                                logger.error(f"❌ Tool Execution Error (Catalog): {e}")
                                search_results = "Tuve un problema consultando el catálogo momentáneamente. ¿Me podrías preguntar de nuevo?"
                            
                            logger.info(f"📤 Preparing tool response for '{query}'...") 
                            
                            tool_response_part = Part.from_function_response(
                                name=function_name,
                                response={
                                    "content": search_results 
                                }
                            )
                            response_parts.append(tool_response_part)

                        # C) Credit Calculation
                        elif function_name == "calculate_credit_score":
                            ocupacion = function_call.args.get("ocupacion_y_contrato", "")
                            ingresos = function_call.args.get("ingresos_demostrables", "")
                            datacredito = function_call.args.get("historial_datacredito", "")
                            mora = function_call.args.get("mora_y_paz_salvo", "")
                            vivienda = function_call.args.get("gastos_vivienda", "")
                            gas = function_call.args.get("tiene_gas_natural", False)
                            celular = function_call.args.get("plan_celular", "")
                            
                            logger.info(f"💰 AI calculating credit score: Ocupacion={ocupacion}, Ingresos={ingresos}, Datacredito={datacredito}, Gas={gas}")
                            
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
                                logger.error(f"❌ Tool Execution Error (Credit): {e}")
                                credit_result = "Error calculando el crédito. Intenta de nuevo."
                            
                            tool_response_part = Part.from_function_response(
                                name=function_name,
                                response={
                                    "content": credit_result
                                }
                            )
                            response_parts.append(tool_response_part)
                    
                    # Send ALL responses back to the model in a single turn
                    if response_parts:
                        logger.info(f"📤 Sending {len(response_parts)} tool responses to AI...")
                        final_response = chat.send_message(response_parts)
                        return final_response.text.strip()
                
                # Normal text response
                try:
                    ai_response = response.text.strip()
                    if not ai_response:
                        logger.warning("⚠️ Empty AI response (valid text but no content)")
                        return self._fallback_response(texto, history)
                except Exception as e:
                    # Mantenibilidad & Seguridad (QA Baseline):
                    # Handle Gemini reasoning engine edge case where thoughts_token_count > 0 
                    # but text is empty, causing Vertex AI SDK to raise exceptions when accessing .text.
                    logger.warning(f"⚠️ Empty reasoning response caught. Fallback injected. Error: {e}")
                    return "¡Qué buena máquina, parcero! Esa no la manejo, pero tengo opciones equivalentes en nuestro catálogo. ¿Te gustaría que busquemos una parecida?"
                        
                logger.info(f"✅ AI response generated ({len(ai_response)} chars)")
                return ai_response
            
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

    def generate_summary(self, conversation_text: str) -> Dict[str, Any]:
        """
        Summarize the conversation and extract structured data.
        """
        if not self._model:
            return {"summary": "", "extracted": {}}
        
        try:
            chat = self._model.start_chat()
            prompt = f"""
Eres Juan Pablo, el asistente virtual experto de Tienda Las Motos.
Tu misión es resumir la conversación con el cliente y extraer datos clave.

Analiza esta conversación y genera:
1. Un resumen conciso (1-2 oraciones) del tema principal y datos clave
2. Extrae información estructurada si está presente

Conversación:
{conversation_text}

Responde en formato JSON:
{{
  "summary": "resumen aquí",
  "extracted": {{
    "name": "nombre si se mencionó",
    "moto_interest": "modelo de moto si se mencionó"
  }}
}}
"""
            response = chat.send_message(prompt)
            response_text = response.text.strip()
            
            import json
            import re
            json_match = re.search(r'```(?:json)?\s*({.*?})\s*```', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(1)
            
            result = json.loads(response_text)
            
            if "summary" not in result: result["summary"] = ""
            if "extracted" not in result: result["extracted"] = {}
            
            logger.info(f"📝 Generated summary with {len(result.get('extracted', {}))} extracted fields")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error generating summary: {str(e)}")
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

    def evaluate_survey_intent(self, user_message: str, pending_question: str) -> Dict[str, Any]:
        """
        (V16 - Context Switching)
        Fast, deterministic AI function that evaluates if the user's message is answering 
        the current survey question OR asking an unrelated question (Context Switch).
        
        Security & Continuity (QA Baseline):
        Implements a strict Fail-Closed paradigm. If the model fails (timeout, quota, 
        malformed JSON), it defaults to `is_answering_survey: True`. This prevents 
        a temporary API failure from incorrectly booting the user out of the survey flow.
        
        Args:
            user_message: The message received from the user
            pending_question: The specific survey question they should be answering
            
        Returns:
            Dict containing 'is_answering_survey' (bool) and 'reasoning' (str).
        """
        default_fallback = {
            "is_answering_survey": True,
            "reasoning": "Fallback due to AI evaluation failure (Fail-Closed)"
        }
        
        if not self._model:
            logger.warning("⚠️ Cannot evaluate survey intent (AI unavailable), returning Fail-Closed fallback")
            return default_fallback
            
        try:
            chat = self._model.start_chat()
            
            prompt = f"""
You are an Intent Evaluator Classifier for a motorcycle dealership virtual assistant.
Your ONLY job is to determine if the user's message is an attempt to answer the currently pending survey question, OR if the user is asking a completely unrelated question (initiating a Context Switch).

PENDING QUESTION TO THE USER: "{pending_question}"
USER'S MESSAGE: "{user_message}"

CRITERIA:
- Return True if the user is attempting to answer the question, even if the answer is vague, incomplete, or variations of "I don't know".
- Return False ONLY if the user is completely ignoring the question to ask something entirely different (e.g., asking for the price of a motorcycle, asking where the store is located, asking about a different topic).

Respond in JSON format exactly like this:
{{
    "is_answering_survey": boolean,
    "reasoning": "string explaining why"
}}
"""
            # Request specific JSON response using GenerationConfig
            response = chat.send_message(
                prompt,
                generation_config=GenerationConfig(
                    temperature=0.0, # Deterministic
                    response_mime_type="application/json"
                )
            )
            
            response_text = response.text.strip()
            
            # Clean up potential markdown formatting a round JSON
            import json
            import re
            json_match = re.search(r'(\{.*\})', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(1)
                
            result = json.loads(response_text)
            
            # Ensure required fields exist
            if "is_answering_survey" not in result or "reasoning" not in result:
                raise ValueError("JSON missing required fields")
                
            # Log the decision
            intent_type = "ANSWERING_SURVEY" if result["is_answering_survey"] else "CONTEXT_SWITCH"
            logger.info(f"🧭 Intent Evaluator Decision: {intent_type} | Reason: {result['reasoning']}")
            
            return {
                "is_answering_survey": bool(result["is_answering_survey"]),
                "reasoning": str(result["reasoning"])
            }
            
        except Exception as e:
            logger.error(f"❌ Error during Intent Evaluation: {e}. Defaulting to Fail-Closed (True).", exc_info=True)
            return default_fallback


