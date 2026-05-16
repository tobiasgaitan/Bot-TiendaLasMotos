---
task: 028
name: Compress Catalog Specs
description: Inflación severa de tokens y sobrecarga de ventana de contexto en ai_brain.py provocada por la serialización masiva del campo 'specs' en la línea 508 de catalog_service.py.
---

# Quick Task 028: Compress Catalog Specs

## Objective
Compress the output of the 'specs' field in `search_catalog` to a maximum of 10 words using the `_summarize` method, mitigating token inflation while preserving 'price' and 'image_url' for the PCC Pro Protocol.

## Tasks

<task type="auto">
  <name>Surgically Edit catalog_service.py</name>
  <files>app/services/catalog_service.py</files>
  <action>Wrap the 'specs' field with `self._summarize(m['specs'])` at line 508.</action>
  <verify>npx agent-cli eval</verify>
  <done>Evaluation passes the REGLA_DE_VISUALES without context overload.</done>
</task>

---
*Created: 2026-05-16*
