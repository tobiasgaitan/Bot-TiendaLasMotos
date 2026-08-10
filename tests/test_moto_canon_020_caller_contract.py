"""
Caller-contract regression pins for C-20e.

Freezes the current behavior of the four whatsapp.py callers that invoke
update_prospect_summary WITHOUT passing catalog=. Post Fix A, every such
caller now resolves the catalog singleton, which means non-canonical
moto_interest values that fuzzy-match catalog items are silently dropped.
These pins freeze the behavior as the "decisión vigente" while C-21
(post-F5) evaluates persisting raw interest with a canonical=False flag.
"""

import unicodedata
import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.memory_service import MemoryService


PHONE_E164 = "+573192564289"


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
        def _strip_diacritics(s: str) -> str:
            return "".join(
                c for c in unicodedata.normalize("NFD", s.lower())
                if unicodedata.category(c) != "Mn"
            )
        q = _strip_diacritics(query)
        matches = []
        for item in self._items:
            name = _strip_diacritics(str(item.get("name", "")))
            tags = [_strip_diacritics(str(t)) for t in item.get("searchBy", [])]
            if q in name or any(q in t for t in tags):
                matches.append(item)
        return matches


def _build_fake_catalog() -> _FakeCatalog:
    return _FakeCatalog([
        {"name": "TVS Raider 125", "searchBy": ["raider", "urbana"]},
        {"name": "Victory MRX 150", "searchBy": ["doble proposito", "enduro"]},
    ])


# ---------------------------------------------------------------------------
# CE-01 — caller 697 (ponytail_status only): no moto_interest in payload
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_moto_canon_020_ce01_caller_697_no_moto_key():
    """Ponytail deprioritization does not write moto_interest."""
    ms = _build_memory_service()

    with patch("app.services.catalog_service.catalog_service", _build_fake_catalog()):
        await ms.update_prospect_summary(
            PHONE_E164, "", {"ponytail_status": "DEPRIORITIZED"}, catalog=None
        )

    payload = ms.get_ref.return_value.set.call_args.args[0]
    assert "moto_interest" not in payload
    assert payload.get("ponytail_status") == "DEPRIORITIZED"


# ---------------------------------------------------------------------------
# CE-02 — caller 1270 (doc urls): no moto_interest in payload
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_moto_canon_020_ce02_caller_1270_no_moto_key():
    """Document URL persistence does not write moto_interest."""
    ms = _build_memory_service()

    with patch("app.services.catalog_service.catalog_service", _build_fake_catalog()):
        await ms.update_prospect_summary(
            PHONE_E164, "", {
                "doc_cedula_url": "https://storage/tmp/cedula.jpg",
                "doc_cedula": True,
            }, catalog=None
        )

    payload = ms.get_ref.return_value.set.call_args.args[0]
    assert "moto_interest" not in payload


# ---------------------------------------------------------------------------
# CE-03 — caller 1873 (habeas + ponytail): no moto_interest in payload
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_moto_canon_020_ce03_caller_1873_no_moto_key():
    """Habeas data reaction acceptance does not write moto_interest."""
    ms = _build_memory_service()

    with patch("app.services.catalog_service.catalog_service", _build_fake_catalog()):
        await ms.update_prospect_summary(
            PHONE_E164, "", {
                "habeas_data_accepted": True,
                "ponytail_status": "PENDING",
            }, catalog=None
        )

    payload = ms.get_ref.return_value.set.call_args.args[0]
    assert "moto_interest" not in payload


# ---------------------------------------------------------------------------
# CE-04 — caller 1418 (vision): category match → moto_interest rejected (congelado)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_moto_canon_020_ce04_vision_category_match_rejected():
    """Post-reset vision path: 'Doble propósito' matching catalog items is
    rejected from moto_interest (current behavior frozen by Fix A)."""
    ms = _build_memory_service(current_data={"ponytail_status": "UNINITIATED"})

    with patch("app.services.catalog_service.catalog_service", _build_fake_catalog()):
        await ms.update_prospect_summary(
            PHONE_E164, "", {
                "moto_interest": "Doble propósito",
                "ponytail_status": "PENDING",
            }, catalog=None
        )

    payload = ms.get_ref.return_value.set.call_args.args[0]
    assert payload.get("moto_interest") != "Doble propósito", (
        "Category-style extraction matching catalog items must be rejected"
    )
    assert "moto_interest" not in payload


# ---------------------------------------------------------------------------
# CE-05 — partial model "TVS Raider" (substring of catalog name) → rejected
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_moto_canon_020_ce05_partial_model_match_rejected():
    """A non-canonical extraction that is a substring of a catalog name
    (e.g. 'TVS Raider' ⊂ 'TVS Raider 125') is rejected."""
    ms = _build_memory_service()

    with patch("app.services.catalog_service.catalog_service", _build_fake_catalog()):
        await ms.update_prospect_summary(
            PHONE_E164, "", {"moto_interest": "TVS Raider"}, catalog=None
        )

    payload = ms.get_ref.return_value.set.call_args.args[0]
    assert "moto_interest" not in payload


# ---------------------------------------------------------------------------
# CE-06 — no-match control: "Raider 150" (no substring match) → allowed
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_moto_canon_020_ce06_no_match_control_allowed():
    """A value with no catalog match is still allowed (conservative behavior)."""
    ms = _build_memory_service()

    with patch("app.services.catalog_service.catalog_service", _build_fake_catalog()):
        await ms.update_prospect_summary(
            PHONE_E164, "", {"moto_interest": "Raider 150"}, catalog=None
        )

    payload = ms.get_ref.return_value.set.call_args.args[0]
    assert payload.get("moto_interest") == "Raider 150"
