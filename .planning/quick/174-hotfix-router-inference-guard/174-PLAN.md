---
task: 174
name: hotfix_router_inference_guard
description: Implement initialization guard block before inference in whatsapp.py and add consistency test
---

# Quick Task 174: hotfix_router_inference_guard

## Objective
Implement a blocking initialization guard right before the inference block (around line 1197 in app/routers/whatsapp.py) that awaits memory_service.get_or_create_prospect(user_phone) and hydrates prospect_data. Add a unit test `test_inferred_state_reset_consistency` in `tests/test_webhook_sync_block.py` to verify this behavior.

## Tasks

<task type="auto">
  <name>Implement inference guard in whatsapp.py</name>
  <files>app/routers/whatsapp.py</files>
  <action>Add an await ms.get_or_create_prospect(user_phone) call to fully hydrate prospect_data before the inference try block, supporting test environments with mock fallbacks.</action>
  <verify>.venv/bin/pytest tests/test_webhook_sync_block.py</verify>
  <done>The code runs and passes existing tests.</done>
</task>

<task type="auto">
  <name>Implement unit test in test_webhook_sync_block.py</name>
  <files>tests/test_webhook_sync_block.py</files>
  <action>Add test_inferred_state_reset_consistency to verify prospect_data has correct initial state after a /reset and is loaded prior to inference.</action>
  <verify>.venv/bin/pytest tests/test_webhook_sync_block.py</verify>
  <done>All tests including the new test pass successfully.</done>
</task>
