# Project State
## Current Position
**Last Activity:** 2026-05-14 — BOT-DB-4.3-FIX: Normalización final 60/60 y optimización de Recall [EXITOSO].
**Last Activity (Hotfixes v9.9.1):** 2026-05-15 — Validación End-to-End exitosa. Se lograron 3 hitos críticos:n1. **Contrato de Interfaz:** Patrón adaptador en `CatalogService` para compatibilidad AI/Router.n2. **Estabilidad de Router:** Fix de `UnboundLocalError` (Scope del módulo `re`) en `whatsapp.py`.n3. **Calibración de Juez:** Flexibilización de la regla C5 (One-Question-Rule) a máximo 2 para permitir saludos naturales sin falsos positivos.n
**Last Activity:** 2026-05-14 — BOT-BE-4.2: Simplificación de CatalogService y Blindaje PCC-GUARD [CERTIFICADO].
**Last Activity (Hotfixes v9.9.1):** 2026-05-15 — Validación End-to-End exitosa. Se lograron 3 hitos críticos:n1. **Contrato de Interfaz:** Patrón adaptador en `CatalogService` para compatibilidad AI/Router.n2. **Estabilidad de Router:** Fix de `UnboundLocalError` (Scope del módulo `re`) en `whatsapp.py`.n3. **Calibración de Juez:** Flexibilización de la regla C5 (One-Question-Rule) a máximo 2 para permitir saludos naturales sin falsos positivos.n
**Last Activity:** 2026-05-14 — BOT-DB-4.3: Normalización imagen_url (8 docs corregidos) [APROBADO].
**Last Activity (Hotfixes v9.9.1):** 2026-05-15 — Validación End-to-End exitosa. Se lograron 3 hitos críticos:n1. **Contrato de Interfaz:** Patrón adaptador en `CatalogService` para compatibilidad AI/Router.n2. **Estabilidad de Router:** Fix de `UnboundLocalError` (Scope del módulo `re`) en `whatsapp.py`.n3. **Calibración de Juez:** Flexibilización de la regla C5 (One-Question-Rule) a máximo 2 para permitir saludos naturales sin falsos positivos.n
**Phase:** 1 — Agente Único
**Status:** COMPLETED (v9.9.0 Certified)
**Last activity:** 2026-05-14 — BOT-BUG-2.1: JudgeService C2 real parity validation + ScoringService word-boundary fix (commit 2a91c11).

## Key Decisions
| Decision | Phase | Rationale |
|----------|-------|-----------|
| Agente Único Centralizado | 1 | Elimina latencia de triaje y asegura contexto total en Juan Pablo. |
| Persistencia Lineal Bloqueante | Init | Garantiza integridad en Firestore (v9.6.0). |
| Cognitive Brakes (Anti-Placeholder) | 1 | Elimina emisión de $X.XXX al usuario. Guardrail regex + omisión condicional de cuota. |
| Langfuse Observability (@observe) | 1 | userId=phone (E.164), funnel_phase tags, search_catalog latency, token cost per generation. |
| Unificación search_catalog | 1 | Interfaz única para catálogo y auditoría (v9.9.0). |

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 021 | Cognitive Brakes & Placeholder Sanitization | 2026-05-10 | 994ed3b | 021-cognitive-brakes-tool-calling |
| 022 | Langfuse Observability Integration (BOT-TRACE-201) | 2026-05-11 | befe140 | 022-langfuse-observability-integration |
| 023 | Unificación Financiera & Paridad v1.4.0 (Apache 160 Fix) | 2026-05-11 | 40312c7 | 023-financial-refactor-unification |
| 024 | Sync Docs v9.9.0 & Forensic Audit | 2026-05-13 | [current] | 024-sync-docs-v9.9.0 |
| 025 | BOT-BUG-2.1: JudgeService C2 Parity + Scoring Word-Boundary | 2026-05-14 | 2a91c11 | 025-bot-bug-2.1-judge-parity-fix |

### Historical Critical Commits (v9.9.0 Sync)
- `bc6e8e4`: fix(catalog): surgical rename of search to search_catalog and unification of references.
- `f0b825d`: refactor(memory): repair CRM memory tests and Firestore mocks.
