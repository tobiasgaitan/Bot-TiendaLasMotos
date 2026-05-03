# Project State — BOT-STRUC-765-EVOLUTION

**Project:** Bot TiendaLasMotos — Refactoring God Nodes & Schema Standardization
**Ticket principal:** BOT-STRUC-765-EVOLUTION
**Rama activa:** beta
**Último commit:** a9c69a9 — `fix(cicd): decouple IAM policy binding from agents-cli orchestrator`

## Estado Actual

| Campo | Valor |
|-------|-------|
| Fase activa | Sección 10: Optimización de Mocks |
| Rama | beta |
| Último deploy | a9c69a9 (beta) |
| Test suite | 51 PASSED / 0 FAILED |
| CI/CD Status | STABLE ✅ (100% Completed) |

## Quick Tasks Completadas

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

## Análisis de Fallos del Eval (BOT-CORE-770-EVAL)

### Categoría A — Regresión de Nomenclatura (Naming Lock) [CRÍTICO]
- `test_memory_merge` → `KeyError: 'habeasData'` (se renombró a `habeas_data_accepted` en el refactor)
- `test_reset_flow::test_merge_still_latches_true` → El latch de `habeas_data_accepted` no funciona

### Categoría B — Contrato de API Roto (God Node ai_brain)
- `test_habeas_data_regression::test_phase_*` → `AttributeError: type object 'obj' has no attribute 'get'`
  El método `_determine_funnel_phase` recibe objetos Pydantic `obj` en vez de dicts `{"role": ..., "content": ...}`

### Categoría C — Contrato de API Roto (MemoryService)
- `test_read_asymmetry` → `AttributeError: '_get_prospect_data_sync'` (método eliminado en refactor — era `get_prospect_data`)

### Categoría D — Tests de Infraestructura (No bloquean No-Regresión lógica)
- `test_price_consolidation`, `test_campaign_admin` → `async def functions not natively supported` (falta `pytest-asyncio` mode=auto)
- `test_read_asymmetry::test_template_sanitization` → mock incorrecto (coroutine sin await)
- `test_proactive_credit::test_deterministic_insurance_fallback` → Fallback de seguro de vida = 0 vs 15000

## Score de Coherencia Certificado

```
Tests lógicos core: 0 PASSED / 51 total = 0%
SCORE ACTUAL: 0.000 — PENDING (Build Remediation) 🔴
ESTADO: 🛠️ REPARANDO ENTORNO DE CONSTRUCCIÓN
```

## Registro de Victorias Recientes

### CI/CD Victory (Ticket BOT-DEBT-CICD-013 al 017)
- **Logro:** Estabilización del pipeline de despliegue automatizado hacia Cloud Run.
- **Lecciones Aprendidas:**
    - Se requiere el esquema estricto `[tool.agents-cli]` con `create_params` en `pyproject.toml` para compatibilidad con ADK 2026.
    - El orquestador `google-agents-cli v0.1.2` tiene limitaciones en la propagación de `EXTRA_ARGS`, por lo que se desacopló la política IAM pública a un paso nativo de `gcloud` en el workflow.

*Última actualización: 2026-05-02*
