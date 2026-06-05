---
task: 040
name: Cascade Failure & Denial of Service Fix
description: "Fix ValueError crash on empty catalog 'summary' key and unhandled gRPC exception in update_whatsapp_status"
---

# Quick Task 040: Cascade Failure & Denial of Service Fix

## Objective
Resolve two critical crashes that cause denial of service: (1) a synchronous `raise ValueError` in `ai_brain.py` line 1096 that kills the God Node when a catalog item has an empty `summary` key, and (2) an unhandled gRPC exception in `memory_service.py` `update_whatsapp_status` that breaks the execution thread.

## Tasks

<task type="auto">
  <name>Refactor Anti-Null Masking in ai_brain.py catalog iteration</name>
  <files>app/services/ai_brain.py</files>
  <action>Replace the `raise ValueError` at line 1096 with a `logger.warning` that emits full diagnostic context (item name, summary, price values) and a `continue` to skip the corrupted item without destroying the catalog iteration loop. Also change the outer `except Exception as e: raise e` at line 1143-1146 to log the error and set a degraded `search_results` fallback instead of re-raising, so a single corrupted item doesn't crash the entire God Node.</action>
  <verify>cd /Users/tobiasgaitangallego/Bot-TiendaLasMotos && python -m pytest tests/test_pcc_ficha_tecnica.py tests/test_catalog_price_bonus.py tests/test_perf_45.py -v --tb=short 2>&1 | tail -30</verify>
  <done>Corrupted catalog items are skipped with a logger.warning, the iteration continues, and existing tests pass.</done>
</task>

<task type="auto">
  <name>Wrap update_whatsapp_status with gRPC exception handler</name>
  <files>app/services/memory_service.py</files>
  <action>In `update_whatsapp_status`, the current `except Exception as e` at line 603 logs but still allows unhandled gRPC errors to propagate via the `except (TimeoutError, ...) raise` block at line 601. The caller in whatsapp.py line 201 wraps this in a background task but only has a generic `except Exception`. The fix: ensure that the method's outer `except Exception` block catches ALL remaining exceptions (including gRPC-specific ones like NotFound, PermissionDenied) and logs them forensically WITHOUT re-raising, so the orchestrator thread is never broken by a status update failure.</action>
  <verify>cd /Users/tobiasgaitangallego/Bot-TiendaLasMotos && python -m pytest tests/ -v --tb=short 2>&1 | tail -30</verify>
  <done>gRPC exceptions in update_whatsapp_status are captured with forensic logging, the orchestrator thread continues.</done>
</task>

<task type="auto">
  <name>Unit tests for both fixes</name>
  <files>tests/test_bot_bug_040.py</files>
  <action>Create test_bot_bug_040.py with: (1) Test that a catalog item with empty 'summary' does NOT raise ValueError but is skipped with continue (test the formatter logic in isolation). (2) Test that update_whatsapp_status catches gRPC NotFound and does not raise. (3) Content assertion test verifying 'Ficha Tecnica:' presence when valid items exist alongside corrupted ones.</action>
  <verify>cd /Users/tobiasgaitangallego/Bot-TiendaLasMotos && python -m pytest tests/test_bot_bug_040.py -v --tb=short</verify>
  <done>All 3 test cases pass, validating both fixes.</done>
</task>

---
*Created: 2026-06-04*
