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
    from vertexai.generative_models import GenerativeModel
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
        
        # Initialize Vertex AI if available
        if VERTEX_AI_AVAILABLE:
            try:
                vertexai.init(project="tiendalasmotos", location="us-central1")
                self._model = GenerativeModel("gemini-2.0-flash-exp")
                logger.info("🧠 CerebroIA initialized with Gemini 2.0 Flash")
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

NO HACER:
- No inventar información técnica que no conoces
- No prometer descuentos sin autorización
- No desviar la conversación a temas no relacionados con motos
- No ser insistente si el cliente no está interesado
        """.strip()
    
    def pensar_respuesta(self, texto: str) -> str:
        """
        Generate an intelligent response using Gemini AI.
        
        Args:
            texto: User message text
        
        Returns:
            AI-generated response string
        """
        try:
            # If Vertex AI is available, use it
            if self._model:
                logger.info(f"🤔 Generating AI response for: {texto[:50]}...")
                
                # Create chat with system instruction
                chat = self._model.start_chat()
                
                # Generate response
                response = chat.send_message(
                    f"{self._system_instruction}\n\nUsuario: {texto}\n\nSebas:"
                )
                
                ai_response = response.text.strip()
                logger.info(f"✅ AI response generated ({len(ai_response)} chars)")
                return ai_response
            
            # Fallback response if AI not available
            else:
                return self._fallback_response(texto)
                
        except Exception as e:
            logger.error(f"❌ Error generating AI response: {str(e)}")
            return self._fallback_response(texto)
    
    def _fallback_response(self, texto: str) -> str:
        """
        Generate a fallback response when AI is not available.
        
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
