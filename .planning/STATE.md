# Estado del Proyecto - Bot-TiendaLasMotos

Versión: v10.52.0 | Hito: AUD-FP-AUTO-007 — Deterministic forma_pago="Crédito" auto-fill on Habeas Data acceptance + T3 deduplication | Coherence Score: 1.000 (673/673 Tests PASSED vía `npx agent-cli eval`)

### Current Position
**Phase:** AUD-FP-AUTO-007 (Milestone 3 / Etapa 6+) — Regla determinista forma_pago="Crédito" en aceptación PASO 4 + T3 deduplicación de save_message — CERRADA (Success)
**Status:** Complete — Implementación quirúrgica certificada contra el plan del OPENCODE PLANNER:
  - Regla determinista `forma_pago="Crédito"` en `update_prospect_summary` cuando ocurre la transición `habeas_data_accepted` False→True, el script legal fue presentado (`habeas_data_accepted_sent` True) y `forma_pago` está vacío. Extracción explícita del mismo turno gana prioridad (R3).
  - Capa de derivación aditiva post-merge (entre L606 y L611) respetando el contrato de `_merge_extracted_data` (pins `test_memory_merge` intactos) y los espejos dashboard existentes.
  - Módulo MemoryService línea v9.x bump 9.8.6→9.8.7; sin cambios a `juan_pablo_personality`, reset (P0), backfill ni O1.
  - T3: eliminación de la escritura duplicada `save_message` en `_pipeline_text_cognitive` (whatsapp.py L2065-2066); eco del modelo se mantiene únicamente en `_process_and_send_egress_message` y en ramas fallback internas. Pins PEI-1/3/4/5 intactos.
  - Tests aditivos: `tests/test_forma_pago_autofill_007.py` (7 ítems: 6 unitarios + 1 e2e 👍). Pins A/B/C per A6: schema estable (Pin A), Pin B rediseñado como derivación en persistencia, Pin C robustecido (sent-gate). R2-4a documentada: pre-v10.52.0 la aceptación no rellenaba `forma_pago`; v10.52.0 la aceptación PASO 4 con script presentado lo rellena si vacío.
  - Denominador canónico 666→673 (661+7 tests/ + 5 scripts/); 673 recolectados = 673 puntuables; 673 PASSED; 0 failed; 0 skipped. Coherence 1.000 — DEPLOY AUTHORIZED.
**Deuda Técnica Residual Documentada:**
- ~~Saludo repetitivo en matriz~~ — RESUELTO (FIX-B Ampliado, v10.48.0)
- ~~Entidad "Crediorbe" obsoleta~~ — RESUELTO y cerrado forensemente (FIX-E re-sync Firestore prod + personality.json, v10.48.0). Residual operativo manual ajeno al prompt: borrar doc `financial_config/general/financieras/crediorbe` en Firestore prod.
- ~~Pregunta genérica en FAQ brake~~ — RESUELTO (FIX-D, v10.48.0)
- ~~Cuarentena C5 vigente (por mandato expreso, NO ejecutada en esta etapa): H-COL-1 (tono) y H-COL-2 parcial (BUSINESS_RULES vs catálogo)~~ — **RESUELTO (2026-07-27, cuarentena C5 levantada — intervención 100% documental):** script de BUSINESS_RULES.md alineado a 1ª persona singular + bloque "Gobernanza de Datos" (SSOT Documental vs SSOT de Ejecución + Regla de Precedencia) + Directiva Inmutable #6 en DOCUMENTO_MAESTRO.md.
**Previous:** Milestone 3 - Etapa 4: Cierre de Fase Operativo & Certified — Cerrada [BOT-BUILD-FIX-SUMMARY-MOTO-INTEREST-001, BOT-BUILD-FIX-MATRIX-RESTART-001, BOT-BUILD-FIX-CATALOG-PROFILE-001-AMPLIADO-v2, BOT-BUILD-FIX-CATALOG-PROFILE-001-AMPLIADO] (Success)
**Next:** Milestone 3 - Etapa 7: Sincronización GSD (/gsd-sync), Certificación de Coherencia (npx agent-cli eval ≥0.9), Despliegue (npx agent-cli deploy → publish). Etapa 5 (concurrencia/legado) permanece en el roadmap.

---
*Last updated: 2026-08-05*
