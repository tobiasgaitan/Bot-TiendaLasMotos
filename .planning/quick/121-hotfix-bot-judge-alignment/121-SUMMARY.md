# Quick Task 121: hotfix-bot-judge-alignment — Summary

**Executed:** 2026-07-06
**Status:** Complete

## What Was Done
1. **Stateless Query Translation**: Implemented `resolve_query_aliases` in `app/routers/whatsapp.py` to translate colloquial query terms or synonyms (e.g. 'señoritera') to the canonical category name (e.g. 'semiautomatica') using `config_service.get_catalog_aliases()` before calling `catalog_service_local.search()`.
2. **Context Formatting with Neto and Con SOAT prices**: Modified both text and audio message handlers in `app/routers/whatsapp.py` to format the constructed `catalog_context` for the Judge Service to include both the base/net price from the catalog (`Neto: $X.XXX.XXX`) and the price with SOAT/registration/fees included (`Con SOAT: $Y.YYY.YYY (incluye SOAT, Matrícula, y tramites)`).
3. **Regression Tests**: Added `tests/test_judge_alias_context.py` containing automated tests to certify the alias resolution, context formatting, and Judge Service approval for Victory Advance X1 prices.

## Files Modified
| File | Action | Description |
|------|--------|-------------|
| [app/routers/whatsapp.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/routers/whatsapp.py) | Modified | Added query translation and dual price formatting in `catalog_context` |
| [tests/test_judge_alias_context.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_judge_alias_context.py) | Created | Added regression test suite for alias resolution and price checks |

## Verification
- Verified with unit tests passing successfully:
  ```bash
  .venv/bin/pytest tests/test_judge_alias_context.py
  ```
  Output: `2 passed in 0.49s`
- Full test suite passed without regression:
  ```bash
  .venv/bin/pytest
  ```
  Output: `200 passed, 2 skipped in 6.54s`
- Verified evaluation gate passes successfully:
  ```bash
  npx @tobiasgaitan/agent-cli eval
  ```
  Output: `Score: 1.000`

---
*Completed: 2026-07-06*
