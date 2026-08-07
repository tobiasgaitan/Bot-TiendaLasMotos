# Estado del Proyecto - Bot-TiendaLasMotos

Versión: v10.55.0 | Hito: BOT-BUILD-CLASSIFIER-011 — Clasificador con documento padre dominante + purge condicional | Coherence Score: 1.000 (695/695 Tests PASSED vía `npx agent-cli eval`)

### Current Position
**Phase:** BOT-BUILD-CLASSIFIER-011 (minor v10.55.0) — Corrección de la regresión de clasificación PHASE_1 con matriz completa y consentimiento latcheado — CERRADA (Success)
**Status:** Complete — Ejecución certificada contra el plan arquitectónico aprobado v1.0:
  - Fix A: `_determine_funnel_phase` en `app/services/ai_brain.py:946-1025` toma al documento padre como fuente primaria: `credit_intent = is_credit OR is_financial_intent OR habeas_data_accepted`; `consent_evidence = habeas_data_accepted_sent OR has_sent_link`. El historial queda como fallback (OR), no como requisito bloqueante.
  - Fix B: `MemoryService.create_prospect_if_missing` (`memory_service.py:514-516`) ejecuta `clear_memory` solo cuando el doc NO existe; se preserva el historial entre turnos para prospectos existentes y se mantiene la idempotencia de `/reset`.
  - Re-pin de `tests/test_habeas_data_regression.py::test_phase_block_without_physical_link` (PHASE_2→PHASE_3) con docstring de reconciliación.
  - Tests aditivos `tests/test_classifier_profiling_011.py` (5 ítems): PHASE_3 con padre completo + historial vacío, PHASE_3 con forma_pago vacante + habeas latch, PHASE_1 early-prospect + guardrail intacto, purge condicionado, no re-saludo.
  - Guardrail `ai_brain.py:2420-2431`, Vías A/B de AUD-CIERRE-RUTAS-010, personalidad, latches y espejos dashboard intactos.
  - Denominador canónico 690→695 (690 tests/ + 5 scripts/); 695/695 PASSED; 0 failed; 0 skipped. Coherence 1.000 — PUSH CONGELADO POR COND-4.

**Previous:** AUD-CIERRE-RUTAS-010 (v10.54.0) — Rediseño de la doctrina de CIERRE DE FASE con prioridad absoluta de bandas de score sobre `strategy` + gate gas/Brilla — CERRADA (Success)
**Next:** Push a beta + tag v10.55.0 solo tras orden literal (COND-4).

---
*Last updated: 2026-08-06*
