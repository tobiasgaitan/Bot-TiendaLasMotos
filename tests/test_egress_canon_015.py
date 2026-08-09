"""
[BOT-BUILD-EGRESS-CANON-015]
Pins de regresión para egreso determinista de imagen y modelo.

Evidencia del incidente: Top Result=VICTORY MRX 125 pero texto recomendó MRX 150;
URL alucinada auteco.com.co extirpada dejando sustituidas=0 y Visual-Lock V1 inactivo
ante Markdown presente-pero-extirpado.

Objetivo: (a) imagen desde imagen_url de la ficha del Top Result independiente del eco LLM;
(b) texto alineado a matches[0] vía énfasis TOP RESULT + retry guard; (c) sustitución SSOT
contra modelo recomendado; (d) M2 exact-equality intacto; (e) stash efímero nunca persiste.
"""
import logging
import re
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

PHONE_E164 = "+573192564288"
PHONE_NUMBER_ID = "999999"

MRX125_NAME = "Victory MRX 125"
MRX125_URL = (
    "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos.appspot.com/o/"
    "mrx125.png?alt=media"
)
MRX150_NAME = "Victory MRX 150"
MRX150_URL = (
    "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos.appspot.com/o/"
    "mrx150.png?alt=media"
)
AUTECO_URL = "https://auteco.com.co/images/victory-mrx-150.webp"


def _make_fc_response(tool_name: str, tool_args: dict):
    """Mock Gemini response carrying a single function_call part."""
    mock_response = MagicMock()
    mock_part = MagicMock()
    mock_part.text = None
    fc = MagicMock()
    fc.name = tool_name
    fc.args = tool_args
    mock_part.function_call = fc
    mock_response.candidates = [MagicMock()]
    mock_response.candidates[0].content.parts = [mock_part]
    mock_response.usage_metadata = MagicMock()
    mock_response.usage_metadata.total_token_count = 100
    return mock_response


def _make_text_response(text: str):
    mock_response = MagicMock()
    mock_part = MagicMock()
    mock_part.text = text
    mock_part.function_call = None
    mock_response.candidates = [MagicMock()]
    mock_response.candidates[0].content.parts = [mock_part]
    mock_response.usage_metadata = MagicMock()
    mock_response.usage_metadata.total_token_count = 100
    return mock_response


def _build_catalog_service_singleton():
    """Real CatalogService with manually populated indexes for URL-Lock tests."""
    from app.services.catalog_service import CatalogService

    catalog = CatalogService()
    catalog._items = [
        {
            "id": "victory-mrx-125",
            "name": MRX125_NAME,
            "price": 8500000,
            "cc": 125,
            "category": "Enduro",
            "searchBy": ["doble", "proposito", "enduro"],
            "search_tokens": ["victory", "mrx", "125", "doble", "proposito"],
            "search_text": "victory mrx 125 doble proposito enduro",
            "description": "",
            "image_url": MRX125_URL,
            "bonusAmount": 0,
            "bonusEndDate": None,
        },
        {
            "id": "victory-mrx-150",
            "name": MRX150_NAME,
            "price": 9000000,
            "cc": 150,
            "category": "Enduro",
            "searchBy": ["doble", "proposito", "enduro"],
            "search_tokens": ["victory", "mrx", "150", "doble", "proposito"],
            "search_text": "victory mrx 150 doble proposito enduro",
            "description": "",
            "image_url": MRX150_URL,
            "bonusAmount": 0,
            "bonusEndDate": None,
        },
    ]
    catalog._items_by_image_url_norm = {}
    for item in catalog._items:
        norm = CatalogService._normalize_image_url(item["image_url"])
        catalog._items_by_image_url_norm[norm] = item
    catalog._category_aliases = {}
    catalog._class_category_aliases = {}
    return catalog


# -----------------------------------------------------------------------------
# Pin 1: URL alucinada auteco + precio → Strategy A con imagen del Top Result
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_canon_injection_when_auteco_hallucination_stripped(caplog):
    """
    GIVEN response with wrong-model Markdown on auteco.com.co + stash top=MRX 125.
    WHEN _pipeline_egress runs URL-Lock first.
    THEN auteco URL is stripped, canonical MRX 125 image injected via Strategy A,
         url_report.summary() is logged, and no raw markdown remains in caption.
    """
    caplog.set_level(logging.INFO)
    from app.routers.whatsapp import _pipeline_egress

    catalog = _build_catalog_service_singleton()
    response_text = (
        f"Te recomiendo la {MRX150_NAME} por $9.000.000. "
        f"![{MRX150_NAME}]({AUTECO_URL})"
    )
    prospect_data = {
        "exists": True,
        "phone": PHONE_E164,
        "_catalog_top_name": MRX125_NAME,
        "_catalog_top_image": MRX125_URL,
    }

    mock_image_sender = AsyncMock(return_value=True)
    mock_text_sender = AsyncMock(return_value=True)
    mock_ms = MagicMock()
    mock_ms.save_message = AsyncMock()

    with patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp._send_whatsapp_image", mock_image_sender), \
         patch("app.routers.whatsapp._send_whatsapp_message", mock_text_sender), \
         patch("app.routers.whatsapp._process_and_send_egress_message", AsyncMock()), \
         patch("app.services.catalog_service.catalog_service", catalog):
        await _pipeline_egress(
            response_text,
            user_phone=PHONE_E164,
            phone_number_id=PHONE_NUMBER_ID,
            prospect_data=prospect_data,
            catalog=catalog,
        )

    mock_image_sender.assert_awaited_once()
    args = mock_image_sender.await_args
    assert args.args[0] == PHONE_E164
    assert args.args[1] == MRX125_URL
    caption = args.kwargs.get("caption") or (args.args[2] if len(args.args) > 2 else "")
    assert "auteco" not in caption.lower()
    assert "![" not in caption
    assert "$9.000.000" in caption

    # url_report.summary() must be logged (not bound to _)
    assert any("🔒 [URL-LOCK]" in r.message and "extirpadas=1" in r.message for r in caplog.records)

    # Unified egress path must NOT be invoked when we inject.
    mock_text_sender.assert_not_called()


# -----------------------------------------------------------------------------
# Pin 2: LLM recomienda matches[1] → retry guard → texto final con Top Result
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_alignment_guard_retries_until_top_result_recommended():
    """
    GIVEN tool-response with matches[0]=MRX 125, matches[1]=MRX 150;
          LLM first final text recommends MRX 150.
    WHEN alignment guard fires.
    THEN a retry instruction naming the TOP RESULT is emitted and the final text
         recommends MRX 125. Stash fields are populated.
    """
    from app.services.ai_brain import CerebroIA

    fake_catalog = MagicMock()
    fake_catalog.search_items = MagicMock(
        return_value=[
            {
                "name": MRX125_NAME,
                "category": "Enduro",
                "price": "$8.500.000",
                "image_url": MRX125_URL,
                "summary": "",
            },
            {
                "name": MRX150_NAME,
                "category": "Enduro",
                "price": "$9.000.000",
                "image_url": MRX150_URL,
                "summary": "",
            },
        ]
    )
    fake_catalog.get_catalog_aliases.return_value = {}
    fake_catalog._items = fake_catalog.search_items.return_value

    cerebro = CerebroIA(catalog_service=fake_catalog)
    cerebro.client = MagicMock()
    cerebro.motor_financiero = MagicMock()

    sent_payloads = []
    responses = [
        _make_fc_response("search_catalog", {"query": "doble propósito"}),
        _make_text_response(
            f"Para doble propósito te recomiendo la {MRX150_NAME} por $9.000.000. "
            f"![{MRX150_NAME}]({MRX150_URL})\n\nFicha Tecnica: Motor 150cc, ideal para ciudad."
        ),
        _make_text_response(
            f"Para doble propósito te recomiendo la {MRX125_NAME} por $8.500.000. "
            f"![{MRX125_NAME}]({MRX125_URL})\n\nFicha Tecnica: Motor 125cc, perfecta para doble propósito."
        ),
    ]

    async def _send(*args, **kwargs):
        if args:
            sent_payloads.append(args[0])
        return responses.pop(0)

    mock_chat = MagicMock()
    mock_chat.send_message = AsyncMock(side_effect=_send)
    cerebro.client.aio.chats.create.return_value = mock_chat

    prospect_data = {
        "exists": True,
        "phone": PHONE_E164,
        "moto_interest": "",
        "moto_confirmada": False,
        "forma_pago": "",
        "habeas_data_accepted": False,
        "habeas_data_accepted_sent": False,
    }
    user_text = "Hola, quisiera una moto doble propósito a crédito"

    with patch("app.services.config_service.config_service") as mock_cfg:
        mock_cfg.get_registration_cost.return_value = 0
        mock_cfg.get_catalog_aliases.return_value = {}
        result = await cerebro.pensar_respuesta(
            texto=user_text,
            prospect_data=prospect_data,
            history=[{"role": "user", "content": user_text}],
        )

    assert MRX125_NAME in result, f"Expected Top Result in final text, got: {result}"
    assert MRX150_NAME not in result or MRX125_NAME in result
    assert prospect_data["moto_interest"] == MRX125_NAME
    assert prospect_data["_catalog_top_name"] == MRX125_NAME
    assert prospect_data["_catalog_top_image"] == MRX125_URL

    # Retry instruction must have been sent naming the TOP RESULT.
    assert any(
        isinstance(p, str) and "TOP RESULT" in p and MRX125_NAME in p
        for p in sent_payloads
    ), "Expected forced retry instruction naming the Top Result"


# -----------------------------------------------------------------------------
# Pin 3: Categoría nunca canónica (M2 exact-equality intacto)
# -----------------------------------------------------------------------------
def test_m2_exact_name_canonicity_category_stays_phase_1():
    """
    GIVEN moto_interest is a category ('doble propósito') and credit intent in history;
          catalog usable with exact-name items.
    WHEN _determine_funnel_phase evaluates.
    THEN phase is PHASE_1_PROFILING — M2 exact-equality is NOT weakened.
    """
    from app.services.ai_brain import CerebroIA

    fake_catalog = MagicMock()
    fake_catalog._items = [{"name": "Victory MRX 125"}, {"name": "Victory MRX 150"}]
    fake_catalog.get_all_items.return_value = fake_catalog._items

    cerebro = CerebroIA(catalog_service=fake_catalog)
    prospect_data = {
        "moto_interest": "doble propósito",
        "forma_pago": "",
        "habeas_data_accepted": False,
        "habeas_data_accepted_sent": False,
    }
    history = [{"role": "user", "content": "Hola, quisiera una moto doble propósito a crédito"}]

    phase = cerebro._determine_funnel_phase(prospect_data, history=history)
    assert phase == "PHASE_1_PROFILING"


# -----------------------------------------------------------------------------
# Pin 4: Sustitución SSOT contra modelo recomendado cuando stem no único
# -----------------------------------------------------------------------------
def test_substitute_from_catalog_uses_recommended_model_when_stem_not_unique():
    """
    GIVEN an auteco URL whose stem/token set is NOT unique across the catalog.
    WHEN _substitute_from_catalog receives recommended_model='Victory MRX 125'.
    THEN it returns the canonical image_url of MRX 125 instead of None.
    """
    from app.services.egress_guard_service import _substitute_from_catalog

    catalog = _build_catalog_service_singleton()
    # Both items share tokens {victory, mrx} so stem-only/token-only uniqueness fails.
    with patch("app.services.catalog_service.catalog_service", catalog):
        result = _substitute_from_catalog(AUTECO_URL, recommended_model=MRX125_NAME)

    assert result == MRX125_URL, f"Expected MRX 125 image, got {result!r}"


# -----------------------------------------------------------------------------
# Pin 5: Wrong-model con host canónico → Strategy A con imagen del Top
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_canon_injection_when_wrong_model_canonical_host():
    """
    GIVEN response with Markdown pointing to a canonical host but wrong model
          (MRX 150) while stash top=MRX 125.
    WHEN _pipeline_egress resolves post-URL-Lock state.
    THEN canonical MRX 125 image is injected and caption strips the wrong markdown.
    """
    from app.routers.whatsapp import _pipeline_egress

    catalog = _build_catalog_service_singleton()
    response_text = (
        f"Te recomiendo la {MRX150_NAME} por $9.000.000. "
        f"![{MRX150_NAME}]({MRX150_URL})"
    )
    prospect_data = {
        "exists": True,
        "phone": PHONE_E164,
        "_catalog_top_name": MRX125_NAME,
        "_catalog_top_image": MRX125_URL,
    }

    mock_image_sender = AsyncMock(return_value=True)
    mock_text_sender = AsyncMock(return_value=True)
    mock_ms = MagicMock()
    mock_ms.save_message = AsyncMock()

    with patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp._send_whatsapp_image", mock_image_sender), \
         patch("app.routers.whatsapp._send_whatsapp_message", mock_text_sender), \
         patch("app.routers.whatsapp._process_and_send_egress_message", AsyncMock()), \
         patch("app.services.catalog_service.catalog_service", catalog):
        await _pipeline_egress(
            response_text,
            user_phone=PHONE_E164,
            phone_number_id=PHONE_NUMBER_ID,
            prospect_data=prospect_data,
            catalog=catalog,
        )

    mock_image_sender.assert_awaited_once()
    args = mock_image_sender.await_args
    assert args.args[1] == MRX125_URL
    caption = args.kwargs.get("caption") or (args.args[2] if len(args.args) > 2 else "")
    # The caption keeps the LLM wording but the image token (wrong model URL)
    # must be stripped because the canonical top-result image is sent separately.
    assert "mrx150.png" not in caption
    assert "![" not in caption
    assert MRX150_NAME in caption


# -----------------------------------------------------------------------------
# Pin 6: Eco correcto (dueño==top, host canónico) → PEI-5 preservado
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_no_extra_injection_when_llm_echo_matches_top_result():
    """
    GIVEN response with correct Markdown for the Top Result (MRX 125) on canonical host.
    WHEN _pipeline_egress runs.
    THEN no extra Strategy A injection happens; delegation to the unified egress path
         handles the existing Markdown (PEI-5 intacto).
    """
    from app.routers.whatsapp import _pipeline_egress

    catalog = _build_catalog_service_singleton()
    response_text = (
        f"Mira esta {MRX125_NAME}\n\n"
        f"![{MRX125_NAME}]({MRX125_URL})\n\n"
        f"Precio: $8.500.000"
    )
    prospect_data = {
        "exists": True,
        "phone": PHONE_E164,
        "_catalog_top_name": MRX125_NAME,
        "_catalog_top_image": MRX125_URL,
    }

    timeline = []

    async def _send_image(phone, url, caption="", phone_number_id=None, **kwargs):
        timeline.append(("send_image", url, caption))
        return True

    async def _save(phone, role, content, **kwargs):
        timeline.append(("save", role, content))
        return True

    mock_image_sender = AsyncMock(side_effect=_send_image)
    mock_text_sender = AsyncMock(return_value=True)
    mock_ms = MagicMock()
    mock_ms.save_message = AsyncMock(side_effect=_save)

    with patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp._send_whatsapp_image", mock_image_sender), \
         patch("app.routers.whatsapp._send_whatsapp_message", mock_text_sender), \
         patch("app.services.catalog_service.catalog_service", catalog):
        await _pipeline_egress(
            response_text,
            user_phone=PHONE_E164,
            phone_number_id=PHONE_NUMBER_ID,
            prospect_data=prospect_data,
            catalog=catalog,
        )

    # Strategy A from unified egress sends image once.
    mock_image_sender.assert_awaited_once()
    assert timeline[0][0] == "send_image"
    assert timeline[0][1] == MRX125_URL
    caption = timeline[0][2]
    assert "![" not in caption and "](" not in caption
    assert f"Mira esta {MRX125_NAME}" in caption
    assert "Precio: $8.500.000" in caption

    # Eco save(model) posterior al envío (PEI-5).
    assert [e[0] for e in timeline] == ["send_image", "save"]
    assert timeline[1][1] == "model"
    saved_text = timeline[1][2]
    assert "![" not in saved_text and "](" not in saved_text


# -----------------------------------------------------------------------------
# Pin 7: Stash efímero AUSENTE del documento Firestore post-turno
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ephemeral_stash_not_persisted_to_firestore():
    """
    GIVEN prospect_data carries _catalog_top_name/_catalog_top_image.
    WHEN _pipeline_egress finishes.
    THEN the stash keys are popped from prospect_data and never reach save_message
         or persist_credit_score_result payloads.
    """
    from app.routers.whatsapp import _pipeline_egress

    catalog = _build_catalog_service_singleton()
    response_text = f"Te recomiendo la {MRX125_NAME} por $8.500.000."
    prospect_data = {
        "exists": True,
        "phone": PHONE_E164,
        "_catalog_top_name": MRX125_NAME,
        "_catalog_top_image": MRX125_URL,
    }

    saved_payloads = []

    async def _save(phone, role, content, **kwargs):
        saved_payloads.append((role, content))
        return True

    mock_ms = MagicMock()
    mock_ms.save_message = AsyncMock(side_effect=_save)

    with patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp._send_whatsapp_message", AsyncMock(return_value=True)), \
         patch("app.services.catalog_service.catalog_service", catalog):
        await _pipeline_egress(
            response_text,
            user_phone=PHONE_E164,
            phone_number_id=PHONE_NUMBER_ID,
            prospect_data=prospect_data,
            catalog=catalog,
        )

    assert "_catalog_top_name" not in prospect_data
    assert "_catalog_top_image" not in prospect_data
    for role, content in saved_payloads:
        assert "_catalog_top_name" not in str(content)
        assert "_catalog_top_image" not in str(content)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
