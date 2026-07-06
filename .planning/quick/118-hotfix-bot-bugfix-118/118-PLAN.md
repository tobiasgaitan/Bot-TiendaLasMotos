---
task: 118
name: hotfix-bot-bugfix-118
description: Drift Interceptor alias literal validation failure on compuesto/conectores.
---

# Quick Task 118: hotfix-bot-bugfix-118

## Objective
Refactor the alias validation loop inside CerebroIA._is_synonym_or_model_match in app/services/ai_brain.py to check if the synonym is contained in the prospect interest (moto_interest) or vice versa (e.g., syn in m or m in syn) instead of strict equality. Update tests/test_drift_alias_bypass.py to include a test case where prospect interest is 'moto señoritera' and the search query is 'semiautomatica', asserting that the Drift Interceptor bypasses and allows the catalog search.

## Tasks

<task type="auto">
  <name>Refactor _is_synonym_or_model_match in ai_brain.py</name>
  <files>app/services/ai_brain.py</files>
  <action>Modify the regional synonym matching block in CerebroIA._is_synonym_or_model_match to use 'syn in m or m in syn' for synonym checking</action>
  <verify>.venv/bin/pytest tests/test_drift_alias_bypass.py</verify>
  <done>Regional synonym checks allow matches when containing synonyms (e.g., 'señoritera' matching 'moto señoritera')</done>
</task>

<task type="auto">
  <name>Add test assertion in test_drift_alias_bypass.py</name>
  <files>tests/test_drift_alias_bypass.py</files>
  <action>Add a test case/assertion checking that when prospect interest is 'moto señoritera' and query is 'semiautomatica', the bypass is allowed and search_items is called</action>
  <verify>.venv/bin/pytest tests/test_drift_alias_bypass.py</verify>
  <done>All tests in test_drift_alias_bypass.py pass, including the new assertion</done>
</task>

---
*Created: 2026-07-05*
