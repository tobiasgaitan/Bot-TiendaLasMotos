"""
[AUD-DEUDA-DASH-008] Extensión del writer de score a media y fallback del Juez.

Verifica que el marcador `_score_resultado` (único productor en ai_brain.py) se
consuma también en:
  - Rama moto del pipeline media/visión (G1).
  - Rama sticker/meme del pipeline media/visión (G2).
  - Fallback del Juez en texto (G3) y audio (G4).
  - Rama de error crítico en texto (G5).

Y conserva el comportamiento existente cuando no hay marcador (pins MVI-2/MVI-3,
tci3). HANDOFF sigue sin persistir score (R1).

Denominador canónico: 673 + 9 = 682 (677 tests/ + 5 scripts/).
"""
import random

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.routers.whatsapp import (
    _pipeline_audio,
    _pipeline_egress,
    _pipeline_media_vision,
    _pipeline_text_cognitive,
)
from app.services.memory_service import MemoryService
from tests.factories import make_catalog_item, format_cop

PHONE_E164 = "+573192564288"
PHONE_RAW = "573192564288"
PHONE_NUMBER_ID = "999999"
FALLBACK_MSG = "Disculpa, no estoy seguro de la respuesta, permíteme le pregunto a mi supervisor y te comento."
SCORE_MARKER = {"score": 817, "entity": "Brilla de Gases", "strategy": "Consignación"}


def _prospect(human_help: bool = False) -> dict:
    return {
        "exists": True,
        "status": "IN_PROGRESS",
        "chatbot_status": "ACTIVE",
        "name": "Juan Test",
        "celular": PHONE_E164,
        "ai_summary": "Resumen previo",
        "human_help_requested": human_help,
    }


def _build_ms_mock(timeline: list | None = None, prospect: dict | None = None) -> MagicMock:
    prospect = prospect or _prospect()
    ms = MagicMock()
    ms.create_prospect_if_missing = AsyncMock()
    ms.update_last_interaction = AsyncMock()
    ms.transition_to_in_progress = AsyncMock()
    ms.generate_and_update_summary = AsyncMock()
    ms.set_human_help_status = AsyncMock()
    ms.delete_prospect_completely = AsyncMock(return_value=True)
    ms.get_or_create_prospect = AsyncMock(return_value=prospect)
    ms.get_prospect_data = AsyncMock(return_value=prospect)
    ms.get_chat_history = AsyncMock(return_value=[])
    ms.persist_credit_score_result = AsyncMock()

    if timeline is not None:
        async def _save(phone, role, content, **kwargs):
            timeline.append((f"save_message:{role}", content))
            return True

        ms.save_message = AsyncMock(side_effect=_save)
    else:
        ms.save_message = AsyncMock()

    ms.update_prospect_summary = AsyncMock()
    return ms


def _moto_item() -> tuple[dict, dict, str]:
    item = make_catalog_item(1, random.Random(2026))
    canonical_price = format_cop(item["price"])
    matched = {
        "id": item["id"],
        "name": item["name"],
        "image_url": item["image_url"],
        "price": item["price"],
        "formatted_price": canonical_price,
        "summary": item["summary"],
        "active": True,
    }
    return item, matched, canonical_price


def _image_payload(caption: str = "") -> dict:
    return {
        "from": PHONE_RAW,
        "id": "wamid.mvi",
        "type": "image",
        "phone_number_id": PHONE_NUMBER_ID,
        "image": {"id": "media-mvi-1", "mime_type": "image/jpeg", "caption": caption},
    }


def _sticker_payload(emoji: str = "👍") -> dict:
    return {
        "from": PHONE_RAW,
        "id": "wamid.stk",
        "type": "sticker",
        "phone_number_id": PHONE_NUMBER_ID,
        "sticker": {"id": "media-stk-1", "mime_type": "image/webp", "emoji": emoji},
    }


def _audio_payload() -> dict:
    return {
        "from": PHONE_RAW,
        "id": "wamid.ai",
        "type": "audio",
        "phone_number_id": PHONE_NUMBER_ID,
        "media_id": "media-ai-1",
        "mime_type": "audio/ogg; codecs=opus",
    }


def _text_payload(body: str = "Hola") -> dict:
    return {
        "from": PHONE_RAW,
        "id": "wamid.txt",
        "type": "text",
        "phone_number_id": PHONE_NUMBER_ID,
        "text": {"body": body},
    }


# ── G1: rama moto media/visión ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_m1_moto_path_with_marker_uses_score_persist():
    """G1: marcador presente → _process_and_send_egress_message recibe score_persist."""
    item, matched, canonical_price = _moto_item()
    mock_ms = _build_ms_mock()
    mock_cerebro = MagicMock()

    async def _pensar(*args, **kwargs):
        prospect_data = kwargs.get("prospect_data")
        if prospect_data is not None:
            prospect_data["_score_resultado"] = SCORE_MARKER
        return f"Claro, la {item['name']} es una dura."

    mock_cerebro.pensar_respuesta = AsyncMock(side_effect=_pensar)
    mock_vision = MagicMock()
    mock_vision.analyze_image = AsyncMock(return_value=f"MOTO_DETECTADA: {item['name']}")
    mock_catalog = MagicMock()
    mock_catalog.get_vision_catalog_projection = MagicMock(return_value=[])
    mock_catalog.match_catalog_item_by_image = MagicMock(return_value=matched)
    mock_catalog._rehydrate_formatted_price = MagicMock(return_value=canonical_price)
    mock_storage = MagicMock()
    mock_storage.download_media = AsyncMock(return_value=b"fake_image_bytes")

    captured_kwargs = {}

    async def _egress(phone, text, phone_number_id=None, **kwargs):
        captured_kwargs["phone"] = phone
        captured_kwargs["text"] = text
        captured_kwargs["score_persist"] = kwargs.get("score_persist")
        return True

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.routers.whatsapp.storage_service", mock_storage), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.VisionService", return_value=mock_vision), \
         patch("app.routers.whatsapp.db", MagicMock(name="global_db")), \
         patch("app.routers.whatsapp._process_and_send_egress_message", AsyncMock(side_effect=_egress)), \
         patch("app.routers.whatsapp._send_whatsapp_message", AsyncMock(return_value=True)):
        await _pipeline_media_vision(
            _image_payload(),
            user_phone=PHONE_E164,
            msg_type="image",
            phone_number_id=PHONE_NUMBER_ID,
        )

    assert captured_kwargs.get("score_persist") == SCORE_MARKER
    mock_ms.save_message.assert_awaited_once_with(PHONE_E164, "user", mock_ms.save_message.await_args.args[2])


@pytest.mark.asyncio
async def test_m2_moto_path_without_marker_keeps_exact_signature():
    """G1: sin marcador → llamada actual (sin score_persist)."""
    item, matched, canonical_price = _moto_item()
    mock_ms = _build_ms_mock()
    mock_cerebro = MagicMock()
    mock_cerebro.pensar_respuesta = AsyncMock(return_value=f"Claro, la {item['name']} es una dura.")
    mock_vision = MagicMock()
    mock_vision.analyze_image = AsyncMock(return_value=f"MOTO_DETECTADA: {item['name']}")
    mock_catalog = MagicMock()
    mock_catalog.get_vision_catalog_projection = MagicMock(return_value=[])
    mock_catalog.match_catalog_item_by_image = MagicMock(return_value=matched)
    mock_catalog._rehydrate_formatted_price = MagicMock(return_value=canonical_price)
    mock_storage = MagicMock()
    mock_storage.download_media = AsyncMock(return_value=b"fake_image_bytes")
    mock_egress = AsyncMock(return_value=True)

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.routers.whatsapp.storage_service", mock_storage), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.VisionService", return_value=mock_vision), \
         patch("app.routers.whatsapp.db", MagicMock(name="global_db")), \
         patch("app.routers.whatsapp._process_and_send_egress_message", mock_egress), \
         patch("app.routers.whatsapp._send_whatsapp_message", AsyncMock(return_value=True)):
        await _pipeline_media_vision(
            _image_payload(),
            user_phone=PHONE_E164,
            msg_type="image",
            phone_number_id=PHONE_NUMBER_ID,
        )

    mock_egress.assert_awaited_once_with(PHONE_E164, mock_egress.await_args.args[1], phone_number_id=PHONE_NUMBER_ID)
    assert mock_egress.await_args.kwargs == {"phone_number_id": PHONE_NUMBER_ID}
    mock_ms.persist_credit_score_result.assert_not_awaited()


# ── G2: rama sticker/meme media/visión ────────────────────────────────────────

@pytest.mark.asyncio
async def test_m3_sticker_path_with_marker_uses_writer():
    """G2: marcador presente → persist_credit_score_result reemplaza save_message(model)."""
    mock_ms = _build_ms_mock()
    mock_cerebro = MagicMock()

    async def _pensar(*args, **kwargs):
        prospect_data = kwargs.get("prospect_data")
        if prospect_data is not None:
            prospect_data["_score_resultado"] = SCORE_MARKER
        return "Perfecto, sigamos."

    mock_cerebro.pensar_respuesta = AsyncMock(side_effect=_pensar)
    mock_vision = MagicMock()
    mock_vision.analyze_image = AsyncMock(return_value="[System Note: affirmative thumbs up]")
    mock_catalog = MagicMock()
    mock_storage = MagicMock()
    mock_storage.download_media = AsyncMock(return_value=b"fake_sticker_bytes")

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.routers.whatsapp.storage_service", mock_storage), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.VisionService", return_value=mock_vision), \
         patch("app.routers.whatsapp.db", MagicMock(name="global_db")), \
         patch("app.routers.whatsapp._send_whatsapp_message", AsyncMock(return_value=True)):
        await _pipeline_media_vision(
            _sticker_payload(),
            user_phone=PHONE_E164,
            msg_type="sticker",
            phone_number_id=PHONE_NUMBER_ID,
        )

    mock_ms.persist_credit_score_result.assert_awaited_once_with(PHONE_E164, SCORE_MARKER, "Perfecto, sigamos.")
    # save_message(user) se conserva; save_message(model) no se invoca.
    model_saves = [c for c in mock_ms.save_message.await_args_list if c.args[1] == "model"]
    assert len(model_saves) == 0


@pytest.mark.asyncio
async def test_m4_sticker_path_without_marker_keeps_plain_save():
    """G2: sin marcador → comportamiento actual (user + model save)."""
    mock_ms = _build_ms_mock()
    mock_cerebro = MagicMock()
    mock_cerebro.pensar_respuesta = AsyncMock(return_value="Perfecto, sigamos.")
    mock_vision = MagicMock()
    mock_vision.analyze_image = AsyncMock(return_value="[System Note: affirmative thumbs up]")
    mock_catalog = MagicMock()
    mock_storage = MagicMock()
    mock_storage.download_media = AsyncMock(return_value=b"fake_sticker_bytes")

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.routers.whatsapp.storage_service", mock_storage), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.VisionService", return_value=mock_vision), \
         patch("app.routers.whatsapp.db", MagicMock(name="global_db")), \
         patch("app.routers.whatsapp._send_whatsapp_message", AsyncMock(return_value=True)):
        await _pipeline_media_vision(
            _sticker_payload(),
            user_phone=PHONE_E164,
            msg_type="sticker",
            phone_number_id=PHONE_NUMBER_ID,
        )

    mock_ms.persist_credit_score_result.assert_not_awaited()
    mock_ms.save_message.assert_any_await(PHONE_E164, "user", "Sí")
    mock_ms.save_message.assert_any_await(PHONE_E164, "model", "Perfecto, sigamos.")


# ── G3/G5: fallback del Juez en texto ────────────────────────────────────────

@pytest.mark.asyncio
async def test_f1_text_judge_fallback_with_marker_uses_writer():
    """G3: fallback del Juez texto + marcador → writer con fallback_msg."""
    prospect = _prospect()
    mock_ms = _build_ms_mock(prospect=prospect)
    mock_cerebro = MagicMock()

    async def _pensar(*args, **kwargs):
        prospect_data = kwargs.get("prospect_data")
        if prospect_data is not None:
            prospect_data["_score_resultado"] = SCORE_MARKER
        return "Respuesta que el Juez rechazará."

    mock_cerebro.pensar_respuesta = AsyncMock(side_effect=_pensar)
    mock_judge = MagicMock()
    mock_judge.analyze_response = AsyncMock(return_value=(False, "C1_VISUAL_LOCK"))
    mock_catalog = MagicMock()
    mock_catalog.search = MagicMock(return_value=[])

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.judge_service", mock_judge), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp._send_whatsapp_message", AsyncMock(return_value=True)), \
         patch("app.routers.whatsapp._mark_ponytail_deprioritized", new_callable=AsyncMock) as mock_ponytail:
        result = await _pipeline_text_cognitive(
            _text_payload(),
            user_phone=PHONE_E164,
            phone_number_id=PHONE_NUMBER_ID,
            message_body="test",
            cerebro_ia=mock_cerebro,
            context="",
            prospect_data=prospect,
            current_history=[],
            skip_greeting=True,
        )

    assert result[0] is None
    mock_ms.set_human_help_status.assert_awaited_once_with(PHONE_E164, True)
    mock_ponytail.assert_awaited_once()
    mock_ms.persist_credit_score_result.assert_awaited_once_with(PHONE_E164, SCORE_MARKER, FALLBACK_MSG)
    # No save_message plano de model
    model_saves = [c for c in mock_ms.save_message.await_args_list if c.args[1] == "model"]
    assert len(model_saves) == 0


@pytest.mark.asyncio
async def test_f3_text_judge_fallback_without_marker_uses_plain_save():
    """G3: fallback del Juez texto sin marcador → save_message(model) plano."""
    prospect = _prospect()
    mock_ms = _build_ms_mock(prospect=prospect)
    mock_cerebro = MagicMock()
    mock_cerebro.pensar_respuesta = AsyncMock(return_value="Respuesta que el Juez rechazará.")
    mock_judge = MagicMock()
    mock_judge.analyze_response = AsyncMock(return_value=(False, "C1_VISUAL_LOCK"))
    mock_catalog = MagicMock()
    mock_catalog.search = MagicMock(return_value=[])

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.judge_service", mock_judge), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp._send_whatsapp_message", AsyncMock(return_value=True)), \
         patch("app.routers.whatsapp._mark_ponytail_deprioritized", new_callable=AsyncMock):
        await _pipeline_text_cognitive(
            _text_payload(),
            user_phone=PHONE_E164,
            phone_number_id=PHONE_NUMBER_ID,
            message_body="test",
            cerebro_ia=mock_cerebro,
            context="",
            prospect_data=prospect,
            current_history=[],
            skip_greeting=True,
        )

    mock_ms.persist_credit_score_result.assert_not_awaited()
    mock_ms.save_message.assert_any_await(PHONE_E164, "model", FALLBACK_MSG)


# ── G4: fallback del Juez en audio ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_f2_audio_judge_fallback_with_marker_uses_writer():
    """G4: fallback del Juez audio + marcador → writer con fallback_msg."""
    prospect = _prospect()
    mock_ms = _build_ms_mock(prospect=prospect)
    mock_audio = MagicMock()
    mock_audio.transcribe_audio = AsyncMock(return_value="Quiero la Victory")
    mock_storage = MagicMock()
    mock_storage.download_media = AsyncMock(return_value=b"fake_audio_bytes")
    mock_cerebro = MagicMock()

    async def _pensar(*args, **kwargs):
        prospect_data = kwargs.get("prospect_data")
        if prospect_data is not None:
            prospect_data["_score_resultado"] = SCORE_MARKER
        return "Respuesta que el Juez rechazará."

    mock_cerebro.pensar_respuesta = AsyncMock(side_effect=_pensar)
    mock_judge = MagicMock()
    mock_judge.analyze_response = AsyncMock(return_value=(False, "C1_VISUAL_LOCK"))
    mock_catalog = MagicMock()
    mock_catalog.normalize_transcription = MagicMock(side_effect=lambda x: x)
    mock_catalog.search = MagicMock(return_value=[])

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.AudioService", return_value=mock_audio), \
         patch("app.routers.whatsapp.storage_service", mock_storage), \
         patch("app.routers.whatsapp.judge_service", mock_judge), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp._send_whatsapp_message", AsyncMock(return_value=True)), \
         patch("app.routers.whatsapp._mark_ponytail_deprioritized", new_callable=AsyncMock):
        result = await _pipeline_audio(
            _audio_payload(),
            user_phone=PHONE_E164,
            phone_number_id=PHONE_NUMBER_ID,
            cerebro_ia=mock_cerebro,
            context="",
            prospect_data=prospect,
        )

    assert result[0] is None
    mock_ms.persist_credit_score_result.assert_awaited_once_with(PHONE_E164, SCORE_MARKER, FALLBACK_MSG)


# ── I1: idempotencia del writer ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_i1_idempotency_same_content_bucket_collapses():
    """I1: mismo content+bucket → mismo dedup id (colapso de redeliveries)."""
    ms = MemoryService(db=MagicMock())
    did1 = ms._score_historial_dedup_id(PHONE_E164, "Score 817", now=1_000_000)
    did2 = ms._score_historial_dedup_id(PHONE_E164, "Score 817", now=1_000_001)
    did3 = ms._score_historial_dedup_id(PHONE_E164, "Score 817", now=1_000_000 + 199)
    assert did1 == did2
    assert did1 == did3
    did_other_bucket = ms._score_historial_dedup_id(PHONE_E164, "Score 817", now=1_000_000 + 200)
    assert did1 != did_other_bucket


# ── R1: HANDOFF no persiste score (regresión) ─────────────────────────────────

@pytest.mark.asyncio
async def test_r1_handoff_with_marker_does_not_persist():
    """R1: HANDOFF_TRIGGERED + marcador → warning, sin persistencia."""
    mock_ms = _build_ms_mock()
    prospect = _prospect()
    prospect["_score_resultado"] = SCORE_MARKER

    with patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp._send_whatsapp_message", AsyncMock(return_value=True)), \
         patch("app.routers.whatsapp._mark_ponytail_deprioritized", new_callable=AsyncMock):
        await _pipeline_egress(
            "HANDOFF_TRIGGERED: por favor transferir",
            user_phone=PHONE_E164,
            phone_number_id=PHONE_NUMBER_ID,
            prospect_data=prospect,
        )

    mock_ms.persist_credit_score_result.assert_not_awaited()
    assert "_score_resultado" not in prospect
