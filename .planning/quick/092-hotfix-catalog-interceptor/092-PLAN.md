---
task: 092
name: hotfix-catalog-interceptor
description: El interceptor de CatalogService bloquea las consultas debido a la desalineación de los scores de similitud de difflib cuando la instrucción interna del parámetro de la herramienta traduce un término coloquial a categorías genéricas (ej. de 'señoritera' a 'scooter'), generando un retorno vacío que rompe el payload de la API de Meta y provoca tormentas de reintentos duplicados.
---

# Quick Task 092: hotfix-catalog-interceptor

## Objective
Implement token synonym expansion and fallback checks in `CatalogService.search_items` to ensure search queries (especially category translations like 'scooter' or 'señoritera') never return empty results or propagate null/empty strings to `ai_brain.py`.

## Tasks

<task type="auto">
  <name>Implement Token Synonym Expansion and Fallback in search_items</name>
  <files>app/services/catalog_service.py</files>
  <action>
    - Add colloquial synonym mapping for category terms (scooter -> moped, etc.) to query tokens.
    - Add a token-overlap fallback loop in `search_items` if standard scoring results in no matches.
    - Ensure default catalog items are returned if the list remains empty.
    - Set fallback non-empty values for required fields (name, price, summary, image_url) to protect against null masking in `ai_brain.py`.
  </action>
  <verify>uv run pytest tests/test_pcc_ficha_tecnica.py</verify>
  <done>Tests pass and search_items is guaranteed to never return empty/null/incomplete items.</done>
</task>

---
*Created: 2026-07-02*
