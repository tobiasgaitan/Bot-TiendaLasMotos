---
task: 030
name: Fix Anti-Null Masking Catalog
description: Falso positivo por Enmascaramiento Nulo (Anti-Null Masking Fault) en la frontera de sincronización entre ai_brain.py y catalog_service.py. El orquestador de IA consume la herramienta de catálogo asumiendo el retorno de un objeto estructorado y buscando la llave inexistente 'raw_price', mientras que el método físico real devuelve un string Markdown, enviando las excepciones a un bloque try-except tolerante que oculta la desaparición de la línea de cuotas del Paso 5.
---

# Quick Task 030: Fix Anti-Null Masking Catalog

## Objective
Refactor the tool execution loop in `app/services/ai_brain.py` (specifically within the `calculate_credit_score` tool resolution) to consume `catalog_service.search_items(moto_name)` instead of the markdown-returning `search_catalog(moto_name)`. Align keys with the immutable `price` field needed by `financial_service.py` by attempting to extract `raw_price` and fallback to `price` (parsing it if it's a string), and ensure the technical sheet summary persists under the `"Ficha Tecnica:"` label. Write a robust pytest assertion to verify this behavior and prevent regression.

## Tasks

<task type="auto">
  <name>Surgically edit ai_brain.py</name>
  <files>app/services/ai_brain.py</files>
  <action>Change `search_catalog(moto_name)` to `search_items(moto_name)` under `calculate_credit_score` resolution. Add robust numeric price retrieval mapping to both raw_price and price, fallback-safe with string parsing.</action>
  <verify>.venv/bin/pytest and npx agent-cli eval</verify>
  <done>ai_brain.py compiles and correctly retrieves numeric price, preventing silent try-except silencing of credit cuota simulation.</done>
</task>

<task type="auto">
  <name>Write unit test in tests/test_perf_45.py</name>
  <files>tests/test_perf_45.py</files>
  <action>Create a unit test asserting that the tool resolution loop for calculate_credit_score extracts raw_price, executes simulated credit successfully, and contains the required "Ficha Tecnica:" and disclaimer format, throwing explicit errors if intermediate keys mutate to empty/None values.</action>
  <verify>.venv/bin/pytest tests/test_perf_45.py</verify>
  <done>Pytest verifies that the credit flow outputs simulated cuotas with perfect key alignment and explicit errors on null masking.</done>
</task>

---
*Created: 2026-05-16*
