# ROADMAP — BOT-STRUC-765-EVOLUTION

## Epic: Refactorización Arquitectural de God Nodes

**Objetivo:** Desacoplar `ai_brain.py` / `whatsapp.py` extrayendo lógica de precios, telemetría
y medios a servicios especializados. Estandarizar el EXTRACTION_SCHEMA y reintegrar SurveyService.

---

## Fase 1 — Refactorización God Nodes [✅ COMPLETADA]

| Item | Estado | Commit |
|------|--------|--------|
| Extraer ConfigService / StorageService | ✅ Done | b4471b3 |
| EXTRACTION_SCHEMA global | ✅ Done | b4471b3 |
| HTTP error observability | ✅ Done | b4471b3 |
| Webhook status tracking | ✅ Done | b210e76 |
| Phone normalization status | ✅ Done | 2990ef7 |

## Fase 2 — Naming Lock & Contrato de Tests [🔴 BLOQUEADA]

**Prerequisito:** Resolver las 13 regresiones identificadas en BOT-CORE-770-EVAL.

| Item | Prioridad | Categoría |
|------|-----------|-----------|
| Alinear `habeasData` → `habeas_data_accepted` en test_memory_merge | CRÍTICA | A |
| Reparar `_determine_funnel_phase` — objetos Pydantic vs dicts | CRÍTICA | B |
| Reparar o deprecar `_get_prospect_data_sync` | CRÍTICA | C |
| Configurar `pytest-asyncio` mode=auto | MEDIA | D |
| Fix fallback seguro_vida en MotorFinanciero | MEDIA | D |

## Fase 3 — Despliegue Beta & Certificación

**Prerequisito:** Score coherencia ≥ 0.9 en `npx agent-cli eval` o equivalente pytest.

---
*Generado: 2026-04-29 | BOT-CORE-770-EVAL*
