---
task: 121
name: hotfix-bot-judge-alignment
description: Stateless alignment of catalog context for the Judge Service in whatsapp.py
---

# Quick Task 121: hotfix-bot-judge-alignment

## Objective
Implement stateless alignment of catalog context for the Judge Service in `whatsapp.py`.
1) Translate the user's message body/transcription using `config_service.get_catalog_aliases()` before searching items.
2) Include both Firestore net price and total price (including SOAT/Matrícula) in the `catalog_context` string sent to the Judge.
3) Add a regression test in `tests/test_judge_alias_context.py` using 'Victory Advance X1' and aliases like 'señoritera'.

## Tasks

<task type="auto">
  <name>Implement stateless query translation and catalog_context construction in whatsapp.py</name>
  <files>[app/routers/whatsapp.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/routers/whatsapp.py)</files>
  <action>Add `resolve_query_aliases` helper and translate query before searching. Modify building of `catalog_context` to lookup original items in `catalog_service_local._items` and formatting it with both Neto and Con SOAT prices.</action>
  <verify>.venv/bin/pytest tests/test_zero_failures_whatsapp.py or similar</verify>
  <done>Query translation and catalog_context building are successfully implemented without mutating CerebroIA state.</done>
</task>

<task type="auto">
  <name>Develop regression test in tests/test_judge_alias_context.py</name>
  <files>[tests/test_judge_alias_context.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_judge_alias_context.py)</files>
  <action>Create a new test file validating synonym translation to category and checking that Judge evaluates using the correct category (e.g. Semiautomatica for 'señoritera') with both net and SOAT prices of Victory Advance X1.</action>
  <verify>.venv/bin/pytest tests/test_judge_alias_context.py</verify>
  <done>Test suite includes the regression test and runs successfully.</done>
</task>

---
*Created: 2026-07-06*
