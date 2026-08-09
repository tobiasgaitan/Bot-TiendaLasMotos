"""
Regression pins for BOT-BUILD-DRIFT-CANON-016.
Covers Fixes A (drift-interceptor diacritics + re-injection),
B (M2 canonical gate), C (PCC bypass_strict formula) and D (honest fallback).
"""
import re
import unicodedata
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai_brain import CerebroIA
from app.services.agentic_loop_service import AgenticOrchestrator
from app.services.memory_service import MemoryService


PHONE_E164 = "+573192564288"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _norm(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s.lower().strip())
        if unicodedata.category(c) != "Mn"
    )


def _build_memory_service(current_data: dict = None) -> MemoryService:
    ms = MemoryService.__new__(MemoryService)
    ms.collection_name = "prospectos"

    fake_snap = MagicMock()
    fake_snap.exists = True
    fake_snap.to_dict.return_value = current_data or {}

    async def _fake_io(coro, phone, label, timeout=None):
        if "doc_ref.set" in label:
            _fake_io.last_set = coro
            return MagicMock()
        return fake_snap

    ms._firestore_io = _fake_io
    ms._db = MagicMock()

    doc_ref = MagicMock()
    doc_ref.set = MagicMock(return_value=AsyncMock())
    ms.get_ref = AsyncMock(return_value=doc_ref)
    return ms


class _FakeCatalog:
    def __init__(self, items):
        self._items = items

    @staticmethod
    def _normalize_item_id_key(raw: str) -> str:
        if not raw or not isinstance(raw, str):
            return ""
        s = unicodedata.normalize("NFKC", raw).lower().strip()
        s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
        s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
        return s

    def search_items(self, query: str, trace_id: str = None):
        q = query.lower()
        matches = []
        for item in self._items:
            name = str(item.get("name", "")).lower()
            tags = [str(t).lower() for t in item.get("searchBy", [])]
            if q in name or any(q in t for t in tags):
                matches.append(item)
        return matches[:3]

    def get_catalog_aliases(self):
        return {"enduro": ["enduro", "trocha", "campo", "doble proposito"]}


def _build_fake_catalog() -> _FakeCatalog:
    return _FakeCatalog([
        {"name": "Victory MRX 150", "image_url": "https://img.url", "price": "$8.500.000", "searchBy": ["doble proposito", "enduro"]},
        {"name": "TVS NTorq 125", "image_url": "https://img.url", "price": "$7.200.000", "searchBy": ["automatica", "scooter"]},
        {"name": "TVS Raider 125", "image_url": "https://img.url", "price": "$9.000.000", "searchBy": ["sport"]},
    ])


# ---------------------------------------------------------------------------
# R-H1 — Drift interceptor diacritics + deterministic re-injection
# ---------------------------------------------------------------------------
def test_rh1a_is_synonym_or_model_match_strips_diacritics_on_moto_interest():
    """doble propósito (accented, extracted) must match the unaccented catalog alias."""
    catalog = _build_fake_catalog()
    cerebro = CerebroIA(catalog_service=catalog)
    aliases = catalog.get_catalog_aliases()

    assert cerebro._is_synonym_or_model_match("enduro", "doble propósito", aliases), (
        "enduro must be a synonym of doble propósito after diacritic normalization"
    )


@pytest.mark.asyncio
async def test_rh1b_interceptor_reinjects_canonical_protected_term():
    """When drift-blocked, a CANONICAL protected term triggers deterministic re-injection."""
    catalog = _build_fake_catalog()
    cerebro = CerebroIA(catalog_service=catalog)

    prospect_data = {"exists": True, "moto_interest": "Victory MRX 150", "nombre": "Test"}

    with patch.object(cerebro, "_call_gemini_with_retry_async", new_callable=AsyncMock) as mocked_call:
        # Turn 1: LLM attempts a drift query blocked by ratio.
        fc1 = MagicMock()
        fc1.name = "search_catalog"
        fc1.args = {"query": "xyz123"}
        part1 = MagicMock(function_call=fc1, text=None)
        response1 = MagicMock(candidates=[MagicMock(content=MagicMock(parts=[part1]))])

        # Turn 2: final text after re-injected catalog results.
        part2 = MagicMock(function_call=None, text="Recomendación final")
        response2 = MagicMock(candidates=[MagicMock(content=MagicMock(parts=[part2]))])

        mocked_call.side_effect = [response1, response2]

        with patch.object(catalog, "search_items", wraps=catalog.search_items) as search_spy:
            await cerebro.pensar_respuesta("info de la moto fantasma", prospect_data=prospect_data)

            # Re-injected query must be the canonical protected term.
            calls = [c.args[0] for c in search_spy.call_args_list]
            assert any(c == "Victory MRX 150" for c in calls), (
                f"Expected re-injection of canonical protected term, got {calls}"
            )


# ---------------------------------------------------------------------------
# R-H2 — M2 canonical gate
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_rh2a_reject_noncanonical_category_extraction_post_reset():
    """Post-reset DB empty: a category-style extraction without hint must be rejected."""
    ms = _build_memory_service()
    catalog = _build_fake_catalog()

    await ms.update_prospect_summary(
        PHONE_E164, "", {"moto_interest": "doble proposito"}, catalog=catalog
    )
    payload = ms.get_ref.return_value.set.call_args.args[0]
    assert "moto_interest" not in payload, (
        "Non-canonical category extraction without hint/DB must not be persisted"
    )


@pytest.mark.asyncio
async def test_rh2b_canonical_hint_overrides_category_extraction():
    """A canonical catalog_moto_hint must override a category extraction."""
    ms = _build_memory_service()
    catalog = _build_fake_catalog()

    await ms.update_prospect_summary(
        PHONE_E164,
        "",
        {"moto_interest": "doble propósito"},
        catalog_moto_hint="Victory MRX 150",
        catalog=catalog,
    )
    payload = ms.get_ref.return_value.set.call_args.args[0]
    assert payload["moto_interest"] == "Victory MRX 150"


# ---------------------------------------------------------------------------
# R-H3 — PCC bypass_strict truth table
# ---------------------------------------------------------------------------
def _run_checker(bot_response: str, is_catalog_query: bool, prospect_data: dict, user_prompt: str):
    orchestrator = AgenticOrchestrator()
    return orchestrator.run_checker(
        bot_response,
        is_catalog_query=is_catalog_query,
        prospect_data=prospect_data,
        user_prompt=user_prompt,
    )


def test_rh3_1_purchase_intent_vetoes_bypass_even_with_general_faq():
    """Fila 1: compra × canónico × FAQ general → bypass False."""
    result = _run_checker(
        "Nuestro horario es de lunes a sábado.",
        is_catalog_query=False,
        prospect_data={"moto_interest": "Victory MRX 125"},
        user_prompt="quiero comprar una moto, cual es el horario?",
    )
    assert result.get("bypass_strict") is not True


def test_rh3_2_purchase_intent_category_cold_start():
    """Fila 2: compra × categoría → bypass False."""
    result = _run_checker(
        "¡Hola! Qué gusto saludarte...",
        is_catalog_query=False,
        prospect_data={},
        user_prompt="Hola, quisiera una moto doble propósito a crédito",
    )
    assert result.get("bypass_strict") is not True


def test_rh3_3_credit_faq_abstract_with_canonical_moto():
    """Fila 3: FAQ abstracta × canónico → bypass True (PINs 1588-1696)."""
    result = _run_checker(
        "Los requisitos son cédula y recibos.",
        is_catalog_query=True,
        prospect_data={"moto_interest": "Apache 160"},
        user_prompt="ok, y si la quiero sacar a credito, cuales son los requisitos?",
    )
    assert result.get("bypass_strict") is True


def test_rh3_4_credit_faq_abstract_with_category_moto():
    """Fila 4: FAQ abstracta × categoría → bypass True."""
    result = _run_checker(
        "Necesitas cédula y buen historial.",
        is_catalog_query=False,
        prospect_data={"moto_interest": "doble propósito"},
        user_prompt="estoy reportado, puedo sacar credito?",
    )
    assert result.get("bypass_strict") is True


def test_rh3_5_chitchat_without_moto():
    """Fila 5: chit-chat sin moto → bypass True."""
    result = _run_checker(
        "¡Hola! En qué puedo ayudarte?",
        is_catalog_query=False,
        prospect_data={},
        user_prompt="hola",
    )
    assert result.get("bypass_strict") is True


def test_rh3_6_catalog_query_category_noncanonical_no_purchase():
    """Fila 6: consulta catálogo × categoría no canónica, sin compra/FAQ → bypass False."""
    result = _run_checker(
        "Tenemos varias opciones.",
        is_catalog_query=True,
        prospect_data={"moto_interest": "doble propósito"},
        user_prompt="moto doble propósito",
    )
    assert result.get("bypass_strict") is not True


def test_rh3_7_catalog_query_canonical_no_purchase():
    """Fila 7: consulta catálogo × canónico, sin compra/FAQ → bypass False."""
    result = _run_checker(
        "La Victory MRX 125 cuesta $8.500.000.",
        is_catalog_query=True,
        prospect_data={"moto_interest": "Victory MRX 125"},
        user_prompt="Victory MRX 125",
    )
    assert result.get("bypass_strict") is not True


def test_rh3_8_general_faq_with_canonical_moto():
    """Fila 8: FAQ general × canónico → bypass True."""
    result = _run_checker(
        "Abrimos de lunes a sábado.",
        is_catalog_query=False,
        prospect_data={"moto_interest": "Victory MRX 125"},
        user_prompt="cual es el horario?",
    )
    assert result.get("bypass_strict") is True


# ---------------------------------------------------------------------------
# R-H4 — Honest fallback copy
# ---------------------------------------------------------------------------
def test_rh4_fallback_copy_is_honest():
    cerebro = CerebroIA()

    empty = cerebro._fallback_response("query", reason="empty_candidate")
    assert "no me cargó tu mensaje" not in empty
    assert "inconveniente procesando esa búsqueda" in empty

    interceptor = cerebro._fallback_response("query", reason="interceptor_block")
    assert "no me cargó tu mensaje" not in interceptor
    assert "concretarla" in interceptor

    system = cerebro._fallback_response("query", reason="system_error")
    assert "no me cargó tu mensaje" not in system
    assert "Se me quedó colgado el sistema" in system


@pytest.mark.asyncio
async def test_rh4_tool_loop_fallback_copy_is_honest():
    """
    [BOT-BUILD-PCC-LOOP-017 / PIN-4] El path degradado del tool-loop
    (ai_brain.py:3027) debe invocar _fallback_response con reason='empty_candidate'
    cuando hay resultados de catálogo, y debe anexar el Top Result (nombre + precio + imagen).
    """
    catalog = _build_fake_catalog()
    cerebro = CerebroIA(catalog_service=catalog)
    cerebro.client = MagicMock()

    async def mock_call_gemini(*args, **kwargs):
        fc = MagicMock()
        fc.name = "search_catalog"
        fc.args = {"query": "doble proposito"}
        part = MagicMock(function_call=fc, text=None)
        return MagicMock(candidates=[MagicMock(content=MagicMock(parts=[part]))])

    with patch.object(cerebro, "_call_gemini_with_retry_async", side_effect=mock_call_gemini), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True):

        res = await cerebro._generate_with_retry_async(
            "doble proposito",
            context="",
            prospect_data={"exists": True, "nombre": "Test"},
            history=[],
        )

    assert "Se me quedó colgado el sistema" not in res
    assert "inconveniente procesando esa búsqueda" in res
    assert "Victory MRX 150" in res
    assert "$8.500.000" in res
