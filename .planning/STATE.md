# Estado del Proyecto - Bot-TiendaLasMotos

Versión: v10.51.0 | Hito: AUD-SCORE-PERSIST-001 — Persistencia Estructurada del Score Post-Consentimiento COMPLETED | Coherence Score: 1.000 (666/666 Tests PASSED vía `npx agent-cli eval`)

### Current Position
**Phase:** AUD-SCORE-PERSIST-001 (Milestone 3 / Etapa 6+) — Corrección de persistencia de `score_resultado` y espejos retrocompatibles de llaves divergentes — CERRADA (Success)
**Status:** Complete — Implementación quirúrgica certificada contra el plan del OPENCODE PLANNER:
  - `score_resultado` (number) y `score_resultado_at` persisten en el documento padre `prospectos/{id}` vía transacción Firestore única, solo post-consentimiento Habeas Data.
  - Espejos retrocompatibles añadidos en `update_prospect_summary`: `moto_interes`, `ingresos`, `gastos`, `habeas_data`, `habeas_data_sent`; se conservan las llaves canónicas del bot.
  - Idempotencia del historial: clave determinista `scoremsg_<sha256(phone|model|content|bucket300s)>` absorbe la doble escritura L2063+L2253 y la re-entrada de Cloud Tasks (TTL 120s).
  - Atomicidad: `persist_credit_score_result()` actualiza padre + subcolección `historial` en una sola transacción; fallo → log forense + propagación (Zero-Silent-Failures).
  - Retrocompatibilidad: `historial.content` intacto; único campo aditivo `structured`.
  - Tests T1–T8 aditivos en `tests/test_score_persist_writer.py` (20 ítems); denominador canónico 646→666, 0 failed, 0 skipped. Coherence 1.000 — DEPLOY AUTHORIZED.
**Deuda Técnica Residual Documentada:**
- ~~Saludo repetitivo en matriz~~ — RESUELTO (FIX-B Ampliado, v10.48.0)
- ~~Entidad "Crediorbe" obsoleta~~ — RESUELTO y cerrado forensemente (FIX-E re-sync Firestore prod + personality.json, v10.48.0). Residual operativo manual ajeno al prompt: borrar doc `financial_config/general/financieras/crediorbe` en Firestore prod.
- ~~Pregunta genérica en FAQ brake~~ — RESUELTO (FIX-D, v10.48.0)
- ~~Cuarentena C5 vigente (por mandato expreso, NO ejecutada en esta etapa): H-COL-1 (tono) y H-COL-2 parcial (BUSINESS_RULES vs catálogo)~~ — **RESUELTO (2026-07-27, cuarentena C5 levantada — intervención 100% documental):** script de BUSINESS_RULES.md alineado a 1ª persona singular + bloque "Gobernanza de Datos" (SSOT Documental vs SSOT de Ejecución + Regla de Precedencia) + Directiva Inmutable #6 en DOCUMENTO_MAESTRO.md.
**Previous:** Milestone 3 - Etapa 4: Cierre de Fase Operativo & Certified — Cerrada [BOT-BUILD-FIX-SUMMARY-MOTO-INTEREST-001, BOT-BUILD-FIX-MATRIX-RESTART-001, BOT-BUILD-FIX-CATALOG-PROFILE-001-AMPLIADO-v2, BOT-BUILD-FIX-CATALOG-PROFILE-001-AMPLIADO] (Success)
**Next:** Milestone 3 - Etapa 7: Sincronización GSD (/gsd-sync), Certificación de Coherencia (npx agent-cli eval ≥0.9), Despliegue (npx agent-cli deploy → publish). Etapa 5 (concurrencia/legado) permanece en el roadmap.

---
*Last updated: 2026-08-03*
