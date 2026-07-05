---
task: 113
name: Resolution of Semiautomatica Casing Collision in Firestore Aliases Hydration
description: Implement strict normalization (.lower().strip()) on category/alias processing, loading, and matching across catalog_service.py and ai_brain.py, write robust regression tests in test_drift_alias_bypass.py without difflib sequence matcher mocks, and certify a 1.000 Coherence Score.
---

# Quick Task 113: Resolution of Semiautomatica Casing Collision

## Objective
Implement strict category and alias normalization to resolve casing conflicts between Firestore dynamic configs and catalog data, prevent fallback false positives, and ensure robust drift interceptor testing.

## Tasks

<task type="auto">
  <name>Implement strict casing normalization in catalog_service.py and ai_brain.py</name>
  <files>
    <file>app/services/catalog_service.py</file>
    <file>app/services/ai_brain.py</file>
  </files>
  <action>
    - In app/services/catalog_service.py, strictly normalize keys and values to lower and strip during config loading and synonym expansion in search index.
    - In app/services/ai_brain.py, strictly normalize retrieved aliases and compare category and alias matching case-insensitively (.lower().strip()).
  </action>
  <verify>./.venv/bin/pytest tests/test_interceptor_blindaje.py</verify>
  <done>Category and alias keys/values are strictly lowercased and stripped upon processing, loading, and matching.</done>
</task>

<task type="auto">
  <name>Create regression test suite test_drift_alias_bypass.py</name>
  <files>
    <file>tests/test_drift_alias_bypass.py</file>
  </files>
  <action>
    - Create a test file tests/test_drift_alias_bypass.py evaluating "señoriter" (blocked due to low similarity ratio under cold start) and "señoritera" (bypassed due to alias match).
    - Avoid using any sequence matcher mocks to ensure rigid, realistic test logic.
  </action>
  <verify>./.venv/bin/pytest tests/test_drift_alias_bypass.py</verify>
  <done>The test suite is created and executes successfully assert-checking the bypass and blocking logic.</done>
</task>

<task type="auto">
  <name>Verify coherence score and GSD state update</name>
  <files>
    <file>.planning/STATE.md</file>
  </files>
  <action>
    - Run npx agent-cli eval to verify score is 1.000 (all tests passing).
    - Update .planning/STATE.md and .planning/ROADMAP.md with completion of quick task 113.
  </action>
  <verify>npx agent-cli eval</verify>
  <done>All tests pass, score is 1.000, and GSD documents are updated.</done>
</task>

---
*Created: 2026-07-05*
