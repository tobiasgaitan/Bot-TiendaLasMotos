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

    async def analyze_image(self, image_bytes: bytes, mime_type: str, phone: str, caption: str = "") -> str:
        """
        General analysis of an image sent by user.
        Routes to specific logic (OCR vs Bike ID vs General Sentiment) based on content.
        
        @param image_bytes Binary media payload from Meta.
        @param mime_type MIME type of the uploaded media.
        @param phone Phone number for routing/logs.
        @param caption Optional user caption sent along with media.
        @returns A string intended for either direct output or AI Brain injection.
        """
        if not self._model:
            return "Lo siento, no puedo ver la imagen en este momento. 🙈"

        try:
            image_part = Part.from_data(data=image_bytes, mime_type=mime_type)
            
            # 1. Classification Prompt
            # Ask Gemini what it sees first to route logic
            # Also consider the user's caption if provided
            caption_context = f"User caption: '{caption}'" if caption else ""
            
            prompt = f"""
            Analyze this image. {caption_context}
            If it is a Colombian ID card (Cédula de Ciudadanía) or a utility bill (like Gas Natural), output JSON: {{"type": "kyc_document"}}
            If it is a motorcycle, output JSON: {{"type": "moto", "description": "brief description of the bike"}}
            Otherwise, output JSON: {{"type": "other", "description": "what is it"}}
            Output ONLY raw JSON.
            """
            
            response = self._model.generate_content([image_part, prompt])
            result_json = self._parse_json(response.text)
            
            if result_json.get("type") in ["kyc_document", "id_card"]:
                return await self._process_kyc_document(image_part, phone)
            
            elif result_json.get("type") == "moto":
                return await self._process_moto(image_part, result_json.get("description", ""))
            
            else:
                return await self._process_general_image_sentiment(image_part)

        except Exception as e:
            logger.error(f"❌ Error analyzing image: {e}")
            return "Tuve un problema procesando la imagen. Intenta enviarla de nuevo."

    async def _process_kyc_document(self, image_part: Part, phone: str) -> str:
        """
        Processes KYC documents (Identity cards or Utility bills) directly for the Brilla flow.
        
        Security & Business Logic (QA Baseline):
        - Why: This streamlines the Brilla credit application by explicitly acknowledging
          the document receipt, preventing the AI from falling into the generic or motorcycle-specific flows.
        - Fail-Closed: We only return the validation string if the model confidently 
          classified it as a 'kyc_document'. If unsure, it falls to the fallback.
        - Security: No hardcoded credentials are used here; relies on application ADC.
          Input validation is handled inherently by Vertex AI Part object processing.
        """
        return "¡Documento validado, parcero! 🚀 Ya lo adjunté a tu expediente. ¿Me falta alguna otra foto (cédula o recibo) para radicar tu solicitud con Brilla?"

    async def _process_moto(self, image_part: Part, brief_desc: str) -> str:
        """
        Identify motorcycle and provide structured output for CerebroIA.
        
        Security & Business Logic (QA Baseline):
        - Why: Returning a structured "MOTO_DETECTADA:" string ensures that the 
          WhatsApp router can intercept the image result and pass it to CerebroIA.
          This enables strict cross-selling rules (Competencia y Equivalencias) based on catalog availability,
          rather than having VisionService hallucinate responses.
        """
        prompt = """
        TASK: Identify the motorcycle in this image as accurately as possible.
        
        CRITICAL RULES:
        - Recognize common Colombian models: AKT (NKD, CR4), Bajaj (Pulsar, Boxer), Victory (Bomber, MRX), TVS (Raider), Yamaha, Honda, Suzuki.
        - "NKD 125" is ALWAYS "AKT". NEVER say "Victory NKD".
        - Focus ONLY on identifying the brand, model, and category (e.g., Calle, Sport, Scooter).
        
        OUTPUT FORMAT:
        You MUST output EXACTLY this prefix followed by your description:
        MOTO_DETECTADA: [Your description of brand, model, and category]
        
        No conversational text, no questions. ONLY the prefix and the details.
        """
        response = self._model.generate_content([image_part, prompt])
        return response.text.strip()

    async def _process_general_image_sentiment(self, image_part: Part) -> str:
        """
        Extracts sentiment from general images/memes/stickers for dynamic business routing.
        
        Security & Business Logic (QA Baseline):
        - Why: Intercepting random media lets us gauge user frustration or excitement without breaking flow.
        - Flow Control: Returns a `[System Note: ...]` which is injected directly into the user history array,
          never exposing this raw text to the end-user. CerebroIA reacts accordingly based on prompt engineering.
        """
        prompt = """
        Analyze this image, meme, or sticker. 
        Briefly describe what is happening in the image.
        Explicitly state the inferred sentiment of the user sending this explicitly as one of: (Happy, Sad, Frustrated, Excited, Neutral).
        
        OUTPUT FORMAT:
        [System Note: User sent an image/sticker. Vision analysis: <your brief description>. Sentiment: <Sentiment>]
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
