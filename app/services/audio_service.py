"""
Audio Service
Handles audio processing and AI voice understanding.
"""

import logging
import os
import tempfile
import asyncio
from typing import Optional

# FFmpeg Wrapper
import ffmpeg

logger = logging.getLogger(__name__)

# Vertex AI (Gemini)
try:
    import vertexai
    from vertexai.generative_models import GenerativeModel, Part
    VERTEX_AI_AVAILABLE = True
except ImportError:
    VERTEX_AI_AVAILABLE = False
    logger.warning("⚠️ Vertex AI not available for Audio Service.")

class AudioService:
    """
    Service for processing audio messages via Gemini.
    """

    def __init__(self, config_loader=None):
        self._config_loader = config_loader
        self._model = None
        
        if VERTEX_AI_AVAILABLE:
            try:
                # Gemini 2.5 Flash is effective for audio
                self._model = GenerativeModel("gemini-2.5-flash") 
                logger.info("🎤 AudioService initialized with Gemini 2.5 Flash")
            except Exception as e:
                logger.error(f"❌ AudioService init error: {e}")

    async def transcribe_audio(self, audio_bytes: bytes, mime_type: str) -> str:
        """
        Process incoming audio: Transcode -> AI Transcription.
        """
        if not self._model:
            return "Lo siento, no puedo escuchar audios en este momento. 🙉"

        # 1. Transcode OGG to WAV (16kHz Mono) for Gemini
        mp3_path = self._transcode_to_wav(audio_bytes)
        if not mp3_path:
            return "Tuve un problema con el formato de audio. ¿Me lo escribes? ✍️"

        try:
            # 2. Upload/Prepare for Gemini
            with open(mp3_path, "rb") as f:
                audio_data = f.read()
            
            audio_part = Part.from_data(data=audio_data, mime_type="audio/wav")
            
            # 3. Request Transcription Only
            contents = [
                "Por favor, transcribe exactamente lo que dice este audio en español. No respondas a las preguntas ni asumas un rol, solo devuelve el texto hablado paso a paso de lo que escuches sin añadir comentarios tuyos.",
                audio_part
            ]
            
            response = self._model.generate_content(contents)
            
            text_out = response.text.strip()
            if not text_out:
                logger.warning("⚠️  Gemini returned empty text for audio transcription.")
                return ""
                
            return text_out
            
        except Exception as e:
            logger.error(f"❌ Error transcribing audio with AI: {e}")
            return ""
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

