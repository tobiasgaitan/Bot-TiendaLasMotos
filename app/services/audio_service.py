"""
Audio Service
Handles audio processing and AI voice understanding.
"""

import logging
import os
import tempfile
import asyncio
import random
from typing import Optional

# FFmpeg Wrapper
import ffmpeg
import time

from app.services.llm_client_service import get_shared_llm_client, get_active_model_id

GEMINI_CALL_TIMEOUT_S = 18.0

logger = logging.getLogger(__name__)

# google-genai (Gemini)
try:
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError
    from google.auth.exceptions import DefaultCredentialsError
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    class APIError(Exception): pass
    class DefaultCredentialsError(Exception): pass
    logger.warning("⚠️ google-genai or google-auth not available for Audio Service.")

class AudioService:
    """
    Service for processing audio messages via Gemini.
    """

    def __init__(self, config_loader=None):
        self._config_loader = config_loader
        self._model = None
        
        if GENAI_AVAILABLE:
            try:
                # Check for Gemini API key first to use Developer API
                api_key = os.getenv("GEMINI_API_KEY")
                use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "false").lower() in ("true", "1")
                
                # Check for Google Cloud Application Default Credentials (ADC)
                import google.auth
                from google.auth.exceptions import DefaultCredentialsError
                
                # credentials se resuelve internamente por el SDK de genai (R2);
                # conservamos google.auth.default() únicamente para obtener project.
                _credentials, project = None, None
                try:
                    _credentials, project = google.auth.default()
                except DefaultCredentialsError:
                    pass
                
                project = os.getenv("GOOGLE_CLOUD_PROJECT", project or "tiendali_las_motos")
                
                if api_key and not use_vertex:
                    self.client = get_shared_llm_client(
                        vertexai=False,
                        api_key=api_key,
                    )
                    self._model_id = get_active_model_id("multimodal")
                    logger.info(f"🎤 AudioService initialized with {self._model_id} via Gemini Developer API (API Key)")
                else:
                    # [BOT-BUILD-GENAI-SINGLETON-050-R] No pasamos credentials=;
                    # el SDK resuelve ADC internamente y esto estabiliza la clave de cache
                    # (evita un cliente nuevo por cada AudioService/=request de audio).
                    self.client = get_shared_llm_client(
                        vertexai=True,
                        project=project,
                        location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
                    )
                    self._model_id = get_active_model_id("multimodal")
                    logger.info(f"🎤 AudioService initialized with {self._model_id} via google-genai (Vertex AI + ADC)")
            except (DefaultCredentialsError, APIError) as e:
                logger.exception("❌ Error de credenciales o API gRPC al inicializar el cliente de AudioService")
                if hasattr(e, 'response') and hasattr(e.response, 'text'):
                    logger.error(f"Response Body: {e.response.text}")
                raise e
            except Exception as e:
                logger.exception("❌ Error inesperado al inicializar AudioService")
                if hasattr(e, 'response') and hasattr(e.response, 'text'):
                    logger.error(f"Response Body: {e.response.text}")
                raise e

    async def _call_gemini_with_retry_async(self, func, *args, **kwargs):
        """
        Resiliencia de Red (Exponential Backoff) para llamadas asíncronas.
        [BOT-BUILD-MOTO-CANON-018 / C-17] FIX-2A-equivalent: per-call timeout + retry
        on asyncio.TimeoutError / APIError 429/503.
        """
        max_retries = 2
        base_delay = 2.0
        for attempt in range(max_retries + 1):
            try:
                return await asyncio.wait_for(
                    asyncio.to_thread(func, *args, **kwargs),
                    timeout=GEMINI_CALL_TIMEOUT_S,
                )
            except asyncio.TimeoutError as e:
                if attempt < max_retries:
                    wait_time = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(
                        f"⏳ [AUDIO EXP BACKOFF] Attempt {attempt+1} timed out. "
                        f"Retrying in {wait_time:.2f}s..."
                    )
                    await asyncio.sleep(wait_time)
                    continue
                logger.exception(f"🚨 [AUDIO GEMINI ERROR] Final timeout failure: {e}")
                raise e
            except APIError as e:
                err_str = str(e).lower()
                is_quota_error = "429" in err_str or "resource_exhausted" in err_str
                is_service_error = "503" in err_str or "service_unavailable" in err_str
                if (is_quota_error or is_service_error) and attempt < max_retries:
                    wait_time = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(
                        f"⏳ [AUDIO EXP BACKOFF] Attempt {attempt+1} failed ({type(e).__name__}). "
                        f"Retrying in {wait_time:.2f}s..."
                    )
                    await asyncio.sleep(wait_time)
                    continue
                logger.exception(f"🚨 [AUDIO GEMINI ERROR] Final API failure: {e}")
                raise e
            except Exception as e:
                logger.exception(f"🚨 [AUDIO GEMINI ERROR] Non-retriable failure: {e}")
                raise e

    async def transcribe_audio(self, audio_bytes: bytes, mime_type: str) -> str:
        """
        Process incoming audio: Transcode -> AI Transcription.
        """
        if not hasattr(self, 'client'):
            return "Lo siento, no puedo escuchar audios en este momento. 🙉"

        # 1. Transcode OGG to WAV (16kHz Mono) for Gemini
        mp3_path = self._transcode_to_wav(audio_bytes)
        if not mp3_path:
            return "Tuve un problema con el formato de audio. ¿Me lo escribes? ✍️"

        try:
            # 2. Upload/Prepare for Gemini
            with open(mp3_path, "rb") as f:
                audio_data = f.read()
            
            audio_part = types.Part.from_bytes(data=audio_data, mime_type="audio/wav")
            
            # 3. Request Transcription Only
            contents = [
                "Por favor, transcribe exactamente lo que dice este audio en español. No respondas a las preguntas ni asumas un rol, solo devuelve el texto hablado paso a paso de lo que escuches sin añadir comentarios tuyos.",
                audio_part
            ]
            
            response = await self._call_gemini_with_retry_async(
                self.client.models.generate_content,
                model=self._model_id,
                contents=contents
            )
            
            text_out = response.text.strip()
            if not text_out:
                logger.warning("⚠️  Gemini returned empty text for audio transcription.")
                return ""
                
            return text_out
            
        except (DefaultCredentialsError, APIError) as e:
            logger.exception("❌ Error de credenciales o API gRPC en la transcripción de audio")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                logger.error(f"Response Body: {e.response.text}")
            raise e
        except Exception as e:
            logger.exception("❌ Error inesperado al transcribir el audio con la IA")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                logger.error(f"Response Body: {e.response.text}")
            raise e
        finally:
            # Cleanup
            if mp3_path and os.path.exists(mp3_path):
                try:
                    os.remove(mp3_path)
                except:
                    pass

    def _transcode_to_wav(self, input_bytes: bytes) -> Optional[str]:
        """
        Transcode input bytes (likely OGG) to WAV (16kHz Mono) for Gemini.
        Using ffmpeg-python.
        """
        try:
            # Create temp file for input
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_in:
                temp_in.write(input_bytes)
                temp_in_path = temp_in.name

            # Create temp file for output
            temp_out_path = temp_in_path.replace(".ogg", ".wav")

            # Run ffmpeg with 16kHz mono (ar=16000, ac=1)
            stream = ffmpeg.input(temp_in_path)
            stream = ffmpeg.output(stream, temp_out_path, ar=16000, ac=1)
            ffmpeg.run(stream, overwrite_output=True, quiet=True)
            
            # Cleanup input
            os.remove(temp_in_path)
            
            return temp_out_path
            
        except Exception as e:
            logger.error(f"❌ Transcoding error: {e}")
            # Try to cleanup
            if 'temp_in_path' in locals() and os.path.exists(temp_in_path):
                os.remove(temp_in_path)
            return None

    def _get_system_prompt(self) -> str:
        """Reuse Juan Pablo personality."""
        if self._config_loader:
             personality = self._config_loader.get_juan_pablo_personality()
             return personality.get("system_instruction", "")
        return "You are Juan Pablo, a professional and agile motorcycle expert in Colombia. Respond in Spanish, be helpful and formal but dynamic."

    @classmethod
    def test_integration(cls):
        """
        Test de integración desacoplado para ejecutar desde CLI.
        Instancia de forma nativa AudioService y realiza una petición a Gemini
        para forzar la resolución de credenciales y validar fallos de gRPC o de credenciales.
        """
        import os
        from google.auth.exceptions import DefaultCredentialsError
        from google.genai.errors import APIError
        
        logger.info("🎤 Iniciando prueba de integración desacoplada nativa para AudioService...")
        
        # Validar disponibilidad de la librería
        if not GENAI_AVAILABLE:
            raise ImportError("La librería 'google-genai' no está disponible.")
            
        try:
            service = cls()
            if not hasattr(service, 'client') or service.client is None:
                raise ValueError("El cliente google-genai no se pudo inicializar en AudioService.")
            
            logger.info("📡 Ejecutando llamada real de integración (listar modelos) para verificar credenciales...")
            # Una llamada simple para forzar resolución de credenciales contra Google Cloud
            # Si las credenciales no existen, lanzará DefaultCredentialsError o APIError de gRPC
            models = list(service.client.models.list())
            logger.info(f"✅ Integración exitosa. Modelos disponibles encontrados: {len(models)}")
            return True
            
        except DefaultCredentialsError as e:
            logger.exception("❌ [FORENSIC] Error de credenciales predeterminadas de Google (DefaultCredentialsError)")
            raise e
        except APIError as e:
            logger.exception("❌ [FORENSIC] Error de API / gRPC de Google (APIError)")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                logger.error(f"Cuerpo de respuesta del API: {e.response.text}")
            raise e
        except Exception as e:
            logger.exception("❌ [FORENSIC] Error inesperado en la prueba de integración de AudioService")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                logger.error(f"Cuerpo de respuesta: {e.response.text}")
            raise e

