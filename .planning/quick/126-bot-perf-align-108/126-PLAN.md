---
task: 126
name: bot-perf-align-108
description: Normalizar formato Ficha Tecnica en el formateador de catálogo y revertir flexibilización de regex en el orquestador
---

# Quick Task 126: Align Ficha Tecnica Format

## Objective
Remove leading spaces from the Ficha Tecnica formatter in `app/services/ai_brain.py` line 1354 and restore the rigid validation in `AgenticOrchestrator` to align with the historical unit test asserts without changing the tests.

## Tasks

<task type="auto">
  <name>Align catalog response formatting in ai_brain.py</name>
  <files>[app/services/ai_brain.py, app/services/catalog_service.py]</files>
  <action>Remove two leading spaces from the "  Ficha Tecnica:" literal on line 1354 of ai_brain.py, changing it to "Ficha Tecnica:". Also do the same in catalog_service.py line 635 to maintain consistency across catalog formatting.</action>
  <verify>npx agent-cli eval</verify>
  <done>The spaces are removed, and tests pass.</done>
</task>

<task type="auto">
  <name>Revert flexibilization in AgenticOrchestrator</name>
  <files>[app/services/agentic_loop_service.py]</files>
  <action>Restore the rigid checker regex/logic in agentic_loop_service.py by changing the check back to `has_ficha = "Ficha Tecnica:" in bot_response if is_catalog_query else True`.</action>
  <verify>npx agent-cli eval</verify>
  <done>The flexibilized regex has been removed and the simple string membership check is restored; all tests pass.</done>
</task>

---
*Created: 2026-07-06*
