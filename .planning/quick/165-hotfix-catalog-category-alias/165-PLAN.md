---
task: 165
name: Hotfix Catalog Category Alias Recovery
description: Fix category aliases matching in CatalogService.search_items
---

# Quick Task 165: Hotfix Catalog Category Alias Recovery

## Objective
Restore search capabilities for commercial category styles (aliases) in `CatalogService.search_items` by mapping them to canonical categories during pre-processing, preventing the strict alphabetic/numeric filter from discarding them.

## Tasks

<task type="auto">
  <name>Modify CatalogService.search_items to map category aliases</name>
  <files>app/services/catalog_service.py</files>
  <action>Add a check in the pre-processing phase of search_items that matches clean query tokens against the dictionary of category aliases from get_catalog_aliases(). If a match is found, map the token to its canonical category name, adding it to the search tokens and query alphabetic tokens list to pass the perimeter validation check.</action>
  <verify>.venv/bin/pytest tests/test_catalog_fuzzy.py</verify>
  <done>CatalogService correctly resolves alias queries like "pistera" without returning an empty list.</done>
</task>

<task type="auto">
  <name>Add characterization unit test to test_agentic_loop_async.py</name>
  <files>tests/test_agentic_loop_async.py</files>
  <action>Add a test case in tests/test_agentic_loop_async.py that queries using the 'pisteras' alias, asserts that it resolves to 'Deportiva' and does not return empty.</action>
  <verify>.venv/bin/pytest tests/test_agentic_loop_async.py -k test_catalog_category_alias_recovery</verify>
  <done>The new test case passes successfully.</done>
</task>

---
*Created: 2026-07-12*
