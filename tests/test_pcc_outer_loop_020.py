"""
Invariant I-1 pins for C-20b — route-specific exit guarantees from pensar_respuesta.

Every output of pensar_respuesta must be either text validated by run_checker
or a conforming fallback built by _build_pcc_fallback. No third category.
Non-catalog outputs (FAQ, HANDOFF, non-moto with non-empty text) preserve
_validate_output.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai_brain import CerebroIA


STASH_NAME = "Victory MRX 150"
STASH_IMAGE = "https://img.url/mrx150.png"


def _build_cerebro():
    return CerebroIA(catalog_service=None)


def _valid_text():
    return "Te recomiendo la TVS Apache RTR 160 4V por $7.990.000. Ficha Tecnica: TVS Apache RTR 160 4V ![moto](https://img.url/rtr160.png)"


def _non_compliant_text():
    return "sin precio ni imagen, pero te la recomiendo"


def _empty_text():
    return ""


# ---------------------------------------------------------------------------
# R1 — success route returns validated text, no fallback
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_moto_canon_020_r1_validation_success_returns_validated():
    cerebro = _build_cerebro()

    with patch.object(cerebro, "_generate_with_retry_async", return_value=_valid_text()), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False):

        res = await cerebro.pensar_respuesta(
            "especificaciones de la TVS Apache RTR 160 4V",
            prospect_data={"exists": True, "nombre": "Mario", "phone": "+573192564289"},
        )

    assert "Ficha Tecnica: TVS Apache RTR 160 4V" in res
    assert "¡Qué pena!" not in res


# ---------------------------------------------------------------------------
# R2 — empty final_text with stash → fallback contains Ficha Tecnica: prefix
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_moto_canon_020_r2_empty_with_stash_gets_pcc_fallback():
    cerebro = _build_cerebro()

    with patch.object(cerebro, "_generate_with_retry_async", return_value=_empty_text()), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False):

        res = await cerebro.pensar_respuesta(
            "Hola, quisiera una moto doble propósito a crédito",
            prospect_data={
                "exists": True,
                "nombre": "Mario",
                "phone": "+573192564289",
                "_catalog_top_name": STASH_NAME,
                "_catalog_top_image": STASH_IMAGE,
            },
        )

    assert "Ficha Tecnica: Victory MRX 150" in res
    assert "⭐ Recomendación TOP: Victory MRX 150" in res
    assert STASH_IMAGE in res


# ---------------------------------------------------------------------------
# R3 — empty final_text without stash → honest empty_candidate copy, no exception
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_moto_canon_020_r3_empty_no_stash_returns_honest_copy():
    cerebro = _build_cerebro()

    with patch.object(cerebro, "_generate_with_retry_async", return_value=_empty_text()), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False):

        res = await cerebro.pensar_respuesta(
            "Hola, quisiera una moto",
            prospect_data={
                "exists": True,
                "nombre": "Mario",
                "phone": "+573192564289",
            },
        )

    assert isinstance(res, str) and len(res) > 0
    assert "¡Qué pena!" in res
    assert "Ficha Tecnica:" not in res


# ---------------------------------------------------------------------------
# R4 — non-compliant text + max attempts → fallback with prefix, NOT non-compliant text
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_moto_canon_020_r4_non_compliant_with_stash_returns_fallback():
    cerebro = _build_cerebro()
    calls = []

    async def _mock_generate(*args, **kwargs):
        calls.append(args)
        return _non_compliant_text()

    with patch.object(cerebro, "_generate_with_retry_async", side_effect=_mock_generate), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False):

        res = await cerebro.pensar_respuesta(
            "Hola, quisiera una moto doble propósito",
            prospect_data={
                "exists": True,
                "nombre": "Mario",
                "phone": "+573192564289",
                "_catalog_top_name": STASH_NAME,
                "_catalog_top_image": STASH_IMAGE,
            },
        )

    # After 3 non-compliant attempts, must route to fallback with prefix.
    assert "Ficha Tecnica: Victory MRX 150" in res
    assert "sin precio ni imagen" not in res
    assert len(calls) == 3


# ---------------------------------------------------------------------------
# R5 — max validation attempts exhausted → degrades via _build_pcc_fallback
#       (deadline exhaustion is covered by test_moto_canon_018_deadline_...)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_moto_canon_020_r5_max_attempts_degrades_with_prefix():
    """After 3 non-compliant generations exhaust max_validation_attempts, the
    outer loop must degrade via _build_pcc_fallback with Ficha Tecnica: prefix
    when stash is present — NOT return the (non-compliant) generated text."""
    cerebro = _build_cerebro()

    async def _mock_generate(*args, **kwargs):
        return _non_compliant_text()

    with patch.object(cerebro, "_generate_with_retry_async", side_effect=_mock_generate), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False):

        res = await cerebro.pensar_respuesta(
            "Hola, quisiera una moto doble propósito",
            prospect_data={
                "exists": True,
                "nombre": "Mario",
                "phone": "+573192564289",
                "_catalog_top_name": STASH_NAME,
                "_catalog_top_image": STASH_IMAGE,
            },
        )

    assert "Ficha Tecnica: Victory MRX 150" in res
    assert "sin precio ni imagen" not in res


# ---------------------------------------------------------------------------
# R6a — non-moto query with non-empty text passes _validate_output, no prefix
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_moto_canon_020_r6a_non_moto_passes_validate_output():
    cerebro = _build_cerebro()

    with patch.object(cerebro, "_generate_with_retry_async", return_value="¡Hola! ¿En qué puedo ayudarte?"), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False):

        res = await cerebro.pensar_respuesta(
            "Hola, ¿cómo estás?",
            prospect_data={
                "exists": True,
                "nombre": "Mario",
                "phone": "+573192564289",
            },
        )

    assert "¡Hola!" in res
    assert "Ficha Tecnica:" not in res
    assert "¡Qué pena!" not in res


# ---------------------------------------------------------------------------
# R6b — non-moto query with empty text routes to honest copy, no prefix
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_moto_canon_020_r6b_non_moto_empty_returns_honest():
    cerebro = _build_cerebro()

    with patch.object(cerebro, "_generate_with_retry_async", return_value=""), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False):

        res = await cerebro.pensar_respuesta(
            "Hola",
            prospect_data={
                "exists": True,
                "nombre": "Mario",
                "phone": "+573192564289",
            },
        )

    assert isinstance(res, str) and len(res) > 0
    assert "¡Qué pena!" in res
    assert "Ficha Tecnica:" not in res
