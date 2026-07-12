---
task: 168
name: Conversational Stopword Stripping Hotfix
description: Hotfix to strip conversational noise tokens from query_alphabetic_tokens in CatalogService.search_items
---

# Quick Task 168: Conversational Stopword Stripping Hotfix

## Objective
Strip common Spanish conversational greeting, courtesy, and commerce verbs (such as 'buenas', 'hola', 'tiene', 'manejan') from `query_alphabetic_tokens` in `CatalogService.search_items` to prevent false negatives in the perimetral validation loop (has_alphabetic_match).

## Tasks

<task type="auto">
  <name>Implement Conversational Stopword Stripping</name>
  <files>app/services/catalog_service.py</files>
  <action>Define _CONVERSATIONAL_STOPWORDS containing courtesy words, greetings, and interaction verbs, and strip them from query_alphabetic_tokens immediately after the commercial stopword stripping.</action>
  <verify>.venv/bin/pytest tests/test_agentic_loop_async.py -k test_catalog_generic_stopword_stripping</verify>
  <done>CatalogService._CONVERSATIONAL_STOPWORDS is defined and query_alphabetic_tokens is filtered, permitting conversational search queries to return correct catalog items.</done>
</task>

<task type="auto">
  <name>Expand Test Suite</name>
  <files>tests/test_agentic_loop_async.py</files>
  <action>Modify test_catalog_generic_stopword_stripping to include conversational query tests: 'Buenas, tienen motos pisteras?' and 'Hola, manejan motos scooters?'. Assert they return expected bikes ('TVS Raider 125' and 'TVS Ntorq 125' respectively).</action>
  <verify>.venv/bin/pytest tests/test_agentic_loop_async.py -k test_catalog_generic_stopword_stripping</verify>
  <done>test_catalog_generic_stopword_stripping correctly verifies that conversational queries are successfully stripped of noise and return correct bikes.</done>
</task>

---
*Created: 2026-07-12*
