"""
Wave A pins — M4-PLAN-FINAL-INTEGRATION-001 (A1-A4).

Covers:
- A1: forensic logs (catalog JSON, PCC, egress, Meta payload).
- A2: deterministic Visual-Lock V1 in egress.
- A3: generic moto_interest canonicalization (T1 + T5).
- A4: guards PEI-3/T2 updated to real CatalogService.search_catalog str signature.
"""
import re
import unicodedata
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.routers.whatsapp import _ensure_visual_lock, _pipeline_egress
from app.services.memory_service import MemoryService

PHONE_E164 = "+573192564288"
PHONE_NUMBER_ID = "999999"
MOTO_VICTORY = "Victory MRX 150"
MOTO_NTORQ = "TVS NTorq 125"
MOTO_RAIDER = "TVS Raider 125"
MOTO_URL = "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos.appspot.com/o/moto.png?alt=media"


class _FakeCatalog:
    """Minimal catalog stand-in for unit tests (no Firestore)."""

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

    def search_catalog(self, query: str) -> str:
        return f"mock-catalog-markdown-for-{query}"


def _build_fake_catalog() -> _FakeCatalog:
    return _FakeCatalog([
        {"name": MOTO_VICTORY, "image_url": MOTO_URL, "price": "$8.500.000", "searchBy": ["doble proposito", "enduro"]},
        {"name": MOTO_NTORQ, "image_url": MOTO_URL, "price": "$7.200.000", "searchBy": ["automatica", "scooter"]},
        {"name": MOTO_RAIDER, "image_url": MOTO_URL, "price": "$9.000.000", "searchBy": ["sport"]},
    ])


def _build_memory_service(current_data: dict = None) -> MemoryService:
    ms = MemoryService.__new__(MemoryService)
    ms.collection_name = "prospectos"

    fake_snap = MagicMock()
    fake_snap.exists = True
    fake_snap.to_dict.return_value = current_data or {}

    async def _fake_io(coro, phone, label, timeout=None):
        if "doc_ref.set" in label:
            # Capture the merged payload for assertions.
            _fake_io.last_set = coro
            return MagicMock()
        return fake_snap

    ms._firestore_io = _fake_io
    ms._db = MagicMock()

    doc_ref = MagicMock()
    doc_ref.set = MagicMock(return_value=AsyncMock())
    ms.get_ref = AsyncMock(return_value=doc_ref)
    return ms


# -----------------------------------------------------------------------------
# A3 / T1: category query resolves to canonical model via catalog_moto_hint
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_moto_interest_category_resolves_to_canonical_model():
    """T1: 'doble propósito' extraction overridden by tool hint 'Victory MRX 150'."""
    ms = _build_memory_service()
    catalog = _build_fake_catalog()

    await ms.update_prospect_summary(
        PHONE_E164,
        "",
        {"moto_interest": "doble propósito"},
        catalog_moto_hint=MOTO_VICTORY,
        catalog=catalog,
    )

    # The coro is doc_ref.set(update_payload, merge=True); unwrap MagicMock call.
    update_payload = ms.get_ref.return_value.set.call_args.args[0]
    assert update_payload.get("moto_interest") == MOTO_VICTORY
    assert update_payload.get("moto_interes") == MOTO_VICTORY


# -----------------------------------------------------------------------------
# A3 / T5: generic cases
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_moto_interest_generic_canonicalization_cases():
    """T5: automatica→NTorq, canonical preserved, no-match conservative."""
    ms = _build_memory_service()
    catalog = _build_fake_catalog()

    # Case 1: category 'automatica' resolves to NTorq via hint.
    await ms.update_prospect_summary(
        PHONE_E164, "", {"moto_interest": "automatica"},
        catalog_moto_hint=MOTO_NTORQ, catalog=catalog,
    )
    payload1 = ms.get_ref.return_value.set.call_args.args[0]
    assert payload1["moto_interest"] == MOTO_NTORQ

    # Case 2: already-canonical value is left untouched when no hint.
    ms2 = _build_memory_service(current_data={"moto_interest": MOTO_VICTORY})
    await ms2.update_prospect_summary(
        PHONE_E164, "", {"moto_interest": MOTO_VICTORY}, catalog=catalog,
    )
    payload2 = ms2.get_ref.return_value.set.call_args.args[0]
    assert payload2["moto_interest"] == MOTO_VICTORY

    # Case 3: non-canonical extracted value with no hint and empty DB is persisted conservatively.
    ms3 = _build_memory_service()
    await ms3.update_prospect_summary(
        PHONE_E164, "", {"moto_interest": "algo raro"}, catalog=catalog,
    )
    payload3 = ms3.get_ref.return_value.set.call_args.args[0]
    assert payload3["moto_interest"] == "algo raro"


# -----------------------------------------------------------------------------
# A2: deterministic Visual-Lock V1
# -----------------------------------------------------------------------------
def test_ensure_visual_lock_finds_image_when_markdown_missing():
    catalog = _build_fake_catalog()
    text = f"La {MOTO_VICTORY} cuesta $8.500.000. ¿Te interesa?"
    result = _ensure_visual_lock(text, {"moto_interest": MOTO_VICTORY}, catalog)
    assert result is not None
    assert result[0] == MOTO_URL
    assert result[1] == MOTO_VICTORY


def test_ensure_visual_lock_returns_none_when_markdown_present():
    catalog = _build_fake_catalog()
    text = f"La {MOTO_VICTORY} cuesta $8.500.000. ![{MOTO_VICTORY}]({MOTO_URL})"
    result = _ensure_visual_lock(text, {"moto_interest": MOTO_VICTORY}, catalog)
    assert result is None


@pytest.mark.asyncio
async def test_pipeline_egress_v1_injects_image_when_no_markdown():
    """V1: response has price + canonical moto but no Markdown → Strategy A."""
    catalog = _build_fake_catalog()
    mock_ms = MagicMock()
    mock_ms.save_message = AsyncMock()
    mock_image_sender = AsyncMock(return_value=True)
    mock_unified = AsyncMock(return_value=True)

    response_text = f"Te recomiendo la {MOTO_VICTORY} por $8.500.000. ¿Te gusta?"

    with patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp._send_whatsapp_image", mock_image_sender), \
         patch("app.routers.whatsapp._process_and_send_egress_message", mock_unified):
        await _pipeline_egress(
            response_text,
            user_phone=PHONE_E164,
            phone_number_id=PHONE_NUMBER_ID,
            prospect_data={"moto_interest": MOTO_VICTORY},
            catalog=catalog,
        )

    mock_image_sender.assert_awaited_once()
    args = mock_image_sender.await_args
    assert args.args[0] == PHONE_E164
    assert args.args[1] == MOTO_URL
    assert MOTO_VICTORY in args.kwargs["caption"]
    assert "$8.500.000" in args.kwargs["caption"]
    mock_unified.assert_not_called()
    mock_ms.save_message.assert_awaited_once_with(PHONE_E164, "model", response_text)


@pytest.mark.asyncio
async def test_pipeline_egress_v1_bypasses_when_markdown_present():
    """V1 must NOT double-send if the LLM already included Markdown."""
    catalog = _build_fake_catalog()
    mock_ms = MagicMock()
    mock_ms.save_message = AsyncMock()
    mock_image_sender = AsyncMock(return_value=True)
    mock_unified = AsyncMock(return_value=True)

    response_text = f"Te recomiendo la {MOTO_VICTORY} por $8.500.000. ![{MOTO_VICTORY}]({MOTO_URL})"

    with patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp._send_whatsapp_image", mock_image_sender), \
         patch("app.routers.whatsapp._process_and_send_egress_message", mock_unified):
        await _pipeline_egress(
            response_text,
            user_phone=PHONE_E164,
            phone_number_id=PHONE_NUMBER_ID,
            prospect_data={"moto_interest": MOTO_VICTORY},
            catalog=catalog,
        )

    mock_image_sender.assert_not_called()
    mock_unified.assert_awaited_once()


# -----------------------------------------------------------------------------
# A1: forensic logs
# -----------------------------------------------------------------------------
def test_catalog_forensic_log_emits_image_url(caplog):
    import logging
    from unittest.mock import patch
    from app.services.catalog_service import CatalogService

    catalog = CatalogService()
    catalog._items = [
        {
            "id": "victory-mrx-150",
            "name": MOTO_VICTORY,
            "price": 8500000,
            "cc": 150,
            "category": "Urban",
            "searchBy": ["doble proposito"],
            "search_tokens": ["victory", "mrx", "150"],
            "search_text": "victory mrx 150 doble proposito",
            "description": "",
            "image_url": MOTO_URL,
            "bonusAmount": 0,
            "bonusEndDate": None,
        }
    ]
    catalog._category_aliases = {}
    catalog._class_category_aliases = {}

    caplog.set_level(logging.INFO, logger="app.services.catalog_service")
    with patch("app.services.config_service.config_service") as mock_cfg:
        mock_cfg.get_registration_cost.return_value = 0
        catalog.search_items(MOTO_VICTORY, trace_id="turn-123")
    assert any("📦 [CATALOG-FORENSIC]" in r.message for r in caplog.records)
    assert any("Victory MRX 150" in r.message and MOTO_URL in r.message for r in caplog.records)


def test_pcc_forensic_log_emits_with_trace_id(caplog):
    from app.services.agentic_loop_service import AgenticOrchestrator
    orch = AgenticOrchestrator()
    with caplog.at_level("INFO"):
        orch.run_checker(
            "La Victory MRX 150 cuesta $8.500.000",
            is_catalog_query=True,
            prospect_data={"phone": PHONE_E164, "moto_interest": MOTO_VICTORY},
            user_prompt="doble propósito",
            trace_id="turn-123",
        )
    assert any("🔍 [PCC-FORENSIC]" in r.message and "turn-123" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_meta_payload_log_emits_info(caplog):
    from app.services.whatsapp_service import WhatsAppService

    service = WhatsAppService.__new__(WhatsAppService)
    service.phone_number_id = PHONE_NUMBER_ID
    service.headers = {"Authorization": "Bearer test"}

    class _FakeResponse:
        status_code = 200
        def json(self):
            return {"messages": [{"id": "wamid.test"}]}
        def raise_for_status(self):
            return None

    class _FakeClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False
        async def post(self, url, headers=None, json=None, timeout=None):
            return _FakeResponse()

    with caplog.at_level("INFO"), patch("app.services.whatsapp_service.httpx.AsyncClient", return_value=_FakeClient()):
        await service.send_image_message(PHONE_E164, MOTO_URL, caption="Mira", phone_number_id=PHONE_NUMBER_ID)

    assert any("📤 [META-PAYLOAD]" in r.message and "phone_number_id" in r.message for r in caplog.records)
    assert any("✅ [META-PAYLOAD]" in r.message and "wamid.test" in r.message for r in caplog.records)
