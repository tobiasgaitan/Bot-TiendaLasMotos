# Project State

## Current Position
**Phase:** Quick Task 033 - Catalog Price Bonus Fix (BOT-BE-53).
**Status:** Done (1.000 Coherence Score achieved, 97/97 tests passed).
**Last activity:** Resolver colisión de nomenclatura y agregar bonos de contado en CatalogService (BOT-BE-53).

| Decision | Phase | Source | Rationale |
|----------|-------|--------|-----------|
| Serialization Lock | Tarea 4.3 | Auditor | Prohibir el uso de .get() sin logs forenses en llaves requeridas por el LLM. |
| Similitud Cadenas > 0.85 | Init | User | Evitar llamadas de red y latencia de embeddings externos. Uso de TF-IDF/Levenshtein puro. |
| RAM Hydration | Init | User | Almacenamiento 100% en memoria para cero I/O disk calls. |
| Formato Markdown Strict | Init | User | Cache devuelve directamente el bloque visual (PCC Pro) y no un objeto JSON. |

### Blockers/Concerns
None

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 029 | Fix specs serialization by using pre-summarized summary | 2026-05-16 | fb09334 | 029-fix-specs-serialization |
| 031 | Align search_catalog with search_items and avoid UnboundLocalError | 2026-05-17 | e9eb5dc | 031-hotfix-ai-brain-alignment |
| 032 | Corregir sintaxis de COPY en Dockerfile e instalar git | 2026-05-17 | 7c7769d | 032-corregir-sintaxis-dockerfile |
| 033 | Fallo crítico de colisión de nomenclatura y bonos de contado en CatalogService | 2026-05-18 | e8f18fa | 033-catalog-price-bonus-fix |

---
*Last updated: 2026-05-18*