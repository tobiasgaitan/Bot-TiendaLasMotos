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
    
    def pensar_respuesta(self, texto: str, context: str = "", prospect_data: Optional[Dict[str, Any]] = None, history: list = [], skip_greeting: bool = False, pending_survey_question: Optional[str] = None) -> str:
        """
        Generate an intelligent response using Gemini AI with Retry Logic.
        """
        return self._generate_with_retry(texto, context, prospect_data, history, skip_greeting, pending_survey_question)

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
                description="Search for motorcycles in the catalog using a query string. Use this to find prices, specs, and models. REGLA DE ORO INQUEBRANTABLE: NUNCA asumas el inventario ni ofrezcas motos basándote en tu conocimiento general de internet. Si el usuario menciona CUALQUIER marca, modelo o estilo de moto, ESTÁS OBLIGADO a usar la herramienta search_catalog antes de responder. PROHIBIDO ofrecer motos de la competencia que no estén en los resultados de la herramienta.",
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
            logger.error(f"❌ Error creating tools: {str(e)}", exc_info=True)
            return None

    def _generate_with_retry(self, texto: str, context: str, prospect_data: Optional[Dict[str, Any]] = None, history: list = [], skip_greeting: bool = False, pending_survey_question: Optional[str] = None) -> str:
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

                # -- EVALUACION DETERMINISTA DEL EMBUDO DE VENTAS --
                # POR QUÉ: Los LLM estocásticos fallan evaluando la instrucción condicional (ej. "pregunte A si falta A, sino B").
                # LÓGICA DE NEGOCIO: Retiramos la ponderación lógica de Gemini y computamos matemáticamente la siguiente
                # pregunta de cierre obligatoria basándonos íntegramente en los datos en duro extraídos (prospect_data).
                funnel_instruction = ""
                if prospect_data:
                    p_name = prospect_data.get("name")
                    p_ciudad = prospect_data.get("ciudad")
                    p_payment = prospect_data.get("payment_method")
                    
                    if not p_name:
                        funnel_instruction = "\n\n[SISTEMA - REGLA DE CIERRE OBLIGATORIA: El sistema CRM detectó que aún no sabemos el nombre del cliente. ESTÁS ESTRICTAMENTE OBLIGADO a cerrar tu mensaje preguntando: 'Por cierto, ¿con quién tengo el gusto?' o algo muy similar.]"
                    elif not p_ciudad:
                        funnel_instruction = "\n\n[SISTEMA - REGLA DE CIERRE OBLIGATORIA: El sistema CRM detectó que no sabemos la ciudad del cliente. ESTÁS ESTRICTAMENTE OBLIGADO a cerrar tu mensaje preguntando: '¿Desde qué ciudad nos escribes?' o algo muy similar.]"
                    elif not p_payment:
                        funnel_instruction = "\n\n[SISTEMA - REGLA DE CIERRE OBLIGATORIA: El sistema CRM detectó que no sabemos cómo planea pagar. ESTÁS ESTRICTAMENTE OBLIGADO a cerrar tu mensaje preguntando: '¿Tienes pensado comprarla de contado o prefieres a crédito?']"
                
                full_prompt = f"{self._system_instruction}\n\n"
                
                # Identity Guard
                full_prompt += "Your name is Juan Pablo. NEVER address the user as Juan Pablo.\n"
                
                # Inject prospect data for personalization
                if prospect_data and prospect_data.get("exists"):
                    user_name = prospect_data.get("name", "")
                    full_prompt += "═══════════════════════════════════════════════════════════════════\n"
                    full_prompt += "INFORMACIÓN DEL PROSPECTO (CRM):\n"
                    if user_name:
                        full_prompt += f"- Nombre: {user_name}\n"
                    if prospect_data.get("moto_interest"):
                        full_prompt += f"- Interés en moto: {prospect_data['moto_interest']}\n"
                    if prospect_data.get("summary"):
                        full_prompt += f"- Resumen previo: {prospect_data['summary']}\n"
                    
                    full_prompt += f"\n⚠️ INSTRUCCIÓN DE IDENTIDAD: El nombre del usuario es {user_name if user_name else 'desconocido'}.\n"
                    full_prompt += "Siempre dirígete a ellos con respeto usando 'Señor [Nombre]' o 'Señora [Nombre]' según corresponda (Heurística: nombre terminado en 'a' suele ser Señora).\n"
                    full_prompt += "Ejemplo: '¡Hola Señor Juan!' o 'Dígame Señora Maria...'\n"
                    full_prompt += "Verifica cortésmente si la información sigue vigente si lo consideras necesario.\n"
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
                    full_prompt += "\n[SYSTEM: STRICT RULE: DO NOT under any circumstance start your response with 'Hola', 'Buenos días', or any greeting. The conversation is ongoing. Jump straight into your answer.]\n"
                else:
                    full_prompt += "\n[SYSTEM: MANDATORY WARMTH: Preséntate de forma cálida y profesional como Juan Pablo, asesor de Auteco Las Motos. No seas parco ni directo; usa un tono de bienvenida y menciona la marca Auteco Las Motos.]\n"

                # V16 - Context Switching (Interruption handling)
                if pending_survey_question:
                    full_prompt += "═══════════════════════════════════════════════════════════════════\n"
                    full_prompt += "⚠️ CONTEXTO DE INTERRUPCIÓN (ENCUESTA EN CURSO):\n"
                    full_prompt += f"El usuario estaba respondiendo a esta pregunta: '{pending_survey_question}'\n"
                    full_prompt += "pero ahora acaba de enviar un mensaje diferente o aleatorio.\n\n"
                    full_prompt += "INSTRUCCIONES CRÍTICAS:\n"
                    full_prompt += "1. Tienes HERRAMIENTAS (Tools) disponibles. Úsalas normalmente para obtener datos PRIMERO si es necesario.\n"
                    full_prompt += "2. Solo cuando estés redactando tu respuesta de texto FINAL al usuario, debes retomar el hilo.\n"
                    full_prompt += f"3. Al FINAL de tu mensaje de texto definitivo, debes volver a preguntar EXACTAMENTE: '{pending_survey_question}'\n"
                    full_prompt += "Ejemplo: 'Claro que sí, [respuesta]. Por cierto, para seguir con tu crédito, ¿me recordabas [pregunta pendiente]?'\n"
                    full_prompt += "═══════════════════════════════════════════════════════════════════\n\n"

                # V17 - Survey Trigger Enforcement
                full_prompt += "═══════════════════════════════════════════════════════════════════\n"
                full_prompt += "🚨 V17 - MANEJO DE SOLICITUDES DE CRÉDITO (PASIVO):\n"
                full_prompt += "Si el cliente menciona 'Crédito', 'Brilla' o 'Financiar', NO DISPARES NINGUNA HERRAMIENTA NI ENCUESTA.\n"
                full_prompt += "Tu ÚNICA tarea es continuar con el Embudo de Conversación (Fase 1).\n"
                full_prompt += "Si te piden crédito, responde con entusiasmo ('¡Claro que sí manejamos crédito!') y luego INMEDIATAMENTE haz la pregunta del Objetivo que te falte (Ej. '¿Con quién tengo el gusto?' o '¿Qué moto tienes en mente?').\n"
                full_prompt += "Bajo ninguna circunstancia intentes iniciar el formulario formal tú mismo. Mantén la conversación fluida.\n"
                full_prompt += "═══════════════════════════════════════════════════════════════════\n\n"

                # V18 - Hallucination Guardrail
                full_prompt += "═══════════════════════════════════════════════════════════════════\n"
                full_prompt += "🔒 CRITICAL RULE (ANTI-HALLUCINATION):\n"
                full_prompt += "- When providing motorcycle prices, colors, or technical specifications, YOU MUST ONLY use the exact data provided by the catalog tool.\n"
                full_prompt += "- NEVER hallucinate, guess, or use external knowledge for prices or specs.\n"
                full_prompt += "- If the tool does not provide the info, state clearly that you don't have that specific detail at the moment.\n"
                full_prompt += "═══════════════════════════════════════════════════════════════════\n\n"

                # V19 - Native Image Integration
                full_prompt += "═══════════════════════════════════════════════════════════════════\n"
                full_prompt += "📸 INTEGRACIÓN DE IMÁGENES:\n"
                full_prompt += "- Si tienes disponible un 'Image URL' de la moto proporcionado por el catálogo, DEBES incluir en tu respuesta exactamente la etiqueta `[IMAGE: url]`.\n"
                full_prompt += "- Solo incluye esta etiqueta UNA VEZ por recomendación de moto para no saturar el chat.\n"
                full_prompt += "═══════════════════════════════════════════════════════════════════\n\n"

                # V20 - Protocolo de Memes/Stickers
                full_prompt += "═══════════════════════════════════════════════════════════════════\n"
                full_prompt += "🎭 PROTOCOLO DE MEMES/STICKERS (VISIÓN AI):\n"
                full_prompt += "- Si el usuario envía una imagen o sticker, recibirás un `[System Note: ... Sentiment: ...]`. ¡NO lo ignores ni lo repitas al usuario!\n"
                full_prompt += "- Si Sentiment = 'Sad' o 'Frustrated': Empatiza profundamente con el cliente y ofrécele INMEDIATAMENTE alternativas de financiación o pago a cuotas como 'Crédito Brilla' o 'Codeudor'.\n"
                full_prompt += "- Si Sentiment = 'Happy' o 'Excited': ¡Celebra su alegría con mucho entusiasmo! Y procede a intentar cerrar la venta ofreciendo el enlace de pago seguro inmediatamente.\n"
                full_prompt += "- Si Sentiment = 'Neutral' o poco claro: Responde con naturalidad, haz un comentario corto, amigable o ligeramente humorístico sobre el sticker/imagen, y guía suavemente la conversación de vuelta a las motos.\n"
                full_prompt += "═══════════════════════════════════════════════════════════════════\n\n"

                # V21 - FAQ de Financiación
                full_prompt += "═══════════════════════════════════════════════════════════════════\n"
                full_prompt += "📚 V21 - BASE DE CONOCIMIENTO: FAQ DE FINANCIACIÓN\n"
                full_prompt += "Usa esta información ÚNICAMENTE para responder preguntas específicas que haga el usuario. Tu respuesta debe ser breve y amigable. \n"
                full_prompt += "MUY IMPORTANTE: NO comiences a pedirle su perfil o documentos para el crédito conversacionalmente. Una vez que resuelvas su duda, pregúntale amablemente si está listo para iniciar la solicitud de crédito formal (la cual disparará nuestra encuesta automatizada).\n\n"
                full_prompt += "- REGLAS GENERALES: El estudio de crédito es 100% GRATIS. Normalmente NO se necesita codeudor. Se recomienda contar con un 10% de cuota inicial.\n"
                full_prompt += "- ALIADOS:\n"
                full_prompt += "  * Brilla: (Recibo del gas + Cédula + 2 recibos pagados).\n"
                full_prompt += "  * Addi/Sistecrédito: (Proceso 100% Virtual, Cédula, WhatsApp).\n"
                full_prompt += "  * ProgreSER: (Financia hasta el 100%).\n"
                full_prompt += "  * Galgo: (Ideal para Independientes/Mensajeros).\n"
                full_prompt += "  * Crediorbe: (Aceptan personas reportadas, requiere 10% de cuota inicial).\n"
                full_prompt += "- PERFILES ESPECIALES:\n"
                full_prompt += "  * Reportados: SÍ pueden acceder a crédito (requiere 10% de cuota inicial).\n"
                full_prompt += "  * Extranjeros: Necesitan PPT/PEP + Pasaporte + Dirección local.\n"
                full_prompt += "═══════════════════════════════════════════════════════════════════\n\n"

                if funnel_instruction:
                    full_prompt += funnel_instruction + "\n\n"
                    
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
                            search_results += funnel_instruction
                            
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
                                logger.error(f"❌ Tool Execution Error (Credit): {e}", exc_info=True)
                                credit_result = "Error calculando el crédito. Intenta de nuevo."
                            
                            # -- RECENCY BIAS FIX PARA EL EMBUDO --
                            credit_result += funnel_instruction

                            tool_response_part = Part.from_function_response(
                                name=function_name,
                                response={
                                    "content": credit_result
                                }
                            )
                            response_parts.append(tool_response_part)

                        # D) Start Credit Survey
                        elif function_name == "start_credit_survey":
                            intent = function_call.args.get("intent", "generic_credit")
                            logger.info(f"📋 AI triggering formal survey initiation. Intent: {intent}")
                            # This special flag will be caught by the router to transition to SurveyService
                            return f"TRIGGER_SURVEY:financial_capture"
                    
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
Eres Juan Pablo, el asistente virtual experto de Auteco Las Motos.
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
    "name": "nombre si se mencionó. IGNORA el nombre 'Juan Pablo', 'Auteco' o cualquier referencia al asesor/bot. SOLO extrae el nombre si el usuario se presenta a sí mismo (ej. 'Soy Tobias', 'Mi nombre es...').",
    "city": "ciudad si se mencionó (ej. Bogotá, Medellín)",
    "payment_method": "método de pago si se mencionó (ej. crédito, contado, brilla, no sé)",
    "moto_interest": "Extrae ÚNICAMENTE referencias, marcas o estilos reales de motos (ej. Boxer, Pulsar, NKD, Scooter, Deportiva). IGNORA y NUNCA extraigas términos financieros o de pago aquí."
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
            prompt = f"""
You are an Intent Evaluator and Data Sanitizer.
Analyze the user's message relative to the pending survey question.

PENDING QUESTION: "{pending_question}"
USER MESSAGE: "{user_message}"

MISSION:
1. Determine if they are answering the question (TRUE) or asking something else (FALSE).
2. If TRUE, extract and sanitize the value (e.g. "Gano el minimo" -> "1300000", "estudio" -> "Estudiante").
3. Return ONLY the format: STATUS|VALUE

EXAMPLES:
Question: "¿Cuanto ganas?" | Msg: "El minimo" -> TRUE|1300000
Question: "¿A que te dedicas?" | Msg: "Trabajo en una oficina" -> TRUE|Empleado
Question: "¿Cuanto ganas?" | Msg: "Donde estan ubicados?" -> FALSE|None

Respond ONLY with STATUS|VALUE.
"""
            # Zero-shot bridge evaluation
            response = self._model.generate_content(prompt)
            
            if not response or not hasattr(response, 'text') or not response.text:
                logger.warning("⚠️ Intent Evaluator returned NO text.")
                return default_fallback
                
            response_text = response.text.strip()
            
            # Bridge Parsing (STATUS|VALUE)
            if "|" in response_text:
                status_part, value_part = response_text.split("|", 1)
                is_answering = "TRUE" in status_part.upper()
                sanitized_value = value_part.strip()
            else:
                is_answering = "TRUE" in response_text.upper()
                sanitized_value = user_message # Fallback to original
            
            logger.info(f"🧠 Intent Bridge Result: {is_answering} | Sanitized: {sanitized_value}")
            
            return {
                "is_answering_survey": is_answering,
                "sanitized_value": sanitized_value,
                "reasoning": "Intent Bridge Sanitization"
            }
            
        except Exception as e:
            logger.error(f"❌ Error during Intent Evaluation: {e}. Defaulting to Fail-Closed (True).", exc_info=True)
            return default_fallback


