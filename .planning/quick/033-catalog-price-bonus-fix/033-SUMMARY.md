# Quick Task 033: Catalog Price Bonus Fix — Summary

**Executed:** 2026-05-18
**Status:** Complete

## What Was Done
1. **Canonical Price Enforcement:** Modified the Firestore database extraction in `CatalogService.load_catalog()` to force the canonical base key: `price_val = data.get("price") or 0`, ensuring that any legacy keys like `precio` are ignored, thus resolving a potential collision.
2. **Bonus Extraction:** Configured `CatalogService.load_catalog()` to extract `bonusAmount` and `bonusEndDate` directly from Firestore item documents and inject them into `mapped_item`.
3. **Active Bonus Validation:** Added helper methods `_get_active_bonus_info` and `_is_bonus_active` in `CatalogService`. This parser handles:
   - Objects with `timestamp` or `to_datetime` (Firestore Timestamps, standard datetime).
   - ISO/Standard String representations (`%Y-%m-%d`, `%Y-%m-%dT%H:%M:%S`, etc.).
   - Epoch timestamps (int/float).
4. **Context Serialization:** Enforced real-time validation of bonuses in the serialisation layer inside `search_items()`. Active bonuses are serialized to `truncated_item` as their respective `amount` and `end_date`. Expired/invalid bonuses are sanitized to `0` and `None` respectively, preventing contaminated simulations.
5. **Markdown Mutation:** Configured `search_catalog()` to append ` [BONO EXCLUSIVO DE CONTADO: $X válido hasta Y]` to the item's Markdown entry if the bonus is active.
6. **Robust Testing:** Created a comprehensive test suite in `tests/test_catalog_price_bonus.py` to assert the correct behavior of the hotfix.

## Files Modified
| File | Action | Description |
|------|--------|-------------|
| [catalog_service.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/services/catalog_service.py) | Modified | Core price extraction, bonus parsing, serialisation, and Markdown mutation. |
| [test_catalog_price_bonus.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_catalog_price_bonus.py) | Created | Suite of unit tests covering the extraction, date parsing, serialisation, and Markdown mutation of bonuses. |

## Verification
Executed `pytest` and `npx agent-cli eval`. All tests and validation pipelines passed with a perfect coherence score:
```bash
.venv/bin/pytest tests/test_catalog_price_bonus.py
# 4 passed in 0.11s

npx agent-cli eval
# Tests passed : 97
# Tests failed : 0
# Total        : 97
# Score        : 1.000 (threshold: 0.9)
# ✓ SCORE 1.000 ≥ 0.9 — DEPLOY AUTHORIZED ✅
```

---
*Completed: 2026-05-18*
