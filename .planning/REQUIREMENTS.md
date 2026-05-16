# Requirements

## Overview
Requerimientos técnicos para la implementación de la Caché Semántica en `CatalogService`.

## V1 — Must Have
These are table stakes. The product doesn't work without them.

| ID | Requirement | Phase | Status |
|----|-------------|-------|--------|
| R1 | Crear `semantic_cache_service.py` con almacenamiento 100% en memoria RAM (sin JSON en disco), hidratado sincrónicamente en el arranque. | 1 | Planned |
| R2 | Motor de similitud en Python puro (TF-IDF ligero / N-gramas / Levenshtein) para comparar texto sin red externa (prohibido Gemini Embeddings). | 1 | Planned |
| R3 | Interceptar búsqueda en `CatalogService` para evaluar hit de caché. | 2 | Planned |
| R4 | El Hit de caché debe retornar directamente el bloque Markdown final con la imagen y el precio, preservando estricto el formato comercial. | 2 | Planned |
| R5 | Validar con `get_neighbors` que `ai_brain.py` no sufre daño colateral. | 2 | Planned |
| R6 | Escribir tests unitarios probando variaciones tipográficas. | 2 | Planned |

---
*Last updated: 2026-05-16*