---
task: 196
name: Router Greeting Threshold Hotfix
description: Fix evaluates_skip_greeting newly_created evaluation and align has_no_legitimate_history in ai_brain.py to prevent greeting loops while preserving 12-hour window.
---

# Quick Task 196: Router Greeting Threshold Hotfix

## Objective
Fix the skip_greeting evaluation loop by:
1. Modifying `_evaluate_skip_greeting` in `app/routers/whatsapp.py` to eliminate `is_metadata_only` and evaluate `newly_created` based solely on the existence of the Firestore document (`not exists`).
2. Isolating the current message from history in `_evaluate_skip_greeting` by extracting only previous user messages (slicing the last element if `current_message_saved` is True).
3. Removing all `skip_greeting` variable mutations from `app/services/ai_brain.py`, respecting and inheriting the parameter directly from the router.

## Tasks

<task type="auto">
  <name>Saneamiento de newly_created y Calibración de Umbral en whatsapp.py</name>
  <files>
    <file>app/routers/whatsapp.py</file>
  </files>
  <action>Modify `_evaluate_skip_greeting` in `app/routers/whatsapp.py` to eliminate `is_metadata_only`, calculate `newly_created` as `not exists`, and filter current turn message from past user messages.</action>
  <verify>Run the test suite</verify>
  <done>`is_metadata_only` is removed, `newly_created` is calculated correctly, and tests pass.</done>
</task>

<task type="auto">
  <name>Align has_no_legitimate_history logic in ai_brain.py and remove skip_greeting mutations</name>
  <files>
    <file>app/services/ai_brain.py</file>
  </files>
  <action>Modify `_generate_with_retry_async` in `app/services/ai_brain.py` to evaluate `has_no_legitimate_history` exclusively using the history list length, and remove all direct mutations of the `skip_greeting` parameter.</action>
  <verify>Run existing tests</verify>
  <done>`has_no_legitimate_history` is computed from history, and skip_greeting is inherited directly without any mutations.</done>
</task>

<task type="auto">
  <name>Add unit test to test_identity_legal_gate.py</name>
  <files>
    <file>tests/test_identity_legal_gate.py</file>
  </files>
  <action>Add the unit test `test_consecutive_out_of_catalog_query_suppresses_greeting` to simulate a continuous session query of an out-of-catalog model, verifying that the greeting is suppressed.</action>
  <verify>.venv/bin/pytest tests/test_identity_legal_gate.py</verify>
  <done>New test passes cleanly.</done>
</task>

---
*Created: 2026-07-17*
