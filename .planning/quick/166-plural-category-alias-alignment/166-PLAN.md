---
task: 166
name: Align Category Aliases in Plural and Diminutive
description: Hotfix for plural/diminutive alias containment alignment in CatalogService search_items.
---

# Quick Task 166: Align Category Aliases in Plural and Diminutive

## Objective
Refactor the category alias matching logic in CatalogService.search_items to use flexible substring/token containment, ensuring plural and diminutive queries successfully map to their canonical categories while maintaining perimeter rules.

## Tasks

<task type="auto">
  <name>Refactor Category Alias Containment Check</name>
  <files>app/services/catalog_service.py</files>
  <action>Modify search_items in app/services/catalog_service.py to perform flexible substring/containment mapping between user query tokens and category aliases, checking both directions (a_clean in t_clean or t_clean in a_clean) only if the alias length (len(a_clean)) is at least 3 characters.</action>
  <verify>.venv/bin/pytest tests/test_agentic_loop_async.py -k test_catalog_category_alias_recovery</verify>
  <done>Code handles plural and diminutive aliases correctly, and the specific test passes.</done>
</task>

<task type="auto">
  <name>Rewrite Alias Recovery Test</name>
  <files>tests/test_agentic_loop_async.py</files>
  <action>Update test_catalog_category_alias_recovery in tests/test_agentic_loop_async.py to configure aliases in singular only and run assertions against multiple user query variations including plural ('pisteras'), diminutive ('pisteritas'), and plural synonym ('scooters') against singular configured aliases.</action>
  <verify>.venv/bin/pytest tests/test_agentic_loop_async.py -k test_catalog_category_alias_recovery</verify>
  <done>Test asserts correct category mapping for various linguistic mutations and passes without false positives.</done>
</task>

<task type="auto">
  <name>Validate Coherence Score</name>
  <files></files>
  <action>Run the full evaluation suite with npx agent-cli eval to verify no regressions and maintain a coherence score of 1.000.</action>
  <verify>npx agent-cli eval</verify>
  <done>Coherence Score is 1.000 and all tests pass.</done>
</task>
