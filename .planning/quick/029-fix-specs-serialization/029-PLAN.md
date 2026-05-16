---
task: 029
name: Fix Specs Serialization
description: Falso positivo en optimización de Tarea 4.3. La función _summarize fue integrada en la creación del diccionario temporal (línea 466), pero el pipeline de serialización de texto hacia el LLM (línea 508) sigue inyectando el objeto m['specs'] en estado crudo, provocando Context Bloat.
---

# Quick Task 029: Fix Specs Serialization

## Objective
Surgically replace the raw key reference `m.get('specs')` at line 508 in `app/services/catalog_service.py` with `m.get('summary')` to properly inject the pre-summarized 10-word description into the Gemini context, eliminating the silent false positive and reducing prompt size.

## Tasks

<task type="auto">
  <name>Surgically edit catalog_service.py</name>
  <files>app/services/catalog_service.py</files>
  <action>Replace `m.get('specs')` and `self._summarize(m['specs'])` with `m.get('summary')` and `m['summary']` respectively.</action>
  <verify>.venv/bin/pytest and npx agent-cli eval</verify>
  <done>The test suite passes with a coherence score of 1.000, and catalog serialization correctly outputs the pre-summarized specs (summary).</done>
</task>

---
*Created: 2026-05-16*
