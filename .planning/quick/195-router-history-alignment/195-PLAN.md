---
task: 195
name: Router History Alignment Hotfix
description: Exclusively evaluate has_no_legitimate_history on Firestore history length and force skip_greeting to True when history exists to suppress repeat greetings on out-of-catalog tool failures.
---

# Quick Task 195: Router History Alignment Hotfix

## Objective
Correct the evaluation of `has_no_legitimate_history` in `app/services/ai_brain.py` to depend exclusively on the existence of prior text interactions of the client in Firestore (`len(history) > 0`), and force `skip_greeting = True` if the user has a live session document, isolating the greeting suppression from `search_catalog` execution outcomes.

## Tasks

<task type="auto">
  <name>Align skip_greeting and has_no_legitimate_history logic in ai_brain.py</name>
  <files>
    <file>app/services/ai_brain.py</file>
  </files>
  <action>Modify `app/services/ai_brain.py` to evaluate `has_no_legitimate_history` exclusively using the history list length, and force `skip_greeting = True` when `has_no_legitimate_history` is False.</action>
  <verify>Run the test suite to ensure existing tests pass</verify>
  <done>Evaluation depends exclusively on history, skip_greeting is forced to True when history is present, and tests pass.</done>
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
