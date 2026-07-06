---
task: 114
name: hotfix-bot-perf-114
description: Restore async protection in whatsapp webhook config loader and recover test_webhook_sync_block.py unit test suite.
---

# Quick Task 114: hotfix-bot-perf-114

## Objective
Restore the async/performance shield in `app/routers/whatsapp.py` to prevent redundant loading of Firestore configurations, and recover the test suite `tests/test_webhook_sync_block.py` with its assertions.

## Tasks

<task type="auto">
  <name>Restaura blindaje de inicialización de configuración en webhook</name>
  <files>app/routers/whatsapp.py</files>
  <action>Condition config_service.initialize(db) call to avoid redundant loading: 'if db and not config_service._financial_config: config_service.initialize(db)'</action>
  <verify>pytest tests/test_webhook_sync_block.py</verify>
  <done>The config loader check in app/routers/whatsapp.py is properly conditioned and tests pass.</done>
</task>

<task type="auto">
  <name>Restaura test_webhook_sync_block.py</name>
  <files>tests/test_webhook_sync_block.py</files>
  <action>Re-create the unit test file tests/test_webhook_sync_block.py with the full suite of assertions including test_webhook_no_redundant_config_load and the rest of the recovered tests.</action>
  <verify>pytest tests/test_webhook_sync_block.py</verify>
  <done>All tests in tests/test_webhook_sync_block.py pass successfully.</done>
</task>
