---
task: 131
name: Inject Phonetic Normalization
description: Inyectar la normalización fonética y mapeo de sinónimos tipográficos ('rayder' -> 'raider') en el servicio de catálogo.
---

# Quick Task 131: Inject Phonetic Normalization

## Objective
Implement a spelling correction map and a secondary phonetic/homophone normalization in `CatalogService` to ensure queries with user typographical variations like "rayder" successfully match against target models like "TVS Raider 125" and trigger the appropriate scoring boosts.

## Tasks

<task type="auto">
  <name>Implement Spelling Map and Phonetic Normalization in CatalogService</name>
  <files>app/services/catalog_service.py</files>
  <action>Add spelling_map and _phonetic_normalize helper method, and integrate them into search_items matching logic (identity match and token overlap).</action>
  <verify>.venv/bin/pytest tests/test_catalog_scoring.py</verify>
  <done>spelling corrections and phonetic matches are integrated and existing catalog tests pass.</done>
</task>

<task type="auto">
  <name>Create Unit Test for Fuzzy Catalog Matches</name>
  <files>tests/test_catalog_fuzzy.py</files>
  <action>Create a new test file tests/test_catalog_fuzzy.py asserting that queries like 'rayder' retrieve 'TVS Raider 125'.</action>
  <verify>.venv/bin/pytest tests/test_catalog_fuzzy.py</verify>
  <done>tests/test_catalog_fuzzy.py is created and passes successfully.</done>
</task>
