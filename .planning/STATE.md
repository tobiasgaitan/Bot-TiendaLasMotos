# Estado del Proyecto - Bot-TiendaLasMotos

Versión: v10.56.0 | Hito: AUD-LEGACY-JUDGE-012 — Purga de residuo CrediOrbe (survey_service) + criterio C6 del Juez activado y alineado a la doctrina de 4 rutas | Coherence Score: 1.000 (700/700 Tests PASSED vía `npx agent-cli eval`)

### Current Position
**Phase:** AUD-LEGACY-JUDGE-012 (minor v10.56.0) — Erradicación de CrediOrbe en el flujo legacy de survey_service.py y reactivación del Criterio C6 (Scoring Accuracy) del Juez alineado a `resolve_cierre_route` con gate R-B — CERRADA (Success)
**Status:** Complete — Ejecución certificada contra el plan arquitectónico aprobado v1.0:
  - PARTE A (purga): eliminación del módulo muerto `app/services/survey_service.py` (rama REDIRECT con `entity_name="CrediOrbe"` user-facing; contrato roto con `evaluate_profile` → KeyError → HANDOFF; 0 callers en app/, scripts/, app/routers/admin.py — grep pre-borrado). Se eliminó el test huérfano `tests/test_persistence_unification.py::test_no_mensajeria_collection_in_survey_service`; se añadió la tumba `test_m4_003_survey_service_purgado`; se extendió el guard FIX-E (`test_crediorbe_eradicated_from_source`) a `judge_service.py`; `ponytail-debt.md` #1 → EJECUTADO (M4-003).
  - PARTE B (C6): helper aditivo `app/services/scoring_service.py` (`SMLV_COP` + `score_from_prospect_data` con fallback legacy) y reescritura interna de `judge_service._check_scoring_consistency` (firma y call site intactos): score autoritativo `score_resultado` ∥ recomputo; ruta vía `resolve_cierre_route`; gate R-A (reject si `banco_recommended` y ruta≠1); gate R-B (reject si `brilla_recommended` — frases calificadas + "tramitar por Brilla" — y ruta≠3). 5 tests C6 aditivos en `tests/test_judge_service.py`.
  - Denominador canónico 695→700 (695 tests/ + 5 scripts/); **700/700 PASSED; 0 failed; 0 skipped. Coherence 1.000 — PUSH CONGELADO POR COND-4.**
  - Núcleos intactos: `ai_brain.py`, `personality.json`, `prompts.py`, `BLIND_CREDIT_DEFAULTS`, `resolve_cierre_route`/`is_gas_affirmative`, Vías A/B de AUD-CIERRE-RUTAS-010.

**Previous:** BOT-BUILD-CLASSIFIER-011 (v10.55.0) — Clasificador con documento padre dominante + purge condicional — CERRADA (Success)
**Next:** Push a beta + tag v10.56.0 solo tras orden literal (COND-4).

---
*Last updated: 2026-08-06*