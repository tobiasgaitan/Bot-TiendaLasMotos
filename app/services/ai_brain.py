"""
Cerebro IA - AI Brain Service
Handles intelligent responses using Google Gemini AI for general inquiries.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import Vertex AI
try:
    import vertexai
    from vertexai.generative_models import (
        GenerativeModel,
        Tool,
        FunctionDeclaration,
        Content,
        Part
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
    
    def __init__(self, config_loader=None):
        """
        Initialize the AI brain.
        
        Args:
            config_loader: Optional ConfigLoader instance for dynamic personality
        """
        self._config_loader = config_loader
        self._model = None
        self._system_instruction = self._get_system_instruction()
        self._tools = self._create_tools()
        
        # Initialize Vertex AI if available
        if VERTEX_AI_AVAILABLE:
            try:
                vertexai.init(project="tiendalasmotos", location="us-central1")
                # Initialize model with tools for function calling
                self._model = GenerativeModel(
                    "gemini-2.5-flash",
                    tools=[self._tools] if self._tools else None
                )
                logger.info("🧠 CerebroIA initialized with Gemini 2.5 Flash + Human Handoff Tool")
            except Exception as e:
                logger.error(f"❌ Error initializing Vertex AI: {str(e)}")
                self._model = None
        else:
            logger.warning("⚠️  CerebroIA running in fallback mode (no AI)")
    
    def _get_system_instruction(self) -> str:
        """
        Get system instruction from config or use default.
        
        Returns:
            System instruction prompt for the AI
        """
        if self._config_loader:
            try:
                personality = self._config_loader.get_sebas_personality()
                return personality.get("system_instruction", self._default_instruction())
            except Exception as e:
                logger.error(f"❌ Error loading personality: {str(e)}")
        
        return self._default_instruction()
    
    def _default_instruction(self) -> str:
        """Get default system instruction."""
        return """
⚠️ CRITICAL INSTRUCTION - READ THIS FIRST ⚠️
═══════════════════════════════════════════════════════════════════

BEFORE doing ANYTHING else, check if the user message contains ANY of these keywords:
- "humano", "asesor", "persona", "compañero", "alguien", "otra persona"
- "alguien real", "hablar con", "pásame con", "comunícame con"
- Phrases implying frustration: "no entiendes", "no sirves", "quiero hablar"

IF ANY keyword is detected:
1. STOP IMMEDIATELY - Do NOT attempt to answer
2. CALL trigger_human_handoff(reason="user_request") RIGHT NOW
3. Do NOT verify, do NOT ask questions, do NOT provide alternatives
4. JUST TRANSFER - This is NON-NEGOTIABLE

═══════════════════════════════════════════════════════════════════

Eres 'Sebas', vendedor paisa experto de Tienda Las Motos.

IDENTIDAD:
- Nombre: Sebas
- Rol: Asesor comercial especializado en motocicletas
- Personalidad: Amable, profesional, conocedor del producto
- Objetivo: Ayudar al cliente a encontrar su moto ideal y cerrar la venta

CONOCIMIENTO DEL CATÁLOGO:
Tienes acceso a nuestro catálogo completo de motocicletas:
- NKD 125: Moto urbana, ideal para ciudad, económica
- Sport 100: Deportiva de entrada, perfecta para jóvenes
- Victory Black: Elegante y potente, para ejecutivos
- MRX 150: Todo terreno, aventurera

REGLAS DE CONVERSACIÓN:
1. Tono amable pero directo - no chatear por chatear
2. Siempre orientar hacia la venta o simulación de crédito
3. Si preguntan por precio, ofrecer simulación inmediata
4. Mencionar beneficios clave: financiación flexible, garantía, servicio técnico
5. Cerrar cada mensaje con llamado a la acción claro

FLUJO DE VENTA:
1. Identificar necesidad del cliente
2. Recomendar moto específica del catálogo
3. Ofrecer simulación de crédito
4. Agendar visita a sede o cerrar venta

ESCALACIÓN A HUMANO:
- Si la consulta es muy compleja, técnica, o fuera de tu conocimiento, llama a trigger_human_handoff
- Cuando llames a esta función, el usuario recibirá automáticamente el mensaje de transferencia
- NO inventes respuestas si no estás seguro - es mejor escalar a un humano

NO HACER:
- No inventar información técnica que no conoces
- No prometer descuentos sin autorización
- No desviar la conversación a temas no relacionados con motos
- No ser insistente si el cliente no está interesado
        """.strip()
    
    def pensar_respuesta(self, texto: str, context: str = "") -> str:
        """
        Generate an intelligent response using Gemini AI with Retry Logic.
        """
        # Decorator-style logic implementation inside method for simplicity unless specific util needed
        return self._generate_with_retry(texto, context)

    def _create_tools(self) -> Optional[Tool]:
        """
        Create tools for function calling (human handoff).
        
        Returns:
            Tool object with function declarations, or None if not available
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
            
            return Tool(function_declarations=[handoff_function])
        except Exception as e:
            logger.error(f"❌ Error creating tools: {str(e)}")
            return None
    
    def _generate_with_retry(self, texto: str, context: str) -> str:
        """
        Internal generation with exponential backoff.
        
        Handles both regular text responses and function calls (human handoff).
        """
        if not self._model: return self._fallback_response(texto)
        
        max_retries = 3
        base_delay = 2 # Increased base delay for 429 safety
        
        import time
        from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable

        for attempt in range(max_retries):
            try:
                chat = self._model.start_chat()
                
                full_prompt = f"{self._system_instruction}\n\n"
                if context:
                        full_prompt += f"RESUMEN CONVERSACIÓN ANTERIOR:\n{context}\n\n"
                
                full_prompt += f"Usuario: {texto}\n\nSebas:"
                
                response = chat.send_message(full_prompt)
                
                # Check if model wants to call a function (human handoff)
                if response.candidates[0].content.parts[0].function_call:
                    function_call = response.candidates[0].content.parts[0].function_call
                    
                    if function_call.name == "trigger_human_handoff":
                        reason = function_call.args.get("reason", "unknown")
                        logger.warning(f"🚨 AI triggered human handoff | Reason: {reason}")
                        
                        # Return special marker that router will detect
                        # Format: HANDOFF_TRIGGERED:reason
                        return f"HANDOFF_TRIGGERED:{reason}"
                
                # Normal text response
                ai_response = response.text.strip()
                
                if not ai_response:
                        logger.warning("⚠️ Empty AI response")
                        return self._fallback_response(texto)
                        
                logger.info(f"✅ AI response generated ({len(ai_response)} chars)")
                return ai_response
                
            except (ResourceExhausted, ServiceUnavailable) as e:
                wait_time = base_delay * (2 ** attempt)
                logger.warning(f"⏳ API Limit (429/503). Retrying in {wait_time}s... (Attempt {attempt+1}/{max_retries})")
                time.sleep(wait_time)
                
            except Exception as e:
                logger.error(f"❌ Error in AI attempt {attempt+1}: {e}")
                break
        
        logger.error("❌ Failed to generate AI response after retries")
        return self._fallback_response(texto)

    def detect_sentiment(self, text: str) -> str:
        """
        Analyze sentiment of the user message.
        Returns: 'POSITIVE', 'NEUTRAL', 'NEGATIVE', 'ANGRY'
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

    def generate_summary(self, conversation_text: str) -> str:
        """
        Summarize the conversation for memory context.
        """
        if not self._model: return ""
        try:
            chat = self._model.start_chat()
            response = chat.send_message(
                f"Summarize this conversation in 1-2 sentences capturing key user intent and data:\n{conversation_text}"
            )
            return response.text.strip()
        except:
            return ""

    def _fallback_response(self, texto: str) -> str:
        """
        Generate a fallback response when AI is not available.
        # ... (rest of fallback)

        
        Args:
            texto: User message text
        
        Returns:
            Fallback response string
        """
        texto_lower = texto.lower()
        
        # Simple keyword-based responses
        if any(word in texto_lower for word in ["hola", "buenos", "buenas"]):
            return """
¡Hola! Soy Sebas de Tienda Las Motos 🏍️

Estoy aquí para ayudarte a encontrar tu moto ideal. Tenemos:
- NKD 125: Económica y perfecta para ciudad
- Sport 100: Deportiva para jóvenes
- Victory Black: Elegante para ejecutivos
- MRX 150: Aventurera todo terreno

¿Qué tipo de moto estás buscando? También puedo ayudarte con simulaciones de crédito.
            """.strip()
        
        elif any(word in texto_lower for word in ["precio", "costo", "valor"]):
            return """
¡Excelente pregunta! 💰

Nuestros precios varían según el modelo. Para darte información exacta y ofrecerte las mejores opciones de financiación, ¿me dices qué moto te interesa?

- NKD 125
- Sport 100
- Victory Black
- MRX 150

También puedo hacer una simulación de crédito personalizada con tu inicial y plazo preferido.
            """.strip()
        
        elif any(word in texto_lower for word in ["servicio", "taller", "repuesto"]):
            return """
🔧 **Servicio Técnico y Repuestos**

Contamos con taller especializado y repuestos originales para todas nuestras motos.

¿Necesitas:
- Mantenimiento preventivo?
- Reparación?
- Repuestos específicos?

Déjame saber en qué puedo ayudarte o si prefieres información sobre nuestras motos.
            """.strip()
        
        else:
            return """
Gracias por tu mensaje. Soy Sebas, tu asesor en Tienda Las Motos 🏍️

Puedo ayudarte con:
✅ Información sobre nuestras motos (NKD, Sport, Victory, MRX)
✅ Simulaciones de crédito
✅ Servicio técnico y repuestos
✅ Agendar visita a nuestras sedes

¿En qué te puedo ayudar hoy?
            """.strip()
