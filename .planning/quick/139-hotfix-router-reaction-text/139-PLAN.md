---
task: 139
name: isolate-reaction-interceptor
description: Isolate reaction interceptor to msg_type == 'reaction' and preserve fuzzy difflib matching under text messages.
---

# Quick Task 139: Isolate Reaction Interceptor

## Objective
Isolate the WhatsApp reaction-based Habeas Data acceptance logic completely inside the `msg_type == "reaction"` block, avoiding any residual mutations of `prospect_data` under standard text messages, and ensuring fuzzy matching works properly.

## Tasks

<task type="auto">
  <name>Isolate reaction interceptor in whatsapp.py</name>
  <files>[app/routers/whatsapp.py]</files>
  <action>Move update_prospect_summary and prospect_data['habeas_data_accepted'] = True logic completely inside the if msg_type == "reaction" conditional block, removing all occurrences outside it.</action>
  <verify>.venv/bin/pytest tests/test_identity_legal_gate.py</verify>
  <done>All reaction-specific state mutations are isolated within the reaction webhook block, and tests pass.</done>
</task>

<task type="auto">
  <name>Update tests and add fuzzy text matching verification</name>
  <files>[tests/test_identity_legal_gate.py, tests/test_agentic_loop_async.py]</files>
  <action>Update test_identity_legal_gate.py to support the new isolated structure via updated mocks, and add a test in test_agentic_loop_async.py asserting that clean text messages bypass reaction interception and use fuzzy matching.</action>
  <verify>.venv/bin/pytest tests/test_agentic_loop_async.py tests/test_identity_legal_gate.py</verify>
  <done>Mocks are aligned, and new test verifies text message isolation and fuzzy matching.</done>
</task>

<task type="auto">
  <name>Run agent-cli eval to certify coherence score</name>
  <files>[]</files>
  <action>Run npx @tobiasgaitan/agent-cli eval to verify full suite passes and coherence score remains 1.000.</done>
  <verify>npx @tobiasgaitan/agent-cli eval</verify>
  <done>Evaluation output confirms score >= 0.9 (1.000).</done>
</task>

---
*Created: 2026-07-08*
