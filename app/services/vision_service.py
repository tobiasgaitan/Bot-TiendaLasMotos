"""
Vision Service
Handles image analysis using Gemini Vision (Flash).
"""

import logging
from typing import Dict, Any, Optional
import json

from google.cloud import firestore

logger = logging.getLogger(__name__)

# Vertex AI (Gemini)
try:
    import vertexai
    from vertexai.generative_models import GenerativeModel, Part, Image
    VERTEX_AI_AVAILABLE = True
except ImportError:
    VERTEX_AI_AVAILABLE = False
    logger.warning("⚠️ Vertex AI not available for Vision Service.")

class VisionService:
    """
    Service for analyzing images (OCR, Object Detection) using Gemini.
    """

    def __init__(self, db: firestore.Client):
        self._db = db
        self._model = None
        
        if VERTEX_AI_AVAILABLE:
            try:
                # Using Gemini 2.5 Flash (aligned with ai_brain)
                # Upgraded from 1.5-flash-001 which was deprecated
                self._model = GenerativeModel("gemini-2.5-flash")
                logger.info("👁️ VisionService initialized with Gemini 2.5 Flash")
            except Exception as e:
                logger.error(f"❌ VisionService init error: {e}")

    async def analyze_image(self, image_bytes: bytes, mime_type: str, phone: str) -> str:
        """
        General analysis of an image sent by user.
        Routes to specific logic (OCR vs Bike ID) based on content.
        """
        if not self._model:
            return "Lo siento, no puedo ver la imagen en este momento. 🙈"

        try:
            image_part = Part.from_data(data=image_bytes, mime_type=mime_type)
            
            # 1. Classification Prompt
            # Ask Gemini what it sees first to route logic
            prompt = """
            Analyze this image.
            If it is a Colombian ID card (Cédula de Ciudadanía), output JSON: {"type": "id_card"}
            If it is a motorcycle, output JSON: {"type": "moto", "description": "brief description of the bike"}
            Otherwise, output JSON: {"type": "other", "description": "what is it"}
            Output ONLY raw JSON.
            """
            
            response = self._model.generate_content([image_part, prompt])
            result_json = self._parse_json(response.text)
            
            if result_json.get("type") == "id_card":
                return await self._process_id_card(image_part, phone)
            
            elif result_json.get("type") == "moto":
                return await self._process_moto(image_part, result_json.get("description", ""))
            
            else:
                return "Veo la imagen, pero no estoy seguro de qué hacer con ella. ¿Es una moto o tu cédula? 🤔"

        except Exception as e:
            logger.error(f"❌ Error analyzing image: {e}")
            return "Tuve un problema procesando la imagen. Intenta enviarla de nuevo."

    async def _process_id_card(self, image_part: Part, phone: str) -> str:
        """Extract data from ID card and save lead."""
        prompt = """
        Extract the following information from this Colombian ID Card (Cédula):
        - Full Name (Nombre Completo)
        - ID Number (Número de Cédula)
        
        Output JSON: {"name": "...", "cedula": "..."}
        """
        try:
            response = self._model.generate_content([image_part, prompt])
            data = self._parse_json(response.text)
            
            name = data.get("name")
            cedula = data.get("cedula")
            
            if name and cedula:
                # Save to Firestore 'prospectos' or 'leads'
                doc_ref = self._db.collection("leads").document(phone)
                val_data = {
                    "full_name": name,
                    "document_id": cedula,
                    "phone": phone,
                    "source": "whatsapp_ocr",
                    "updated_at": firestore.SERVER_TIMESTAMP
                }
                doc_ref.set(val_data, merge=True)
                
                return f"✅ ¡Perfecto! He leído tus datos:\n\n👤 {name}\n🆔 {cedula}\n\nLos he guardado para tu estudio de crédito. ¿Continuamos?"
            else:
                return "Pude ver que es una cédula, pero no logré leer bien los datos. ¿Podrías intentar una foto más clara? 📸"
                
        except Exception as e:
            logger.error(f"OCR Error: {e}")
            return "Error leyendo la cédula."

    async def _process_moto(self, image_part: Part, brief_desc: str) -> str:
        """Identify motorcycle and recommend."""
        # We could use inventory service here to vector search based on description
        # For now, let's just act as the expert
        prompt = """
        Identify the motorcycle model in this image.
        If it looks like one of the Auteco/Victory/Bajaj bikes (NKD, MRX, Victory, Boxer, Pulsar), identify it.
        Reply in character as 'Sebas' (Asesor Paisa):
        "¡Uff qué nave! Esa parece una [Modelo]..."
        Then briefly mention if we have it or something similar in stock.
        """
        response = self._model.generate_content([image_part, prompt])
        return response.text.strip()

    def _parse_json(self, text: str) -> Dict[str, Any]:
        """Helper to parse JSON from LLM response."""
        try:
            # Strip code blocks if present
            clean = text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean)
        except:
            return {}
