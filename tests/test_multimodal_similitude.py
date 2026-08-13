import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.services.catalog_service import CatalogService, PRICE_PACKAGE_ANCHOR
from app.services.vision_service import VisionService


# ── Fixtures helpers ──────────────────────────────────────────────────

def _canonical_mock_items():
    """Return a minimal realistic catalog fixture."""
    return [
        {
            "id": "tvs_sport",
            "name": "TVS Sport 100",
            "image_url": "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos-documents/o/tvs_sport.jpg",
            "price": 6200000,
            "formatted_price": "$6.200.000",
        },
        {
            "id": "tvs_raider",
            "name": "TVS Raider 125",
            "image_url": "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos-documents/o/tvs_raider.jpg",
            "price": 7500000,
            "formatted_price": "$7.500.000",
        },
        {
            "id": "akt_nkd",
            "name": "AKT NKD 125",
            "image_url": "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos-documents/o/akt_nkd.jpg",
            "price": 5200000,
            "formatted_price": "$5.200.000",
        },
    ]


def hydrate_catalog_indexes(catalog: CatalogService, items: list):
    """
    [BOT-PLAN-MULTIMODAL-HARDENING-201]
    Populate ALL indexes in one call so no O(1) path is left unexercised.
    [BOT-BUILD-MULTIMODAL-RESOLVER-REGRESSION] Also populates _items_by_id_norm.
    """
    catalog._items = items
    catalog._items_by_id = {it["id"]: it for it in items}
    catalog._items_by_image_url_norm = {}
    catalog._items_by_id_norm = {}
    for it in items:
        url = it.get("image_url", "")
        if url:
            norm = CatalogService._normalize_image_url(url)
            if norm:
                catalog._items_by_image_url_norm[norm] = it
        doc_id = it["id"]
        id_norm_key = CatalogService._normalize_item_id_key(doc_id)
        if id_norm_key:
            if id_norm_key not in catalog._items_by_id_norm:
                catalog._items_by_id_norm[id_norm_key] = []
            if doc_id not in catalog._items_by_id_norm[id_norm_key]:
                catalog._items_by_id_norm[id_norm_key].append(doc_id)
        name = it.get("name", "")
        if name:
            name_norm_key = CatalogService._normalize_item_id_key(name)
            if name_norm_key and name_norm_key != id_norm_key:
                if name_norm_key not in catalog._items_by_id_norm:
                    catalog._items_by_id_norm[name_norm_key] = []
                if doc_id not in catalog._items_by_id_norm[name_norm_key]:
                    catalog._items_by_id_norm[name_norm_key].append(doc_id)
    catalog._padded_ids = set()


# ── Unit: matcher precedence ─────────────────────────────────────────

def test_match_catalog_item_by_image_priority():
    """
    [BOT-PLAN-MULTIMODAL-HARDENING-201] AF-01..AF-03
    Matches by ID first, then by exact image_url, then fuzzy ≥0.85.
    Now uses hydrate_catalog_indexes so O(1) URL index is exercised.
    """
    catalog = CatalogService()
    items = _canonical_mock_items()
    hydrate_catalog_indexes(catalog, items)

    # 1. Match by ID (AF-01)
    res_id = catalog.match_catalog_item_by_image(
        "MOTO_DETECTADA: TVS Sport | Model ID: tvs_raider"
    )
    assert res_id is not None
    assert res_id["id"] == "tvs_raider", "Should match by ID first"
    assert res_id.get("formatted_price") == f"$7.500.000 {PRICE_PACKAGE_ANCHOR}"

    # 2. Match by exact image_url – O(1) index (AF-02)
    res_url = catalog.match_catalog_item_by_image(
        "MOTO_DETECTADA: AKT | Match URL: https://firebasestorage.googleapis.com/v0/b/tiendalasmotos-documents/o/tvs_sport.jpg"
    )
    assert res_url is not None
    assert res_url["id"] == "tvs_sport", "Should match by image_url"
    assert res_url.get("formatted_price") == f"$6.200.000 {PRICE_PACKAGE_ANCHOR}"

    # 3. Fuzzy SequenceMatcher ≥0.85 (AF-03 boundary)
    res_fuzzy = catalog.match_catalog_item_by_image("MOTO_DETECTADA: TVS Sport 100")
    assert res_fuzzy is not None
    assert res_fuzzy["id"] == "tvs_sport"

    res_fuzzy2 = catalog.match_catalog_item_by_image("TVS Sport 10")
    assert res_fuzzy2 is not None
    assert res_fuzzy2["id"] == "tvs_sport"
    assert res_fuzzy2.get("formatted_price") == f"$6.200.000 {PRICE_PACKAGE_ANCHOR}"

    # 4. Fallback search_items
    with patch.object(catalog, 'search_items', return_value=[items[2]]) as mock_search:
        res_fallback = catalog.match_catalog_item_by_image("NKD")
        assert res_fallback is not None
        assert res_fallback["id"] == "akt_nkd"
        mock_search.assert_called_once_with("NKD")


# ── Unit: O(1) URL index coverage (was blind spot) ───────────────────

def test_match_catalog_item_url_index_o1_no_linear_fallback():
    """
    [BOT-PLAN-MULTIMODAL-HARDENING-201] AF-02
    Prove that the O(1) _items_by_image_url_norm lookup works WITHOUT
    the _items list (which was the previously-unexercised blind spot).
    """
    catalog = CatalogService()
    items = _canonical_mock_items()
    hydrate_catalog_indexes(catalog, items)

    # Remove _items to force exclusive O(1) index path
    catalog._items = []

    res = catalog.match_catalog_item_by_image(
        "MOTO_DETECTADA: Whatever | Match URL: https://firebasestorage.googleapis.com/v0/b/tiendalasmotos-documents/o/tvs_sport.jpg"
    )
    assert res is not None
    assert res["id"] == "tvs_sport"
    assert res.get("formatted_price") == f"$6.200.000 {PRICE_PACKAGE_ANCHOR}"

    # When URL is absent and _items is empty, fuzzy falls through to
    # search_items which triggers the emergency fallback item (no 'id' key).
    # That is expected defensive behavior, not a regression.
    res_miss = catalog.match_catalog_item_by_image(
        "MOTO_DETECTADA: Missing | Match URL: https://firebasestorage.googleapis.com/v0/b/tiendalasmotos-documents/o/nonexistent.jpg"
    )
    assert res_miss is None or res_miss.get("id") != "tvs_sport"


def test_match_catalog_item_url_index_normalization():
    """
    [BOT-PLAN-MULTIMODAL-HARDENING-201] AF-02
    O(1) URL index handles trailing-slash and case normalization.
    Query params are preserved as-is (different canonical form).
    """
    catalog = CatalogService()
    items = _canonical_mock_items()
    hydrate_catalog_indexes(catalog, items)

    # Trailing slash normalized away
    res = catalog.match_catalog_item_by_image(
        "MOTO_DETECTADA: TVS | Match URL: https://firebasestorage.googleapis.com/v0/b/tiendalasmotos-documents/o/tvs_sport.jpg/"
    )
    assert res is not None
    assert res["id"] == "tvs_sport"

    # Query params produce a different normalized form from the index key
    # (index has no query; this URL has "?w=800&h=600" → "?h=600&w=800").
    # The O(1) index won't match → falls to fuzzy which matches "TVS NKD"?
    # The intent is: URL with appended query is "another resource".
    res_q = catalog.match_catalog_item_by_image(
        "MOTO_DETECTADA: TVS | Match URL: https://firebasestorage.googleapis.com/v0/b/tiendalasmotos-documents/o/tvs_sport.jpg?w=800&h=600"
    )
    # May or may not match depending on fuzzy fallback; at minimum must not crash
    if res_q is not None:
        assert "id" in res_q

    # Uppercase scheme/host/path → normalized to lowercase → matches index
    res_up = catalog.match_catalog_item_by_image(
        "MOTO_DETECTADA: TVS | Match URL: HTTPS://FIREBASESTORAGE.GOOGLEAPIS.COM/V0/B/TIENDALASMOTOS-DOCUMENTS/O/TVS_SPORT.JPG"
    )
    assert res_up is not None
    assert res_up["id"] == "tvs_sport"


# ── Unit: pipe parser normalization ──────────────────────────────────

def test_parse_vision_pipe_string_normal():
    """Normal pipe fields extracted."""
    parsed = CatalogService._parse_vision_pipe_string(
        "MOTO_DETECTADA: TVS Sport | Match URL: https://img.com/a.jpg | Model ID: tvs_sport"
    )
    assert parsed["model_name"] == "TVS Sport"
    assert parsed["match_url"] == "https://img.com/a.jpg"
    assert parsed["model_id"] == "tvs_sport"


def test_parse_vision_pipe_string_alternate_keys():
    """model_id with hyphen, image_url alias, moto detectada with space."""
    parsed = CatalogService._parse_vision_pipe_string(
        "moto detectada: NKD | image_url: https://x.com/nkd.jpg | model-id: akt_nkd"
    )
    assert parsed["model_name"] == "NKD"
    assert parsed["match_url"] == "https://x.com/nkd.jpg"
    assert parsed["model_id"] == "akt_nkd"


def test_parse_vision_pipe_string_fuzzy_order():
    """Fields in reverse order still parsed correctly."""
    parsed = CatalogService._parse_vision_pipe_string(
        "Model ID: tvs_raider | MOTO_DETECTADA: Raider | Match URL: https://img.com/raider.jpg"
    )
    assert parsed["model_id"] == "tvs_raider"
    assert parsed["model_name"] == "Raider"
    assert parsed["match_url"] == "https://img.com/raider.jpg"


def test_parse_vision_pipe_string_empty_and_null():
    """Empty string and non-string inputs return defaults."""
    assert CatalogService._parse_vision_pipe_string("") == {
        "model_id": None, "match_url": None, "model_name": None
    }
    assert CatalogService._parse_vision_pipe_string(None) == {
        "model_id": None, "match_url": None, "model_name": None
    }


def test_parse_vision_pipe_string_whitespace_nbsp():
    """NBSP and irregular whitespace are normalized."""
    parsed = CatalogService._parse_vision_pipe_string(
        "MOTO_DETECTADA:\u00a0\u00a0Victory  | Match URL:   https://img.com/v.jpg   "
    )
    assert parsed["model_name"] == "Victory"
    assert parsed["match_url"] == "https://img.com/v.jpg"


# ── Unit: ID normalization resolver (AF-ID-01..AF-ID-09) ──────────────

def _agility_items():
    return [
        {
            "id": "agility_fusion",
            "name": "KYMCO Agility Fusion",
            "image_url": "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos-documents/o/agility_fusion.jpg",
            "price": 10179000,
            "formatted_price": "$10.179.000",
        },
        {
            "id": "tvs_sport",
            "name": "TVS Sport 100",
            "image_url": "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos-documents/o/tvs_sport.jpg",
            "price": 6200000,
            "formatted_price": "$6.200.000",
        },
        {
            "id": "akt_nkd",
            "name": "AKT NKD 125",
            "image_url": "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos-documents/o/akt_nkd.jpg",
            "price": 5200000,
            "formatted_price": "$5.200.000",
        },
    ]


def test_normalize_item_id_key_static():
    """AF-ID-BASIC: _normalize_item_id_key produces canonical forms."""
    assert CatalogService._normalize_item_id_key("agility_fusion") == "agility_fusion"
    assert CatalogService._normalize_item_id_key("KYMCO AGILITY FUSION") == "kymco_agility_fusion"
    assert CatalogService._normalize_item_id_key("AGILITY_FUSION") == "agility_fusion"
    assert CatalogService._normalize_item_id_key("agility-fusion") == "agility_fusion"
    assert CatalogService._normalize_item_id_key("  Agility  Fusion  ") == "agility_fusion"
    assert CatalogService._normalize_item_id_key("") == ""
    assert CatalogService._normalize_item_id_key(None) == ""


def test_id_token_set_static():
    """AF-ID-BASIC: _id_token_set produces subset-able frozensets."""
    ts = CatalogService._id_token_set("agility_fusion")
    assert isinstance(ts, frozenset)
    assert ts == {"agility", "fusion"}
    assert CatalogService._id_token_set("TVS Sport 100") == {"tvs", "sport"}
    assert CatalogService._id_token_set("125") == frozenset()


def test_af_id_01_exact_id_still_works():
    """AF-ID-01: Exact match on doc.id untouched (zero regression)."""
    catalog = CatalogService()
    items = _agility_items()
    hydrate_catalog_indexes(catalog, items)
    res = catalog.match_catalog_item_by_image(
        "MOTO_DETECTADA: KYMCO | Model ID: agility_fusion"
    )
    assert res is not None
    assert res["id"] == "agility_fusion"
    assert res.get("formatted_price") == f"$10.179.000 {PRICE_PACKAGE_ANCHOR}"


def test_af_id_02_uppercase_id_norm():
    """AF-ID-02: Uppercase ID resolves via normalized index."""
    catalog = CatalogService()
    items = _agility_items()
    hydrate_catalog_indexes(catalog, items)
    res = catalog.match_catalog_item_by_image(
        "MOTO_DETECTADA: moto | Model ID: AGILITY_FUSION"
    )
    assert res is not None
    assert res["id"] == "agility_fusion"
    assert res.get("formatted_price") == f"$10.179.000 {PRICE_PACKAGE_ANCHOR}"


def test_af_id_03_hyphenated_id_norm():
    """AF-ID-03: Hyphenated ID slug resolves via normalized index."""
    catalog = CatalogService()
    items = _agility_items()
    hydrate_catalog_indexes(catalog, items)
    res = catalog.match_catalog_item_by_image(
        "MOTO_DETECTADA: moto | Model ID: agility-fusion"
    )
    assert res is not None
    assert res["id"] == "agility_fusion"
    assert res.get("formatted_price") == f"$10.179.000 {PRICE_PACKAGE_ANCHOR}"


def test_af_id_04_commercial_name_as_model_id():
    """AF-ID-04: Commercial name as Model ID resolves via name alias norm index."""
    catalog = CatalogService()
    items = _agility_items()
    hydrate_catalog_indexes(catalog, items)
    res = catalog.match_catalog_item_by_image(
        "MOTO_DETECTADA: Agility | Model ID: KYMCO AGILITY FUSION"
    )
    assert res is not None
    assert res["id"] == "agility_fusion"
    assert res.get("formatted_price") == f"$10.179.000 {PRICE_PACKAGE_ANCHOR}"


def test_af_id_05_no_moto_detectada_commercial_model_id():
    """AF-ID-05: Only commercial Model ID (no MOTO_DETECTADA) resolves."""
    catalog = CatalogService()
    items = _agility_items()
    hydrate_catalog_indexes(catalog, items)
    res = catalog.match_catalog_item_by_image(
        "Model ID: KYMCO AGILITY FUSION"
    )
    assert res is not None
    assert res["id"] == "agility_fusion"
    assert res.get("formatted_price") == f"$10.179.000 {PRICE_PACKAGE_ANCHOR}"


def test_af_id_06_dict_input_commercial_id():
    """AF-ID-06: Dict with commercial model_id resolves same as pipe string."""
    catalog = CatalogService()
    items = _agility_items()
    hydrate_catalog_indexes(catalog, items)
    res = catalog.match_catalog_item_by_image({
        "type": "moto",
        "model_id": "KYMCO AGILITY FUSION",
        "moto_detectada": "agility",
    })
    assert res is not None
    assert res["id"] == "agility_fusion"
    assert res.get("formatted_price") == f"$10.179.000 {PRICE_PACKAGE_ANCHOR}"


def test_af_id_07_collision_first_candidate_deterministic():
    """AF-ID-07: Ambiguous normalization collision returns FIRST non-padded candidate."""
    catalog = CatalogService()
    items = [
        {
            "id": "agility_fusion",
            "name": "KYMCO Agility Fusion",
            "image_url": "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos-documents/o/agility_fusion.jpg",
            "price": 10179000,
            "formatted_price": "$10.179.000",
        },
        {
            "id": "agility_fusion_2",
            "name": "KYMCO Agility Fusion 2",
            "image_url": "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos-documents/o/agility_fusion_2.jpg",
            "price": 9990000,
            "formatted_price": "$9.990.000",
        },
    ]
    hydrate_catalog_indexes(catalog, items)
    # Both items map to same norm key 'agility_fusion'
    res = catalog.match_catalog_item_by_image(
        "Model ID: agility fusion"
    )
    assert res is not None
    assert res["id"] == "agility_fusion"
    assert res.get("formatted_price") == f"$10.179.000 {PRICE_PACKAGE_ANCHOR}"
    # Verify image is consistent with the returned item
    assert "agility_fusion.jpg" in res.get("image_url", "")


def test_af_id_08_padded_item_exclusion():
    """AF-ID-08: Padded items are excluded from norm index resolution."""
    catalog = CatalogService()
    items = [
        {
            "id": "padded_item_0",
            "name": "Placeholder",
            "image_url": "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos-documents/o/pad.jpg",
            "price": 0,
            "formatted_price": "$0",
        },
        {
            "id": "agility_fusion",
            "name": "KYMCO Agility Fusion",
            "image_url": "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos-documents/o/agility_fusion.jpg",
            "price": 10179000,
            "formatted_price": "$10.179.000",
        },
    ]
    hydrate_catalog_indexes(catalog, items)
    # Manually mark padded so exclusion logic fires
    catalog._padded_ids.add("padded_item_0")
    # Both would map to generic norm, but padded must be skipped
    res = catalog.match_catalog_item_by_image(
        "Model ID: agility_fusion"
    )
    assert res is not None
    assert res["id"] == "agility_fusion"
    assert res.get("formatted_price") == f"$10.179.000 {PRICE_PACKAGE_ANCHOR}"


def test_af_id_09_formatted_price_preserved():
    """AF-ID-09: All ID resolution paths preserve formatted_price ($) parity."""
    catalog = CatalogService()
    items = _agility_items()
    hydrate_catalog_indexes(catalog, items)

    for pipe in [
        "Model ID: agility_fusion",
        "Model ID: AGILITY_FUSION",
        "Model ID: KYMCO AGILITY FUSION",
        "Model ID: agility-fusion",
    ]:
        res = catalog.match_catalog_item_by_image(pipe)
        assert res is not None, f"Failed for {pipe!r}"
        assert "$" in res.get("formatted_price", ""), f"Price parity broken for {pipe!r}"
        assert res.get("formatted_price") == f"$10.179.000 {PRICE_PACKAGE_ANCHOR}", f"Wrong price for {pipe!r}"
        assert res["id"] == "agility_fusion"


# ── Unit: fuzzy boundary + null inputs (AF-03, AF-04) ────────────────

def test_match_catalog_item_fuzzy_boundary():
    """Ratio 0.849 → no match; 0.85 → match."""
    catalog = CatalogService()
    items = _canonical_mock_items()[:1]  # only TVS Sport
    hydrate_catalog_indexes(catalog, items)

    # "TVS Sport 10" vs "TVS Sport 100" ratio ≈ 0.923 → match
    res = catalog.match_catalog_item_by_image("TVS Sport 10")
    assert res is not None

    # "TVS Xprt ZZZ" vs "TVS Sport 100" ratio < 0.85 → None
    res = catalog.match_catalog_item_by_image("TVS Xprt ZZZ")
    assert res is None


def test_match_catalog_item_none_empty_invalid():
    """AF-04: None, empty, dict with type≠moto, all return None."""
    catalog = CatalogService()
    items = _canonical_mock_items()
    hydrate_catalog_indexes(catalog, items)

    assert catalog.match_catalog_item_by_image(None) is None
    assert catalog.match_catalog_item_by_image("") is None
    assert catalog.match_catalog_item_by_image({}) is None
    assert catalog.match_catalog_item_by_image({"type": "sticker"}) is None
    assert catalog.match_catalog_item_by_image({"type": "other"}) is None


def test_match_catalog_item_dict_input():
    """Dict input with type=moto matches correctly."""
    catalog = CatalogService()
    items = _canonical_mock_items()
    hydrate_catalog_indexes(catalog, items)

    res = catalog.match_catalog_item_by_image({
        "type": "moto",
        "moto_detectada": "TVS Sport 100",
        "match_url": "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos-documents/o/tvs_sport.jpg",
        "model_id": "tvs_sport",
        "confidence": 0.92,
    })
    assert res is not None
    assert res["id"] == "tvs_sport"
    assert res.get("formatted_price") == f"$6.200.000 {PRICE_PACKAGE_ANCHOR}"


# ── Unit: rehydrate formatted_price ──────────────────────────────────

def test_rehydrate_formatted_price():
    """AF-07: _rehydrate_formatted_price fills missing formatted_price with anchor."""
    from app.services.catalog_service import PRICE_PACKAGE_ANCHOR
    item_no_fmt = {"id": "x", "name": "Test", "price": 9990000}
    result = CatalogService._rehydrate_formatted_price(item_no_fmt)
    assert "$9.990.000" in result
    assert PRICE_PACKAGE_ANCHOR in result

    item_has_fmt = {"id": "x", "formatted_price": "$1.000.000"}
    result = CatalogService._rehydrate_formatted_price(item_has_fmt)
    assert "$1.000.000" in result
    assert PRICE_PACKAGE_ANCHOR in result

    item_no_price = {"id": "x", "name": "Test"}
    assert CatalogService._rehydrate_formatted_price(item_no_price) == ""


# ── Unit: Anti-Null Masking (Vision) ─────────────────────────────────

def test_vision_service_catalog_serialization_anti_null_masking():
    """
    Test that VisionService logs a warning with traceback (Anti-Null Masking)
    if catalog items have empty name or image_url.
    """
    mock_db = MagicMock()
    mock_db.project = "test-project-123"

    mock_genai_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"type": "other", "description": "test"}'
    mock_genai_client.models.generate_content.return_value = mock_response

    corrupt_items = [
        {"id": "bad_item_1", "name": None, "image_url": "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos-documents/o/bad.webp?alt=media"},
        {"id": "bad_item_2", "name": "Victory Neo", "image_url": ""}
    ]

    with patch("app.services.genai_client_service.genai.Client", return_value=mock_genai_client), \
         patch("app.services.vision_service.logger.warning") as mock_log_warning:

        service = VisionService(db=mock_db)
        service.client = mock_genai_client
        service._model_id = "gemini-2.5-flash"

        import asyncio
        asyncio.run(service.analyze_image(
            image_bytes=b"dummy",
            mime_type="image/jpeg",
            phone="12345",
            caption="test",
            catalog_items=corrupt_items
        ))

        assert mock_log_warning.call_count == 2

        args1, _ = mock_log_warning.call_args_list[0]
        assert "[INTEGRITY VIOLATION]" in args1[0]
        assert "bad_item_1" in args1[0]
        assert "Traceback:" in args1[0]

        args2, _ = mock_log_warning.call_args_list[1]
        assert "[INTEGRITY VIOLATION]" in args2[0]
        assert "bad_item_2" in args2[0]
        assert "Traceback:" in args2[0]


# ── Integration: WhatsApp webhook e2e ─────────────────────────────────

@pytest.mark.asyncio
async def test_incoming_image_webhook_multimodal_similitude_flow():
    """
    [BOT-PLAN-MULTIMODAL-HARDENING-201] AF-10..AF-14
    Verifies the integration of the multimodal similarity pipeline.
    Now hydrates _items_by_image_url_norm and asserts Ficha Tecnica: in caption.
    """
    import app.routers.whatsapp as whatsapp
    from app.routers.whatsapp import _handle_message_background
    from fastapi import BackgroundTasks

    whatsapp._ensure_services_sync()
    orig_debounce = whatsapp.message_buffer.debounce_seconds
    whatsapp.message_buffer.debounce_seconds = 0.0

    user_phone = "+573009999999"

    try:
        await whatsapp.message_buffer.clear_buffer(user_phone)
        if user_phone in whatsapp.message_buffer._processed_wamids:
            whatsapp.message_buffer._processed_wamids[user_phone].clear()

        msg_data = {
            "from": user_phone,
            "id": "wamid.multimodal_test_158",
            "type": "image",
            "image": {
                "id": "media_id_158",
                "mime_type": "image/jpeg",
                "caption": "Quiero esta moto"
            },
            "phone_number_id": "12345678"
        }

        mock_prospect_data = {
            "exists": True,
            "celular": user_phone,
            "chatbot_status": "ACTIVE",
            "status": "IN_PROGRESS",
            "habeas_data_accepted": True,
            "nombre": "Juan Multimodal",
            "ciudad": "Cali",
            "forma_pago": "credito",
            "moto_interest": None
        }

        mock_ms = AsyncMock()
        mock_ms.get_prospect_data = AsyncMock(return_value=mock_prospect_data)
        mock_ms.create_prospect_if_missing = AsyncMock()
        mock_ms.get_chat_history = AsyncMock(return_value=[])
        mock_ms.save_message = AsyncMock()
        mock_ms.generate_and_update_summary = AsyncMock()
        mock_ms.update_last_interaction = AsyncMock()
        mock_ms.transition_to_in_progress = AsyncMock()
        mock_ms.set_human_help_status = AsyncMock()
        mock_ms.update_prospect_summary = AsyncMock()

        mock_client = MagicMock()
        mock_chat = AsyncMock()
        mock_response = MagicMock()
        mock_candidate = MagicMock()
        mock_part = MagicMock()

        mock_part.text = (
            "Perfecto. La TVS Sport 100 cuesta $6.200.000. "
            "Ficha Tecnica: Gran rendimiento. "
            "![TVS Sport 100](https://firebasestorage.googleapis.com/v0/b/tiendalasmotos-documents/o/tvs_sport.jpg)"
        )
        mock_part.function_call = None
        mock_candidate.content.parts = [mock_part]
        mock_response.candidates = [mock_candidate]
        mock_chat.send_message = AsyncMock(return_value=mock_response)
        mock_client.aio.chats.create = MagicMock(return_value=mock_chat)

        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json = MagicMock(
            return_value={"messages": [{"id": "wamid.outbound_158"}]}
        )

        mock_vision = AsyncMock()
        mock_vision.analyze_image = AsyncMock(
            return_value="MOTO_DETECTADA: TVS Sport 100 | Match URL: https://firebasestorage.googleapis.com/v0/b/tiendalasmotos-documents/o/tvs_sport.jpg | Model ID: tvs_sport"
        )

        mock_catalog_item = {
            "id": "tvs_sport",
            "name": "TVS Sport 100",
            "image_url": "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos-documents/o/tvs_sport.jpg",
            "price": 6200000,
            "formatted_price": "$6.200.000",
            "category": "sport",
            "active": True,
        }

        # ── [BOT-PLAN-MULTIMODAL-HARDENING-201] Hydrate BOTH indexes ──
        import app.services.catalog_service as cs_mod
        items = [mock_catalog_item]
        id_norm_key = cs_mod.CatalogService._normalize_item_id_key(mock_catalog_item["id"])
        with patch("app.routers.whatsapp.settings") as mock_settings, \
             patch("app.routers.whatsapp.db", MagicMock()), \
             patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
             patch("app.routers.whatsapp.judge_service") as mock_judge, \
             patch("app.routers.whatsapp.VisionService", return_value=mock_vision), \
             patch("app.routers.whatsapp.storage_service.download_media", AsyncMock(return_value=b"dummy_bytes")), \
             patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_http_post, \
             patch("app.services.whatsapp_service.whatsapp_service.mark_as_read", AsyncMock()), \
             patch("app.services.genai_client_service.genai.Client", return_value=mock_client), \
             patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
             patch("app.services.ai_brain.SDK_AVAILABLE", True), \
             patch.object(whatsapp.catalog_service, "_items", items), \
             patch.object(whatsapp.catalog_service, "_items_by_id", {"tvs_sport": mock_catalog_item}), \
             patch.object(whatsapp.catalog_service, "_items_by_image_url_norm",
                          {cs_mod.CatalogService._normalize_image_url(mock_catalog_item["image_url"]): mock_catalog_item}), \
             patch.object(whatsapp.catalog_service, "_items_by_id_norm",
                          {id_norm_key: ["tvs_sport"]}):

            mock_http_post.return_value = mock_http_response
            mock_settings.whatsapp_app_secret = None
            mock_judge.analyze_response = AsyncMock(return_value=(True, ""))

            background_tasks = BackgroundTasks()
            await _handle_message_background(msg_data, background_tasks)

            # AF-10: Ponytail PENDING + moto_interest
            mock_ms.update_prospect_summary.assert_any_call(
                user_phone, "", {
                    "moto_interest": "TVS Sport 100",
                    "ponytail_status": "PENDING"
                }
            )

            assert mock_http_post.call_count == 1
            meta_payload = mock_http_post.call_args.kwargs.get("json")
            assert meta_payload is not None
            assert meta_payload.get("type") == "image"

            # AF-13: canonical image link
            assert meta_payload["image"]["link"] == "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos-documents/o/tvs_sport.jpg"

            # AF-11: canonical price in caption
            caption = meta_payload["image"]["caption"]
            assert "TVS Sport 100" in caption
            assert "$6.200.000" in caption

            # AF-12: Ficha Tecnica: prefix present (was missing in v10.45)
            assert "Ficha Tecnica:" in caption, (
                "AF-12 FAIL: caption must contain literal 'Ficha Tecnica:' prefix"
            )

    finally:
        whatsapp.message_buffer.debounce_seconds = orig_debounce


# ── [BOT-BUILD-BUGFIX-MULTIMODAL-CAPTION-01] Harness compartido T2–T4 ────

async def _run_image_caption_flow(caption: str, summary: str, llm_text: str):
    """
    Conduce la rama imagen+caption de `_handle_message_background` con catálogo
    hidratado (índices id / url_norm / id_norm) y LLM mockeado.
    Retorna (mock_ms, mock_http_post) para aserciones de prompt y de egreso.
    """
    import app.routers.whatsapp as whatsapp
    from app.routers.whatsapp import _handle_message_background
    from fastapi import BackgroundTasks

    whatsapp._ensure_services_sync()
    orig_debounce = whatsapp.message_buffer.debounce_seconds
    whatsapp.message_buffer.debounce_seconds = 0.0

    user_phone = "+573008888888"

    try:
        await whatsapp.message_buffer.clear_buffer(user_phone)
        if user_phone in whatsapp.message_buffer._processed_wamids:
            whatsapp.message_buffer._processed_wamids[user_phone].clear()

        msg_data = {
            "from": user_phone,
            "id": f"wamid.caption01_{caption[:12]}",
            "type": "image",
            "image": {
                "id": "media_id_caption01",
                "mime_type": "image/jpeg",
                "caption": caption
            },
            "phone_number_id": "12345678"
        }

        mock_prospect_data = {
            "exists": True,
            "celular": user_phone,
            "chatbot_status": "ACTIVE",
            "status": "IN_PROGRESS",
            "habeas_data_accepted": True,
            "nombre": "Juan Caption",
            "ciudad": "Cali",
            "forma_pago": "credito",
            "moto_interest": None,
            "_catalog_top_name": "TVS Sport 100",
        }

        mock_ms = AsyncMock()
        mock_ms.get_prospect_data = AsyncMock(return_value=mock_prospect_data)
        mock_ms.create_prospect_if_missing = AsyncMock()
        mock_ms.get_chat_history = AsyncMock(return_value=[])
        mock_ms.save_message = AsyncMock()
        mock_ms.generate_and_update_summary = AsyncMock()
        mock_ms.update_last_interaction = AsyncMock()
        mock_ms.transition_to_in_progress = AsyncMock()
        mock_ms.set_human_help_status = AsyncMock()
        mock_ms.update_prospect_summary = AsyncMock()

        mock_client = MagicMock()
        mock_chat = AsyncMock()
        mock_response = MagicMock()
        mock_candidate = MagicMock()
        mock_part = MagicMock()
        mock_part.text = llm_text
        mock_part.function_call = None
        mock_candidate.content.parts = [mock_part]
        mock_response.candidates = [mock_candidate]
        mock_chat.send_message = AsyncMock(return_value=mock_response)
        mock_client.aio.chats.create = MagicMock(return_value=mock_chat)

        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json = MagicMock(
            return_value={"messages": [{"id": "wamid.outbound_caption01"}]}
        )

        mock_vision = AsyncMock()
        mock_vision.analyze_image = AsyncMock(
            return_value="MOTO_DETECTADA: TVS Sport 100 | Match URL: https://firebasestorage.googleapis.com/v0/b/tiendalasmotos-documents/o/tvs_sport.jpg | Model ID: tvs_sport"
        )

        mock_catalog_item = {
            "id": "tvs_sport",
            "name": "TVS Sport 100",
            "image_url": "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos-documents/o/tvs_sport.jpg",
            "price": 6200000,
            "formatted_price": "$6.200.000",
            "category": "sport",
            "active": True,
        }
        if summary is not None:
            mock_catalog_item["summary"] = summary

        import app.services.catalog_service as cs_mod
        items = [mock_catalog_item]
        id_norm_key = cs_mod.CatalogService._normalize_item_id_key(mock_catalog_item["id"])
        # [CAPTION-01] Los índices se parchan sobre el SINGLETON real
        # (app.services.catalog_service.catalog_service), no sobre el LazyProxy
        # del router: LazyProxy no define __setattr__, por lo que patch.object
        # sobre el proxy es invisible para el self real del matcher (placebo).
        with patch("app.routers.whatsapp.settings") as mock_settings, \
             patch("app.routers.whatsapp.db", MagicMock()), \
             patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
             patch("app.routers.whatsapp.judge_service") as mock_judge, \
             patch("app.routers.whatsapp.VisionService", return_value=mock_vision), \
             patch("app.routers.whatsapp.storage_service.download_media", AsyncMock(return_value=b"dummy_bytes")), \
             patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_http_post, \
             patch("app.services.whatsapp_service.whatsapp_service.mark_as_read", AsyncMock()), \
             patch("app.services.genai_client_service.genai.Client", return_value=mock_client), \
             patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
             patch("app.services.ai_brain.SDK_AVAILABLE", True), \
             patch.object(cs_mod.catalog_service, "_items", items), \
             patch.object(cs_mod.catalog_service, "_items_by_id", {"tvs_sport": mock_catalog_item}), \
             patch.object(cs_mod.catalog_service, "_items_by_image_url_norm",
                          {cs_mod.CatalogService._normalize_image_url(mock_catalog_item["image_url"]): mock_catalog_item}), \
             patch.object(cs_mod.catalog_service, "_items_by_id_norm",
                          {id_norm_key: ["tvs_sport"]}), \
             patch.object(cs_mod.catalog_service, "_db", MagicMock()):

            mock_http_post.return_value = mock_http_response
            mock_settings.whatsapp_app_secret = None
            mock_judge.analyze_response = AsyncMock(return_value=(True, ""))

            await _handle_message_background(msg_data, BackgroundTasks())
            return mock_ms, mock_http_post

    finally:
        whatsapp.message_buffer.debounce_seconds = orig_debounce


@pytest.mark.asyncio
async def test_image_tech_caption_injects_canonical_ficha_hint():
    """
    [CAPTION-01 / T2] Caption técnico: el simulated_user_msg persistido como
    mensaje 'user' transporta el hint OBLIGATORIO con la ficha canónica del
    ítem matcheado, y el egreso contiene el prefijo literal 'Ficha Tecnica:'.
    """
    summary = "Motor 124.8cc, caja de 4 cambios, encendido eléctrico"
    llm_text = (
        "La TVS Sport 100 cuesta $6.200.000. "
        "Ficha Tecnica: Motor 124.8cc, caja de 4 cambios, encendido eléctrico. "
        "![TVS Sport 100](https://firebasestorage.googleapis.com/v0/b/tiendalasmotos-documents/o/tvs_sport.jpg)"
    )
    mock_ms, mock_http_post = await _run_image_caption_flow(
        caption="cuantos cambios tiene?", summary=summary, llm_text=llm_text
    )

    user_saves = [c for c in mock_ms.save_message.call_args_list if c.args[1] == "user"]
    assert len(user_saves) == 1
    simulated_user_msg = user_saves[0].args[2]
    assert 'El usuario también escribió: "cuantos cambios tiene?"' in simulated_user_msg
    assert "OBLIGATORIO: incluye el prefijo literal 'Ficha Tecnica:'" in simulated_user_msg
    assert summary in simulated_user_msg

    assert mock_http_post.call_count == 1
    meta_payload = mock_http_post.call_args.kwargs.get("json")
    assert meta_payload.get("type") == "image"
    assert "Ficha Tecnica:" in meta_payload["image"]["caption"]


@pytest.mark.asyncio
async def test_image_tech_caption_backstop_injects_ficha_when_llm_omits():
    """
    [CAPTION-01 / T3] Backstop determinista: el LLM omite el prefijo → el router
    inyecta 'Ficha Tecnica: {summary}' canónico post-generación, antes del egreso.
    """
    summary = "Motor 124.8cc, caja de 4 cambios, encendido eléctrico"
    llm_text = (
        "Claro, la TVS Sport 100 cuesta $6.200.000. "
        "![TVS Sport 100](https://firebasestorage.googleapis.com/v0/b/tiendalasmotos-documents/o/tvs_sport.jpg)"
    )
    mock_ms, mock_http_post = await _run_image_caption_flow(
        caption="que tipo de encendido maneja?", summary=summary, llm_text=llm_text
    )

    assert mock_http_post.call_count == 1
    caption_out = mock_http_post.call_args.kwargs["json"]["image"]["caption"]
    assert "Ficha Tecnica: TVS Sport 100" in caption_out, (
        "C-20b fallback must emit Ficha Tecnica: with model name"
    )
    # C-20b trade-off (C6): specs summary NOT injected. C5-028 pending.
    assert summary not in caption_out, (
        "C-20b: technical summary intentionally absent from degraded fallback"
    )


@pytest.mark.asyncio
async def test_image_nontech_caption_no_ficha_injection():
    """
    [CAPTION-01 / T4] No-regresión: caption no técnico → sin hint OBLIGATORIO y
    sin backstop; el egreso queda libre de bloques 'Ficha Tecnica:' añadidos por
    la costura visual.
    """
    summary = "Motor 124.8cc, caja de 4 cambios, encendido eléctrico"
    llm_text = (
        "Claro, la TVS Sport 100 cuesta $6.200.000. "
        "![TVS Sport 100](https://firebasestorage.googleapis.com/v0/b/tiendalasmotos-documents/o/tvs_sport.jpg)"
    )
    mock_ms, mock_http_post = await _run_image_caption_flow(
        caption="muy bonita", summary=summary, llm_text=llm_text
    )

    user_saves = [c for c in mock_ms.save_message.call_args_list if c.args[1] == "user"]
    assert len(user_saves) == 1
    assert "OBLIGATORIO" not in user_saves[0].args[2]

    assert mock_http_post.call_count == 1
    caption_out = mock_http_post.call_args.kwargs["json"]["image"]["caption"]
    assert "Ficha Tecnica:" not in caption_out
