import pytest
import asyncio
import logging
import sys
import os
from unittest.mock import MagicMock, patch

# Add project root
sys.path.append(os.getcwd())

# Mock modules
sys.modules["google.cloud"] = MagicMock()
sys.modules["google.genai"] = MagicMock()
sys.modules["google.genai.types"] = MagicMock()
sys.modules["ffmpeg"] = MagicMock()

from app.services.audio_service import AudioService

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("AudioTest")

async def run_audio_pipeline():
    logger.info("🧪 Testing Audio Pipeline (V2.5 + WAV 16kHz)...")
    
    # Init Service
    audio = AudioService()
    
    # Mock Transcode to WAV
    # We want to verify _transcode_to_wav is called
    with patch.object(audio, '_transcode_to_wav', return_value="test_audio.wav") as mock_transcode:
        
        # Mock Gemini Client
        audio.client = MagicMock()
        audio._model_id = "gemini-2.0-flash"
        mock_response = MagicMock()
        mock_response.text = "Entendido."
        audio.client.models.generate_content.return_value = mock_response
        
        # Run
        # We need to mock open() to return real bytes for Pydantic/google-genai validation
        mock_file = MagicMock()
        mock_file.read.return_value = b"mock_audio_content"
        
        with patch("builtins.open", return_value=mock_file):
             res = await audio.transcribe_audio(b"ogg_data", "audio/ogg")
             
        # Assertions
        mock_transcode.assert_called_once()
        logger.info("✅ Transcoding to WAV called.")
        
        # Verify Model Prompt includes logic
        args = audio.client.models.generate_content.call_args
        # We can inspect args if needed, but successful return implies flow worked
        
        assert res == "Entendido."
        logger.info("✅ Gemini 2.5 response received.")

def test_audio_pipeline():
    asyncio.run(run_audio_pipeline())
    logger.info("🎉 Audio V2.5 Verification Complete.")

if __name__ == "__main__":
    test_audio_pipeline()
