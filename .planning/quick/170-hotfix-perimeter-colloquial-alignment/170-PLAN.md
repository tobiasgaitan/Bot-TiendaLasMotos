---
task: 170
name: hotfix_perimeter_colloquial_alignment
description: Hotfix perimeter colloquial alignment
---

# Quick Task 170: hotfix_perimeter_colloquial_alignment

## Objective
Refactor the perimeter alphabetic validation loops in `CatalogService.search_items` to verify if at least one of the query tokens (original or expanded) maps successfully against the item's `search_tokens` in addition to `effective_tags` and `name_tokens`. This prevents false negatives when regional synonyms or expanded tokens are only present in the item's compiled search index.

## Tasks

<task type="auto">
  <name>Refactor perimeter validation loops in CatalogService</name>
  <files>app/services/catalog_service.py</files>
  <action>Update both perimeter validation loops in CatalogService.search_items to include matching against item's search_tokens</action>
  <verify>.venv/bin/pytest tests/test_agentic_loop_async.py</verify>
  <done>All tests passed including test_catalog_generic_stopword_stripping and a new characterization case</done>
</task>

---
*Created: 2026-07-12*
