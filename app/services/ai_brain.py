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
                # Initialize model SANS tools (No internal handoff)
                self._model = GenerativeModel(
                    "gemini-2.5-flash",
                    tools=[] # DISABLE AI HANDOFF
                )
                logger.info("🧠 CerebroIA initialized with Gemini 2.5 Flash (No Tools)")
            except Exception as e:
                logger.error(f"❌ Error initializing Vertex AI: {str(e)}")
                self._model = None
        else:
            logger.warning("⚠️  CerebroIA running in fallback mode (no AI)")
    
    def _get_system_instruction(self) -> str:
        """
        Get system instruction.
        
        CRITICAL UPDATE: Forcing "Juan Pablo" persona via code constant to ensure 
        consistency and avoid stale Firestore configurations.
        """
        # We process the code constant directly to guarantee the update
        from app.core.prompts import JUAN_PABLO_SYSTEM_INSTRUCTION
        return JUAN_PABLO_SYSTEM_INSTRUCTION

    
    def _default_instruction(self) -> str:
        """Get default system instruction."""
        from app.core.prompts import JUAN_PABLO_SYSTEM_INSTRUCTION
        return JUAN_PABLO_SYSTEM_INSTRUCTION
    
    def pensar_respuesta(self, texto: str, context: str = "", prospect_data: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate an intelligent response using Gemini AI with Retry Logic.
        
        Includes fast-path detection for human handoff requests to ensure
        immediate response without relying on AI function calling.
        
        Args:
            texto: User message text
            context: Previous conversation summary
            prospect_data: Optional prospect data from CRM for personalization
        
        Returns:
            AI-generated response text or HANDOFF_TRIGGERED marker
        """
        # FAST PATH: Detect human handoff keywords BEFORE AI processing
        # DISABLED: Router now handles strict handoff logic (Check A)
        # This prevents AI from blocking sales topics.
        # texto_lower = texto.lower()
        # handoff_keywords = [
        #     "asesor", "humano", "persona", "alguien real", 
        #     "hablar con", "pásame con", "comunícame con",
        #     "alguien", "otra persona", "compañero",
        #     "no entiendes", "no sirves", "quiero hablar"
        # ]
        
        # if any(keyword in texto_lower for keyword in handoff_keywords):
        #     logger.warning(f"🚨 Fast-path handoff detected | Keywords found in: {texto[:50]}...")
        #     return "HANDOFF_TRIGGERED:user_request"
        
        # Normal AI processing
        return self._generate_with_retry(texto, context, prospect_data)

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
    
    def _generate_with_retry(self, texto: str, context: str, prospect_data: Optional[Dict[str, Any]] = None) -> str:
        """
        Internal generation with exponential backoff.
        
        Handles both regular text responses and function calls (human handoff).
        Injects prospect data for personalized responses when available.
        
        Args:
            texto: User message text
            context: Previous conversation summary
            prospect_data: Optional prospect data from CRM
        
        Returns:
            AI-generated response or HANDOFF_TRIGGERED marker
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

    def generate_summary(self, conversation_text: str) -> Dict[str, Any]:
        """
        Summarize the conversation and extract structured data.
        
        Args:
            conversation_text: Full conversation text to summarize
        
        Returns:
            Dictionary with:
            - summary: Concise conversation summary
            - extracted: Dict with name, moto_interest if detected
        
        Example:
            >>> result = cerebro.generate_summary("User: Hola soy Carlos...")
            >>> print(result)
            {"summary": "Cliente preguntó por...", "extracted": {"name": "Carlos"}}
        """
        if not self._model:
            return {"summary": "", "extracted": {}}
        
        try:
            chat = self._model.start_chat()
            
            # Enhanced prompt for structured extraction
            prompt = f"""
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

Si no detectas un campo, omítelo del objeto extracted.
"""
            
            response = chat.send_message(prompt)
            response_text = response.text.strip()
            
            # Try to parse JSON response
            import json
            import re
            
            # Extract JSON from markdown code blocks if present
            json_match = re.search(r'```(?:json)?\s*({.*?})\s*```', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(1)
            
            result = json.loads(response_text)
            
            # Validate structure
            if "summary" not in result:
                result["summary"] = ""
            if "extracted" not in result:
                result["extracted"] = {}
            
            logger.info(f"📝 Generated summary with {len(result.get('extracted', {}))} extracted fields")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error generating summary: {str(e)}")
            # Fallback: return simple summary without extraction
            return {
                "summary": conversation_text[:200] + "..." if len(conversation_text) > 200 else conversation_text,
                "extracted": {}
            }

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
