"""
Vision Service
Handles image analysis using Gemini Vision (Flash).
"""

import logging
import os
from typing import Dict, Any, Optional, List
import json
import asyncio
import time

from google.cloud import firestore

logger = logging.getLogger(__name__)

# google-genai (Gemini)
try:
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    logger.warning("⚠️ google-genai not available for Vision Service.")

class VisionService:
    """
    Service for analyzing images (OCR, Object Detection) using Gemini.
    """

    def __init__(self, db: firestore.Client):
        self._db = db
        self._model = None

        self._telemetry_enabled = os.getenv("VISION_TELEMETRY_ONLY", "").lower() in ("1", "true")
        self._last_usage: Dict[str, Dict[str, int]] = {}
        
        if GENAI_AVAILABLE:
            try:
                # Using Gemini 2.5 Flash (upgraded for vision)
                self.client = genai.Client(
                    vertexai=True,
                    project=self._db.project, # Re-using project ID from Firestore client
                    location="us-central1"    # Default location, can be moved to env
                )
                self._model_id = "gemini-2.5-flash"
                logger.info(f"👁️ VisionService initialized with {self._model_id} via google-genai"
                            f"{' [TELEMETRY ENABLED]' if self._telemetry_enabled else ''}")
            except Exception as e:
                logger.exception(f"❌ VisionService init error: {e}")

    @staticmethod
    def _extract_usage(response) -> Dict[str, int]:
        usage = getattr(response, "usage_metadata", None)
        if usage is None:
            return {}
        return {
            "prompt_tokens": getattr(usage, "prompt_token_count", 0) or 0,
            "candidates_tokens": getattr(usage, "candidates_token_count", 0) or 0,
            "total_tokens": getattr(usage, "total_token_count", 0) or 0,
        }

    def _capture_usage(self, phase: str, response) -> None:
        if not self._telemetry_enabled:
            return
        usage_data = self._extract_usage(response)
        if usage_data:
            self._last_usage[phase] = usage_data

    async def _generate_content_nonblocking(self, contents):
        """
        [BOT-PLAN-MULTIMODAL-HARDENING-201] Offload síncrono de Gemini a hilo
        secundario para evitar bloquear el event loop de FastAPI bajo Session Lock.
        """
        return await asyncio.to_thread(
            self.client.models.generate_content,
            model=self._model_id,
            contents=contents
        )

    async def _call_gemini_with_retry_async(self, contents):
        """
        Resiliencia de Red (Exponential Backoff) con offload non-blocking.
        """
        max_retries = 2
        delay = 1.5
        for attempt in range(max_retries + 1):
            try:
                return await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self._model_id,
                    contents=contents
                )
            except APIError as e:
                if attempt < max_retries:
                    logger.warning(f"⚠️ Vision Gemini API failure (Attempt {attempt+1}/{max_retries+1}). Retrying in {delay}s... Error: {e}")
                    await asyncio.sleep(delay)
                    continue
                raise e
            except Exception as e:
                raise e

    async def analyze_image(self, image_bytes: bytes, mime_type: str, phone: str, caption: str = "", catalog_items: Optional[List[Dict[str, Any]]] = None) -> str:
        """
        General analysis of an image sent by user.
        Routes to specific logic (OCR vs Bike ID vs General Sentiment) based on content.
        
        @param image_bytes Binary media payload from Meta.
        @param mime_type MIME type of the uploaded media.
        @param phone Phone number for routing/logs.
        @param caption Optional user caption sent along with media.
        @param catalog_items Optional list of active catalog items.
        @returns A string intended for either direct output or AI Brain injection.
        """
        if not hasattr(self, 'client'):
            return "Lo siento, no puedo ver la imagen en este momento. 🙈"

        t_total_start = time.perf_counter()
        self._last_usage.clear()

        # Anti-Null Masking validation for catalog items
        if catalog_items:
            for item in catalog_items:
                name = item.get("name")
                img_url = item.get("image_url")
                if name is None or name == "" or img_url is None or img_url == "":
                    import traceback
                    tb_str = "".join(traceback.format_stack())
                    logger.warning(
                        f"⚠️ [INTEGRITY VIOLATION] Catalog item missing critical visual keys. "
                        f"ID: '{item.get('id', 'unknown')}', name: {name}, image_url: {img_url}.\n"
                        f"Traceback:\n{tb_str}"
                    )

        try:
            image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
            
            # 1. Classification Prompt
            # Ask Gemini what it sees first to route logic
            # Also consider the user's caption if provided
            caption_context = f"User caption: '{caption}'" if caption else ""
            
            prompt = """
            Analiza esta imagen. Si es un documento colombiano (Cédula de Ciudadanía o Recibo de Gas Natural), evalúa:
            1. Nitidez: ¿El texto es 100% legible? (Rechazar si está movida/borrosa).
            2. Iluminación: ¿Hay reflejos o sombras que tapen datos críticos?
            3. Clasificación: ¿Es CEDULA o RECIBO_GAS?

            REGLAS DE SALIDA:
            - Si falla calidad: QUALITY_CHECK: FAILED | Motivo: [Borrosa/Oscura/Recortada/Reflejos]
            - Si pasa: QUALITY_CHECK: PASSED | DOCUMENTO_DETECTADO: [CEDULA/RECIBO_GAS]

            Si no es un documento:
            - Si es una motocicleta, output JSON: {"type": "moto", "description": "brief description of the bike"}
            - De lo contrario, output JSON: {"type": "other", "description": "what is it"}
            """
            
            t_classify_start = time.perf_counter()
            response = await self._call_gemini_with_retry_async(
                contents=[image_part, prompt]
            )
            t_classify = time.perf_counter() - t_classify_start
            self._capture_usage("classify", response)

            # 2. Extract Contract or JSON
            if not response or not getattr(response, "text", None):
                raise ValueError("GenAI API returned an empty response or nulo payload")
            response_text = response.text.strip()
            if not response_text:
                raise ValueError("GenAI API returned an empty text payload")
            
            if "QUALITY_CHECK:" in response_text:
                self._log_telemetry(t_classify, 0, "kyc_document", image_bytes, mime_type, phone, len(catalog_items) if catalog_items else 0, t_total_start)
                return response_text
            
            result_json = self._parse_json(response_text)
            phase_label: str = "other"
            
            t_phase2_start = time.perf_counter()
            if result_json.get("type") in ["kyc_document", "id_card"]:
                # This path is kept for backward compatibility if the prompt fails to follow the new contract
                # but the prompt above should prioritize the text contract.
                phase_label = "kyc_document"
                result = await self._process_kyc_document(image_part, phone)
            elif result_json.get("type") == "moto":
                phase_label = "moto"
                result = await self._process_moto(image_part, result_json.get("description", ""), catalog_items)
            else:
                phase_label = "sentiment"
                result = await self._process_general_image_sentiment(image_part)
            t_phase2 = time.perf_counter() - t_phase2_start

            self._log_telemetry(t_classify, t_phase2, phase_label, image_bytes, mime_type, phone, len(catalog_items) if catalog_items else 0, t_total_start)
            return result

        except Exception as e:
            t_total = time.perf_counter() - t_total_start
            if self._telemetry_enabled:
                logger.info(
                    "📊 [VISION_TELEMETRY] ERROR | total_latency_s=%.4f "
                    "catalog_items=%d image_bytes=%d mime=%s phone=%s",
                    t_total, len(catalog_items) if catalog_items else 0, len(image_bytes), mime_type, phone
                )
            logger.exception(f"❌ Error analyzing image: {e}")
            raise e

    def _log_telemetry(self, t_classify: float, t_phase2: float, phase: str, image_bytes: bytes, mime_type: str, phone: str, catalog_items_count: int, t_total_start: float) -> None:
        if not self._telemetry_enabled:
            return
        t_total = time.perf_counter() - t_total_start
        classify_u = self._last_usage.get("classify", {})
        phase2_u = self._last_usage.get("phase2", {})
        total_tokens = classify_u.get("total_tokens", 0) + phase2_u.get("total_tokens", 0)
        logger.info(
            "📊 [VISION_TELEMETRY] phase=%s "
            "classify_latency_s=%.4f phase2_latency_s=%.4f total_latency_s=%.4f "
            "classify_tokens_in=%d classify_tokens_out=%d "
            "phase2_tokens_in=%d phase2_tokens_out=%d "
            "total_tokens=%d catalog_items=%d image_bytes=%d mime=%s",
            phase, t_classify, t_phase2, t_total,
            classify_u.get("prompt_tokens", 0), classify_u.get("candidates_tokens", 0),
            phase2_u.get("prompt_tokens", 0), phase2_u.get("candidates_tokens", 0),
            total_tokens, catalog_items_count, len(image_bytes), mime_type,
        )

    async def _process_kyc_document(self, image_part: types.Part, phone: str) -> str:
        """
        Processes KYC documents (Identity cards or Utility bills) directly for the Brilla flow.
        
        Returns the mandatory contract format:
        QUALITY_CHECK: [PASSED/FAILED] | DOCUMENTO_DETECTADO: [TIPO]
        """
        # Second pass only if the first classification wasn't enough or for extra safety
        prompt = """
        Analiza el documento. 
        Si es CEDULA o RECIBO_GAS y es LEGIBLE, responde: QUALITY_CHECK: PASSED | DOCUMENTO_DETECTADO: [TIPO]
        Si no es legible o no es un documento válido, responde: QUALITY_CHECK: FAILED | Motivo: [Razón]
        """
        response = await self._generate_content_nonblocking(
            contents=[image_part, prompt]
        )
        self._capture_usage("phase2", response)
        if not response or not getattr(response, "text", None) or not response.text.strip():
            raise ValueError("GenAI API returned an empty response or nulo payload in _process_kyc_document")
        return response.text.strip()

    async def _process_moto(self, image_part: types.Part, brief_desc: str, catalog_items: Optional[List[Dict[str, Any]]] = None) -> str:
        """
        [BOT-BUILD-MULTIMODAL-INTEGRATION-195] JSON-first structured output with
        pipe-string fallback (dual-stack ACL compatibility).
        
        Identify motorcycle and provide structured output for CerebroIA.
        
        Security & Business Logic (QA Baseline):
        - Why: Returning a structured response ensures that the
          WhatsApp router can intercept the image result and pass it to CerebroIA.
          This enables strict cross-selling rules (Competencia y Equivalencias) based on catalog availability,
          rather than having VisionService hallucinate responses.
        """
        catalog_info = ""
        if catalog_items:
            catalog_info = "\nAvailable motorcycles in our catalog:\n"
            for item in catalog_items:
                name = item.get("name", "")
                img = item.get("image_url", "")
                cid = item.get("id", "")
                if name or cid:
                    catalog_info += f"- Name: '{name}', Image URL: '{img}', ID: '{cid}'\n"

        prompt = f"""
        TASK: Identify the motorcycle in this image as accurately as possible and match it to our catalog.
        
        CRITICAL RULES:
        - Recognize common Colombian models: AKT (NKD, CR4), Bajaj (Pulsar, Boxer), Victory (Bomber, MRX), TVS (Raider), Yamaha, Honda, Suzuki.
        - "NKD 125" is ALWAYS "AKT". NEVER say "Victory NKD".
        - Focus ONLY on identifying the brand, model, and category (e.g., Calle, Sport, Scooter).
        - If catalog items are listed below, you MUST match the motorcycle to the closest corresponding model in our catalog.
        - If there is no exact match, choose the best equivalent.
        
        {catalog_info}
        
        OUTPUT FORMAT:
        You MUST output a valid JSON object (no markdown fences, no extra text):
        {{"type":"moto","model_id":"<id from catalog or empty string>","match_url":"<image_url from catalog or empty string>","moto_detectada":"<detected model description>","confidence":0.0}}
        
        If you absolutely cannot produce JSON, fallback to pipe format:
        MOTO_DETECTADA: [model name] | Match URL: [image_url] | Model ID: [ID]
        """
        response = await self._generate_content_nonblocking(
            contents=[image_part, prompt]
        )
        if not response or not getattr(response, "text", None) or not response.text.strip():
            raise ValueError("GenAI API returned an empty response or nulo payload in _process_moto")

        raw_text = response.text.strip()

        # [BOT-BUILD-MULTIMODAL-INTEGRATION-195] JSON-first decode.
        # If the model returned valid JSON, pass it through directly.
        # Otherwise, return the raw text as pipe-string fallback (ACL dual-stack).
        try:
            candidate = json.loads(raw_text.replace("```json", "").replace("```", "").strip())
            if isinstance(candidate, dict) and candidate.get("type") == "moto":
                logger.info(
                    "🎯 VisionService JSON moto DTO decoded successfully. "
                    "model_id=%s moto_detectada=%s",
                    candidate.get("model_id"), candidate.get("moto_detectada"),
                )
                return json.dumps(candidate)
        except (json.JSONDecodeError, TypeError, ValueError):
            logger.info(
                "📝 VisionService JSON decode failed; falling back to pipe-string. "
                "raw preview: %s", raw_text[:120],
            )

        return raw_text

    async def _process_general_image_sentiment(self, image_part: types.Part) -> str:
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
        response = await self._generate_content_nonblocking(
            contents=[image_part, prompt]
        )
        self._capture_usage("phase2", response)
        if not response or not getattr(response, "text", None) or not response.text.strip():
            raise ValueError("GenAI API returned an empty response or nulo payload in _process_general_image_sentiment")
        return response.text.strip()

    def _parse_json(self, text: str) -> Dict[str, Any]:
        """Helper to parse JSON from LLM response."""
        try:
            # Strip code blocks if present
            clean = text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean)
        except:
            return {}
