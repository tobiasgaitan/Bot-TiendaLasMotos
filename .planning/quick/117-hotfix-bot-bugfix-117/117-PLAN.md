---
task: 117
name: hotfix-bot-bugfix-117
description: El interceptor léxico 'motorcycle_keywords' está hardcodeado, desincronizado y no intercepta alias regionales, permitiendo al LLM saltarse la herramienta 'search_catalog' en Cold Start.
---

# Quick Task 117: hotfix-bot-bugfix-117

## Objective
Refactor `ai_brain.py` to build the `motorcycle_keywords` list dynamically by importing `config_service` and merging the keys and synonyms returned by `config_service.get_catalog_aliases()` with the base keywords. Create an integration test validating that pure alias queries invoke `search_catalog` and return validation failures when missing the technical specifications sheet.

## Tasks

<task type="auto">
  <name>Refactor motorcycle_keywords in ai_brain.py</name>
  <files>app/services/ai_brain.py</files>
  <action>Import config_service and update process_message_async/validation-turn to build motorcycle_keywords dynamically by adding config_service.get_catalog_aliases() keys and values to the base keywords.</action>
  <verify>.venv/bin/pytest tests/test_agentic_loop_async.py</verify>
  <done>The motorcycle_keywords array contains both base keywords and dynamic aliases/categories, verified by passing existing tests.</done>
</task>

<task type="auto">
  <name>Implement Integration Test for Alias-based Catalog Tool Call Verification</name>
  <files>tests/test_agentic_loop_async.py</files>
  <action>Add a new integration test test_alias_pure_catalog_invocation asserting that 'señoritera' triggers search_catalog and fails validation (returning success: False) when 'Ficha Tecnica:' is missing.</action>
  <verify>.venv/bin/pytest tests/test_agentic_loop_async.py</verify>
  <done>The test executes successfully and proves the regression is fixed with a 1.000 coherence score.</done>
</task>
