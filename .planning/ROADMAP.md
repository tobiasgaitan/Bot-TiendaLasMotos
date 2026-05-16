# Roadmap

## Milestone 1: Caché Semántica de Catálogo

### Progress

| Phase | Name | Status | Plans | Date |
|-------|------|--------|-------|------|
| 1 | Arquitectura Core (Pure Python Math) | Completed | — | — |
| 2 | Intercepción en CatalogService y Pruebas | Completed | — | — |

### Phases

#### Phase 1: Arquitectura Core
**Goal:** Implementar `SemanticCacheService` capaz de usar algoritmos de similitud locales puros (N-gramas/Levenshtein) sobre un diccionario en RAM.
**Requirements:** R1, R3
- [x] Construir y testear similitud de cadenas sin dependencias externas.
- [x] Implementar hidratación síncrona en memoria.

#### Phase 2: Intercepción y Verificación PCC
**Goal:** Acoplar la caché en `CatalogService` de forma quirúrgica, manteniendo PCC y verificando con tests.
**Requirements:** R2, R4, R5
- [ ] Intercepción en `search_items`.
- [ ] Tests de variaciones tipográficas.
- [ ] Validación con `npx agent-cli eval`.

---
*Last updated: 2026-05-16*
