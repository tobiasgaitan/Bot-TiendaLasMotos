# Estado del Proyecto - Bot-TiendaLasMotos

Versión: v10.54.0 | Hito: AUD-CIERRE-RUTAS-010 — Rediseño de la doctrina de CIERRE DE FASE (bandas > strategy + gate gas/Brilla) | Coherence Score: 1.000 (689/689 Tests PASSED vía `npx agent-cli eval`)

### Current Position
**Phase:** AUD-CIERRE-RUTAS-010 (minor v10.54.0) — Rediseño de la doctrina de CIERRE DE FASE con prioridad absoluta de bandas de score sobre `strategy` y gate de coherencia gas/Brilla — CERRADA (Success)
**Status:** Complete — Ejecución certificada contra el plan arquitectónico aprobado v1.0:
  - Vía A: prompt `juan_pablo_personality` reescrito en `app/core/prompts.py` y `app/core/personality.json`; sincronizado a Firestore vía `scripts/sync_full_prompt.py` con triple aserción forense y evidencia archivada en `scripts/evidence/`.
  - Vía B: enforcement determinista POST-JSON en `app/services/ai_brain.py:2507-2609` mediante `resolve_cierre_route` (`app/services/scoring_service.py`); `score`/`strategy`/`entity` del JSON inalterados; campo aditivo `cierre_ruta` en `res` y `_score_resultado`; logger forense sin PII.
  - Doctrina canónica: R1 score≥750→Banco; R2 500-749→revisión humana (solicita documento post-score); R3 ≤499+gas afirmativo→Brilla; R4 ≤499+gas negativo→rechazo.
  - Normalización estricta de gas (`is_gas_affirmative`): cierra truthy-bug del string `"No"` en `ai_brain.py:2495`.
  - Pins rediseñados in-place: `tests/test_brilla_conmutacion.py` (doctrina de cierre por bandas) y `tests/test_fix_catalog_profile_001.py` (textos canónicos actualizados).
  - Tests aditivos `tests/test_cierre_rutas_010.py` (5 ítems): resolvedor, hueco 499, normalización, regresión exacta del incidente 530/gas="No"→ruta 2, persistencia aditiva.
  - Denominador canónico 684→689 (684 tests/ + 5 scripts/); 689/689 PASSED; 0 failed; 0 skipped. Coherence 1.000 — DEPLOY AUTHORIZED.

**Previous:** AUD-FP-AUTO-REG-009 (v10.53.1) — Fix temporal R1∧R2 en auto-fill forma_pago="Crédito" — CERRADA (Success)
**Next:** Push autorizado a beta + tag v10.54.0 (o deploy según orden).

---
*Last updated: 2026-08-06*
