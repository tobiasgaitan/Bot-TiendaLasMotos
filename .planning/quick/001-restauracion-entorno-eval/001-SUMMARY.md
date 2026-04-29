# Quick Task 001: Restauracion Entorno y Eval — Summary

**Ejecutado:** 2026-04-29
**Ticket:** BOT-CORE-770-EVAL
**Status:** COMPLETADO CON HALLAZGOS CRÍTICOS

---

## ════════════════════════════════════════════════════
## REPORTE DE EVALUACIÓN — VOLCADO EXACTO DE TERMINAL
## ════════════════════════════════════════════════════

```
============================= test session starts ==============================
platform darwin -- Python 3.14.4, pytest-9.0.3, pluggy-1.6.0
rootdir: /Users/tobiasgaitangallego/Bot-TiendaLasMotos
plugins: asyncio-1.3.0
asyncio: mode=Mode.STRICT

collected 25 items / 7 errors (primera ejecución — sin dependencias)
→ Resuelto instalando requirements.txt en .venv

Segunda ejecución (con dependencias completas):
collected 46 items

FAILED tests/test_ai_adapter.py::test_case_2_short_message_with_anchor
FAILED tests/test_campaign_admin.py::test_campaign_orchestrator_failure_isolation
FAILED tests/test_habeas_data_regression.py::TestHabeasDataRegression::test_phase_allowed_with_sent_and_accepted
FAILED tests/test_habeas_data_regression.py::TestHabeasDataRegression::test_phase_block_without_physical_link
FAILED tests/test_memory_merge.py::test_merge_strategy_latch_true_only
FAILED tests/test_memory_merge.py::test_merge_strategy_pop_destructive
FAILED tests/test_price_consolidation.py::test_price_consolidation
FAILED tests/test_proactive_credit.py::TestProactiveCredit::test_deterministic_insurance_fallback
FAILED tests/test_read_asymmetry.py::test_template_sanitization_initialization
FAILED tests/test_read_asymmetry.py::test_reverse_mapping_retrieval
FAILED tests/test_read_asymmetry.py::test_collision_neutralization_priority
FAILED tests/test_reset_flow.py::test_create_prospect_initializes_habeas_data_false
FAILED tests/test_reset_flow.py::test_merge_still_latches_true_if_already_true

================== 13 failed, 33 passed, 5 warnings in 2.91s ==================
```

---

## Score de Coherencia

| Métrica | Valor |
|---------|-------|
| Tests pasados | 33 / 46 |
| Score RAW | **0.717** |
| Umbral requerido | ≥ 0.9 |
| Estado despliegue | ⛔ **BLOQUEADO** |

---

## Diagnóstico Forense de Fallos

### 🔴 Categoría A — Regresión de Nomenclatura (Naming Lock)

**Archivo:** `tests/test_memory_merge.py`
**Error:** `KeyError: 'habeasData'`
**Causa confirmada:** El refactor b4471b3 renombró la llave `habeasData` → `habeas_data_accepted`
en el MemoryService pero los tests usan el nombre antiguo. Es una **Regresión de Nomenclatura**
según el MANDATO de Key Alignment del proyecto.

**Tests afectados:**
- `test_merge_strategy_latch_true_only`
- `test_merge_strategy_pop_destructive`
- `test_reset_flow::test_merge_still_latches_true_if_already_true`

---

### 🔴 Categoría B — Contrato de API Roto (God Node ai_brain)

**Archivo:** `tests/test_habeas_data_regression.py`
**Error:** `AttributeError: type object 'obj' has no attribute 'get'`
**Causa confirmada:** `_determine_funnel_phase(prospect_data, history=[...])` espera
`history` como `List[dict]` con keys `"role"` y `"content"`, pero el refactor
introdujo objetos Pydantic `obj` en lugar de dicts planos. El test pasa dicts limpios
pero la función interna opera sobre objetos tipados.

**Tests afectados:**
- `test_phase_block_without_physical_link`
- `test_phase_allowed_with_sent_and_accepted`

---

### 🔴 Categoría C — Método Eliminado (MemoryService)

**Archivo:** `tests/test_read_asymmetry.py`
**Error:** `AttributeError: '_get_prospect_data_sync'. Did you mean: 'get_prospect_data'?`
**Causa confirmada:** El refactor eliminó el método `_get_prospect_data_sync` del MemoryService.
Los tests de asimetría de lectura lo referencian directamente. Requiere deprecación explícita
o adaptador de compatibilidad.

---

### 🟡 Categoría D — Tests de Infraestructura (No bloquean lógica core)

- `test_campaign_admin::test_campaign_orchestrator_failure_isolation` → `async def` sin modo asyncio configurado
- `test_price_consolidation::test_price_consolidation` → Idem
- `test_read_asymmetry::test_template_sanitization` → `coroutine 'create_prospect_if_missing' was never awaited`
- `test_proactive_credit::test_deterministic_insurance_fallback` → `seguro_vida: 0.0 != 15000` (fallback numérico roto)

---

## Qué Fue Verificado

| Ítem | Estado |
|------|--------|
| Permisos npm cache (EACCES root) | ✅ Diagnosticado — requiere `sudo chown` (pendiente aprobación usuario) |
| Entorno CLI `agent-cli` | ✅ Confirmado: no es paquete npm público (404). `.agent/` solo contiene `VERSION` y `workflows/` |
| `.planning/STATE.md` creado | ✅ |
| `.planning/ROADMAP.md` creado | ✅ |
| Suite pytest ejecutada | ✅ — 33 passed / 13 failed |
| Requirements instalados en venv | ✅ |
| God Nodes auditados (ai_brain, whatsapp, memory_service) | ✅ — 3 regresiones activas detectadas |

---

## Acción Requerida del Auditor (Tobias)

1. **Aprobar** `sudo chown -R $(whoami) ~/.npm` para reparar los permisos EACCES
2. **Autorizar** ticket de seguimiento para reparar las **13 regresiones** antes de autorizar deploy a Beta

---
*Completado: 2026-04-29 | Quick Task 001*
