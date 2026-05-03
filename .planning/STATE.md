# Project State — BOT-STRUC-765-EVOLUTION

**Project:** Bot TiendaLasMotos — Refactoring God Nodes & Schema Standardization
**Ticket principal:** BOT-STRUC-765-EVOLUTION
**Rama activa:** beta
**Último commit:** a9c69a9 — `fix(cicd): decouple IAM policy binding from agents-cli orchestrator`

## Estado Actual

| Campo | Valor |
|-------|-------|
| Fase activa | Sección 11: Despliegue Final |
| Rama | beta |
| Último deploy | ee41c2a (beta) |
| Test suite | 53 PASSED / 0 FAILED |
| Score Coherencia | 1.000 (CERTIFICADO ✅) |
| CI/CD Status | STABLE ✅ (100% Completed) |

## Quick Tasks Completed

| # | Descripción | Fecha | Commit | Directorio |
|---|-------------|-------|--------|------------|
| 001 | Restauracion Entorno y Eval (BOT-CORE-770-EVAL) | 2026-04-29 | pendiente | 001-restauracion-entorno-eval |
| 003 | CLI Environment Isolation | 2026-04-29 | c120cc0 | 003-cli-isolation |
| 005 | Fix Test Regressions (Phone & CC) | 2026-04-29 | 7f9c31f | 005-fix-test-regressions |
| 006 | Fix CICD UV Infrastructure | 2026-04-29 | 56b054a | 006-fix-cicd-uv |
| 007 | CI/CD Stabilization & ADK 2026 Sync | 2026-04-29 | a9c69a9 | 007-cicd-victory |
| 008 | Refactor Firestore Mocks & Fix Warnings | 2026-04-30 | 598710c | 008-refactor-firestore-mocks |
| 009 | Refactor Agent CLI Identity & Version Sync | 2026-05-02 | 9fb731b | 009-refactor-agent-cli-identity |
| 010 | Fix Hatchling Build & Sync | 2026-05-02 | ee41c2a | 010-fix-hatchling-build |
| 011 | Certify Environment Stability | 2026-05-03 | CURRENT | 011-certify-environment |
| 012 | Optimización de Mocks (Sección 10) | 2026-04-30 | 598710c | 008-refactor-firestore-mocks |

## Análisis de Fallos del Eval (BOT-CORE-770-EVAL)

### Categoría A — Regresión de Nomenclatura (Naming Lock) [SOLUCIONADO]
- `test_memory_merge` → `KeyError: 'habeasData'` (reparado en 010)
- `test_reset_flow::test_merge_still_latches_true` → (reparado en 010)

### Categoría B — Contrato de API Roto (God Node ai_brain) [SOLUCIONADO]
- `test_habeas_data_regression::test_phase_*` → reparado en 010

### Categoría C — Contrato de API Roto (MemoryService) [SOLUCIONADO]
- `test_read_asymmetry` → reparado en 010

### Categoría D — Tests de Infraestructura [SOLUCIONADO]
- `test_price_consolidation`, `test_campaign_admin` → reparado en 010
- `test_read_asymmetry::test_template_sanitization` → reparado en 010
- `test_proactive_credit::test_deterministic_insurance_fallback` → reparado en 010

## Score de Coherencia Certificado

```
Tests lógicos core: 53 PASSED / 53 total = 100%
SCORE ACTUAL: 1.000 — CERTIFICADO ✅
ESTADO: 🚀 LISTO PARA DESPLIEGUE A PRODUCCIÓN
```

## Registro de Victorias Recientes

### CI/CD Victory (Ticket BOT-DEBT-CICD-013 al 017)
- **Logro:** Estabilización del pipeline de despliegue automatizado hacia Cloud Run.
- **Lecciones Aprendidas:**
    - Se requiere el esquema estricto `[tool.agents-cli]` con `create_params` en `pyproject.toml` para compatibilidad con ADK 2026.
    - El orquestador `google-agents-cli v0.1.2` tiene limitaciones en la propagación de `EXTRA_ARGS`, por lo que se desacopló la política IAM pública a un paso nativo de `gcloud` en el workflow.

*Última actualización: 2026-05-03*

## Historial de Certificación (Audit Trail)

### 2026-05-03 — Certificación de Estabilidad Final
- **Score:** 1.000 (53/53 tests passed).
- **Acción:** Sincronización de `STATE.md` para reflejar la resolución de la regresión de construcción (Hatchling) y la migración de dependencias `uv`.
- **Estado:** Entorno local certificado como estable y listo para la fase de despliegue final.
- **Sección 10 (Optimización de Mocks):** Confirmada como completada (Task 012/008).
