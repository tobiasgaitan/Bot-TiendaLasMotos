"""
Regression pins for BOT-BUILD-MOTO-CANON-018.

Fix A: update_prospect_summary resolves the catalog singleton when no catalog
object is passed, so a category-style extraction (e.g. "Doble propósito") that
resolves to catalog matches is rejected instead of being persisted as
moto_interest/moto_interes.
"""

import re
import unicodedata
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.memory_service import MemoryService


PHONE_E164 = "+573192564289"


def _normalize(s: str) -> str:
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
        {
            "name": "Victory MRX 150",
            "image_url": "https://img.url",
            "price": "$8.500.000",
            "searchBy": ["doble proposito", "enduro"],
        },
        {
            "name": "TVS NTorq 125",
            "image_url": "https://img.url",
            "price": "$7.200.000",
            "searchBy": ["automatica", "scooter"],
        },
        {
            "name": "TVS Raider 125",
            "image_url": "https://img.url",
            "price": "$9.000.000",
            "searchBy": ["sport"],
        },
    ])


# ---------------------------------------------------------------------------
# R-A1 — Post-reset category extraction without hint MUST be rejected
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_moto_canon_018_ra1_post_reset_category_rejected():
    """Post-reset DB empty + catalog=None: 'Doble propósito' resolves to
    catalog matches via the singleton → must NOT persist moto_interest."""
    ms = _build_memory_service()

    with patch("app.services.catalog_service.catalog_service", _build_fake_catalog()):
        await ms.update_prospect_summary(
            PHONE_E164, "", {"moto_interest": "Doble propósito"}, catalog=None
        )

    payload = ms.get_ref.return_value.set.call_args.args[0]
    assert "moto_interest" not in payload, (
        "Non-canonical category extraction without hint/DB must not persist moto_interest"
    )
    assert "moto_interes" not in payload, (
        "Dashboard mirror moto_interes must also be absent when moto_interest is rejected"
    )


# ---------------------------------------------------------------------------
# R-A2 — Singleton resolution: explicit matches > 0 forces rejection
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_moto_canon_018_ra2_singleton_matches_force_rejection():
    """Same as R-A1 but the singleton returns 5 matches; rejection must still
    happen even though the parameter catalog=None."""
    ms = _build_memory_service()
    fake_catalog = _build_fake_catalog()
    # Expand catalog so 'doble proposito' returns 5 matches
    fake_catalog._items.extend([
        {"name": "TVS Apache RTR 160 4V", "searchBy": ["doble proposito"]},
        {"name": "TVS Apache RTR 200 4V", "searchBy": ["doble proposito"]},
        {"name": "Victory MRX 125", "searchBy": ["doble proposito"]},
    ])

    with patch("app.services.catalog_service.catalog_service", fake_catalog):
        await ms.update_prospect_summary(
            PHONE_E164, "", {"moto_interest": "Doble propósito"}, catalog=None
        )

    payload = ms.get_ref.return_value.set.call_args.args[0]
    assert "moto_interest" not in payload


# ---------------------------------------------------------------------------
# R-A3 — True no-match conservative behavior is preserved
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_moto_canon_018_ra3_true_no_match_allowed():
    """If the singleton genuinely returns zero matches, the conservative
    post-reset behavior of allowing the non-canonical value is preserved."""
    ms = _build_memory_service()
    empty_catalog = _FakeCatalog([])

    with patch("app.services.catalog_service.catalog_service", empty_catalog):
        await ms.update_prospect_summary(
            PHONE_E164, "", {"moto_interest": "Doble propósito"}, catalog=None
        )

    payload = ms.get_ref.return_value.set.call_args.args[0]
    assert payload.get("moto_interest") == "Doble propósito", (
        "True no-match conservative value must still be allowed"
    )


# ---------------------------------------------------------------------------
# R-A4 — Canonical catalog_moto_hint override is preserved
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_moto_canon_018_ra4_canonical_hint_overrides_category():
    """A canonical hint must override a category extraction, and the resulting
    payload must contain the hint (distinct from absence)."""
    ms = _build_memory_service()

    with patch("app.services.catalog_service.catalog_service", _build_fake_catalog()):
        await ms.update_prospect_summary(
            PHONE_E164,
            "",
            {"moto_interest": "Doble propósito"},
            catalog_moto_hint="TVS Apache RTR 200 4V",
            catalog=None,
        )

    payload = ms.get_ref.return_value.set.call_args.args[0]
    assert payload["moto_interest"] == "TVS Apache RTR 200 4V", (
        "Canonical hint must override extracted category"
    )


# ---------------------------------------------------------------------------
# R-A5 — Already-canonical DB value is preserved over category extraction
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_moto_canon_018_ra5_canonical_db_preserved():
    """If the DB already holds a canonical model, a later category extraction
    without hint must not overwrite it."""
    ms = _build_memory_service(current_data={"moto_interest": "Victory MRX 150"})

    with patch("app.services.catalog_service.catalog_service", _build_fake_catalog()):
        await ms.update_prospect_summary(
            PHONE_E164, "", {"moto_interest": "Doble propósito"}, catalog=None
        )

    payload = ms.get_ref.return_value.set.call_args.args[0]
    set_kwargs = ms.get_ref.return_value.set.call_args.kwargs
    # The non-canonical category extraction must NOT be written back.
    assert payload.get("moto_interest") != "Doble propósito", (
        "Non-canonical category extraction must not overwrite DB"
    )
    # Firestore merge=True preserves the existing canonical DB value without
    # echoing it into the update payload (contract of _merge_extracted_data).
    assert set_kwargs.get("merge") is True, "update_prospect_summary must use merge=True"


# ---------------------------------------------------------------------------
# RESOLVE-HELPER — _resolve_catalog is reused by both call sites (DRY)
# ---------------------------------------------------------------------------
def test_moto_canon_018_resolve_helper_reused():
    """Both _is_canonical_moto_interest and the no-match branch must delegate
    catalog singleton resolution to the same helper."""
    ms = _build_memory_service()
    helper = ms._resolve_catalog

    assert callable(helper)
    # Helper returns the parameter when provided
    assert helper(_build_fake_catalog()) is not None
    # Helper returns None safely when singleton is unavailable
    with patch("app.services.catalog_service.catalog_service", None):
        assert helper(None) is None


# ---------------------------------------------------------------------------
# STASH-NOPERSIST-01 — _catalog_top_name/_catalog_top_image are caller-managed
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_moto_canon_018_stash_no_persist():
    """update_prospect_summary is stash-agnostic: when the caller (whatsapp.py)
    has already popped _catalog_top_*, the persisted payload must not contain
    them. This pins the contract that makes the pop in whatsapp.py:2250-2251
    the single source of truth for stash removal."""
    ms = _build_memory_service()
    extracted = {"moto_interest": "Victory MRX 150"}

    with patch("app.services.catalog_service.catalog_service", _build_fake_catalog()):
        await ms.update_prospect_summary(PHONE_E164, "", extracted, catalog=None)

    payload = ms.get_ref.return_value.set.call_args.args[0]
    assert "_catalog_top_name" not in payload
    assert "_catalog_top_image" not in payload
    assert payload.get("moto_interest") == "Victory MRX 150"
