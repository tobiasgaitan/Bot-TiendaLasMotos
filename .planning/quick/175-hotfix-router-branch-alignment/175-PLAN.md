---
task: 175
name: Aligning Router Greeting Flag across Media Branches
description: Replace unconditional hardcoded skip_greeting=True in whatsapp.py satellite calls with dynamic evaluation and expand test assertions.
---

# Quick Task 175: Aligning Router Greeting Flag across Media Branches

## Objective
Substitute all remaining hardcoded `skip_greeting=True` flags in `app/routers/whatsapp.py` (specifically in the media/stickers and image detection branches) with dynamic `_evaluate_skip_greeting` calls. Expand `tests/test_webhook_sync_block.py` with rigid `assert_called_with` assertions on `skip_greeting` arguments for media tasks to prevent future hardcoding regressions.

## Tasks

<task type="auto">
  <name>Surgically align skip_greeting in app/routers/whatsapp.py</name>
  <files>
    <file>app/routers/whatsapp.py</file>
  </files>
  <action>Ensure that in app/routers/whatsapp.py, any Thinking satellite calls to cerebro_ia.pensar_respuesta evaluate skip_greeting dynamically using _evaluate_skip_greeting.</action>
  <verify>pytest tests/test_webhook_sync_block.py</verify>
  <done>All calls to pensar_respuesta dynamically pass evaluated skip_greeting.</done>
</task>

<task type="auto">
  <name>Extend and harden test_webhook_sync_block.py assertions</name>
  <files>
    <file>tests/test_webhook_sync_block.py</file>
  </files>
  <action>Add precise assertions using assert_called_with or asserting specific keys in mock calls to verify that the skip_greeting flag is calculated and passed correctly in both image and sticker flows.</action>
  <verify>pytest tests/test_webhook_sync_block.py</verify>
  <done>Tests verify skip_greeting passes assertion checks on mock parameters.</done>
</task>
