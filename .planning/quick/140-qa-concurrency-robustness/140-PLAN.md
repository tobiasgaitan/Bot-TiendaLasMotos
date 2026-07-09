---
task: 140
name: concurrency-stress-phonetic
description: Falso positivo en el entorno de pruebas por falta de simulación de estrés concurrente. El motor fonético falla bajo ráfagas de acuses de Meta que bloquean temporalmente el refresco de alias de catálogo mediante el guardrail IN_PROGRESS.
---

# Quick Task 140: Concurrency Stress Phonetic

## Objective
Isolate background status updates from catalog hydration to prevent race conditions under load, and verify via a sequential stress test that fuzzy matching (specifically 'boser' to 'Boxer') succeeds even during webhook floods.

## Tasks

<task type="auto">
  <name>Isolate webhook statuses processing and fix phonetic search</name>
  <files>app/routers/whatsapp.py, app/services/catalog_service.py</files>
  <action>
    1. Define `_extract_statuses_list` to retrieve all statuses from webhook payload.
    2. Update `webhook_handler` and `task_processor` loops to process statuses with a try/except with continue to prevent a failure of a status update from interrupting the router.
    3. Put `_ensure_services()` inside the `try` block in `_handle_statuses_background` to ensure any service initialization failure is properly trapped and isolated.
    4. Add `"boser": "boxer"` to `spelling_map` in `app/services/catalog_service.py`.
  </action>
  <verify>pytest tests/test_agentic_loop_async.py</verify>
  <done>All tests pass and fuzzy match for 'boser' resolves Boxer under concurrency stress.</done>
</task>

<task type="auto">
  <name>Inject concurrency stress test</name>
  <files>tests/test_agentic_loop_async.py</files>
  <action>
    Add a new asynchronous test case `test_concurrency_stress_phonetic_boser` to `tests/test_agentic_loop_async.py` simulating concurrent Meta status webhooks arriving along with a fuzzy text query for 'boser'.
  </action>
  <verify>pytest tests/test_agentic_loop_async.py</verify>
  <done>The new test case passes and total test count raises.</done>
</task>

---
*Created: 2026-07-09*
