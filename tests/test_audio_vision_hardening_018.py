"""
Regression pins for BOT-BUILD-MOTO-CANON-018 C-17.

Validates that AudioService and VisionService Gemini wrappers apply
asyncio.wait_for, capture asyncio.TimeoutError, and retry with exponential
backoff (base_delay=2.0 + jitter).
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.audio_service import AudioService, GEMINI_CALL_TIMEOUT_S as AUDIO_TIMEOUT
from app.services.vision_service import VisionService, GEMINI_CALL_TIMEOUT_S as VISION_TIMEOUT


# ---------------------------------------------------------------------------
# AUDIO-HARDEN — audio_service wraps sync call in wait_for + TimeoutError retry
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_moto_canon_018_audio_harden_timeout_retry(monkeypatch, caplog):
    caplog.set_level("ERROR", logger="app.services.audio_service")

    sleep_calls = []

    async def _fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr("app.services.audio_service.asyncio.sleep", _fake_sleep)

    svc = AudioService.__new__(AudioService)
    svc.client = MagicMock()
    svc._model_id = "test-model"

    attempt = 0

    def _sync_generate_content(*args, **kwargs):
        nonlocal attempt
        attempt += 1
        raise asyncio.TimeoutError("forced timeout")

    svc.client.models.generate_content = _sync_generate_content

    with pytest.raises(asyncio.TimeoutError):
        await svc._call_gemini_with_retry_async(svc.client.models.generate_content, contents=[])

    assert attempt == 3
    assert len(sleep_calls) == 2
    assert sleep_calls[0] >= 2.0
    assert sleep_calls[1] >= 4.0
    assert "🚨 [AUDIO GEMINI ERROR] Final timeout failure" in caplog.text


# ---------------------------------------------------------------------------
# VISION-HARDEN — vision_service wraps to_thread in wait_for + TimeoutError retry
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_moto_canon_018_vision_harden_timeout_retry(monkeypatch, caplog):
    caplog.set_level("ERROR", logger="app.services.vision_service")

    sleep_calls = []

    async def _fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr("app.services.vision_service.asyncio.sleep", _fake_sleep)

    svc = VisionService.__new__(VisionService)
    svc.client = MagicMock()
    svc._model_id = "test-model"

    attempt = 0

    def _sync_generate_content(*args, **kwargs):
        nonlocal attempt
        attempt += 1
        raise asyncio.TimeoutError("forced timeout")

    svc.client.models.generate_content = _sync_generate_content

    with pytest.raises(asyncio.TimeoutError):
        await svc._call_gemini_with_retry_async(contents=[])

    assert attempt == 3
    assert len(sleep_calls) == 2
    assert sleep_calls[0] >= 2.0
    assert sleep_calls[1] >= 4.0
    assert "🚨 [VISION GEMINI ERROR] Final timeout failure" in caplog.text


# ---------------------------------------------------------------------------
# Sanity: timeout constants are aligned with ai_brain Fix C capa 1
# ---------------------------------------------------------------------------
def test_moto_canon_018_av_timeout_constants_aligned():
    assert AUDIO_TIMEOUT == 18.0
    assert VISION_TIMEOUT == 18.0
