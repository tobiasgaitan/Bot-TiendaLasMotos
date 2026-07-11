---
task: 163
name: Catalog Search Threshold Calibration
description: Modify CatalogService.search_items to enforce that queries with alphabetic/text tokens (length >= 2) must match at least one of those tokens (exactly or phonetically) in the item name or searchBy tags. If there is zero alphabetical match, the score is forced to 0.
---

# Quick Task 163: Catalog Search Threshold Calibration

## Objective
Prevent false positive matches in `CatalogService.search_items` (e.g. "Milan 150" or "CR4 150" returning "Victory MRX 150 Trakku") by requiring that any search containing alphabetical tokens of length >= 2 must have at least one exact or phonetic match in the item's name or `searchBy` tags.

## Tasks

<task type="auto">
  <name>Implement strict alphabetic perimeter validation in CatalogService.search_items</name>
  <files>
    <file>app/services/catalog_service.py</file>
  </files>
  <action>
    Modify `app/services/catalog_service.py` to extract core query alphabetical/text tokens (length >= 2, not purely numeric). If such tokens exist, verify if at least one matches (exactly or phonetically) the item's name (tokenized) or its `searchBy` tags. If not, set the score for this item to 0 so it is excluded from search results.
  </action>
  <verify>
    .venv/bin/pytest tests/test_catalog_scoring.py tests/test_catalog_fuzzy.py
  </verify>
  <done>
    Unit tests pass, and existing tests maintain 100% compliance.
  </done>
</task>

<task type="auto">
  <name>Create regression unit tests for Milan 150 and CR4 150 empty results</name>
  <files>
    <file>tests/test_catalog_scoring.py</file>
  </files>
  <action>
    Add a new unit test `test_numeric_collision_prevention` in `tests/test_catalog_scoring.py` to assert that searches for "Milan 150" and "CR4 150" return an empty list of results, and verify that pure displacement searches like "100" or "125" still return relevant matching models (like TVS Sport 100 or TVS Raider 125).
  </action>
  <verify>
    .venv/bin/pytest tests/test_catalog_scoring.py
  </verify>
  <done>
    New regression tests pass successfully.
  </done>
</task>

---
*Created: 2026-07-11*
