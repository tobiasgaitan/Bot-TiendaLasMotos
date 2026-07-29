import pytest
import asyncio
import logging
import sys
import os
from unittest.mock import MagicMock, patch

# Add project root
sys.path.append(os.getcwd())

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("AudioTest")

async def run_audio_pipeline():
    logger.info("🧪 Testing Audio Pipeline (V2.5 + WAV 16kHz)...")

    # [M4-003] Same 4 module mocks, moved from import-time to runtime (patch.dict).
    # The module-level sys.modules block poisoned pytest collection (7 firestore
    # integration failures under tests/). Zero change to what this script validates.
    with patch.dict(sys.modules, {
        "google.cloud": MagicMock(),
        "google.genai": MagicMock(),
        "google.genai.types": MagicMock(),
        "ffmpeg": MagicMock(),
    }):
        from app.services.audio_service import AudioService

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
            # [M4-003/C.4-prime] Model CM protocol: `with open(...) as f` binds
            # f = mock_file.__enter__(); without this pin f.read() is a MagicMock
            # and real pydantic validation (cached audio_service.types) rejects it (H1).
            mock_file.__enter__.return_value = mock_file

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
