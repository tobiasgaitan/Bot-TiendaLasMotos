---
task: 101
name: bot-arch-state-101
description: Revertir la eliminación de 'calculate_credit_score' del toolset en _create_tools (Fase 1) y eliminar la purga regex del prompt. En su lugar, implementar el 'Tool Rejection Pattern' en ai_brain.py y ajustar test_proactive_credit.py.
---

# Quick Task 101: bot-arch-state-101

## Objective
Revert credit tool exclusion and prompt purge for Phase 1. Implement Tool Rejection Pattern for `calculate_credit_score` in PHASE_1_PROFILING, and update unit tests to verify.

## Tasks

<task type="auto">
  <name>Implement Tool Rejection Pattern and revert exclusions</name>
  <files>app/services/ai_brain.py</files>
  <action>Revert exclusions of calculate_credit_score from _create_tools, remove prompt purge regex, and implement tool rejection returning an error message for calculate_credit_score during PHASE_1_PROFILING.</action>
  <verify>.venv/bin/pytest tests/test_proactive_credit.py</verify>
  <done>Verification tests pass successfully.</done>
</task>

<task type="auto">
  <name>Adjust unit tests to validate Tool Rejection Pattern</name>
  <files>tests/test_proactive_credit.py, tests/test_semantic_plumbing.py</files>
  <action>Modify test_proactive_credit.py to assert that calculate_credit_score is in Phase 1 tools but returns an error on invocation. Adjust or remove obsolete prompt purge assertions in test_semantic_plumbing.py.</action>
  <verify>.venv/bin/pytest tests/test_proactive_credit.py tests/test_semantic_plumbing.py</verify>
  <done>All tests pass successfully.</done>
</task>
