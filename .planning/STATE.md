# Estado del Proyecto - Bot-TiendaLasMotos

Versión: v10.57.0 | Hito: BOT-BUILD-FUNNEL-SKIP-014 — Cierre incidente salto de fase: compuerta canónica Habeas + reset verdadero de latches | Coherence Score: 1.000 (denominador REAL 716 = 711 tests/ + 5 scripts/, declarado post-eval; desviación C6 cerrada por PIN-014-E2E)

### Current Position
**Phase:** BOT-BUILD-FUNNEL-SKIP-014 (minor v10.57.0) — Cierre de R1/R2/R3 del incidente de salto de fase post-reset/Wave A — CERRADA (Build + Eval certificados; complementación COND-1 PIN-014-E2E integrada)
**Status:** Build ejecutado contra plan arquitectónico aprobado BOT-PLAN-FUNNEL-SKIP-014 + ADD-01:
  - Fix A (`app/services/ai_brain.py` L996 + L1733-1785): compuerta canónica en `_determine_funnel_phase` — avance a PHASE_2_HABEAS_DATA exige `credit_intent ∧ has_canonical_moto`; categorías libre-texto (ej. "doble propósito") ya no activan el script Habeas. Refuerzo soft PHASE_1 con `try/except` y fallback genérico ante catálogo vacío/timeout.
  - Fix B (`app/services/memory_service.py` + `app/routers/whatsapp.py` L922-969): `reset_phase_latches` zero latches de fase (`habeas_data_accepted`, `forma_pago`, `moto_interest/moto_interes`, `moto_confirmada`, `score_resultado`) SIN purgar historial comercial ni identidad (`nombre`/`ciudad` preservados). Enganche bloqueante SIEMPRE tras `delete_prospect_completely`; feedback condicional `success=True`→"reiniciada por completo" / `success=False`→"reiniciada" + warning estructurado con `trace_id`.
  - Migración one-shot legacy documentada en `CRM_MEMORY_GUIDE.md` (C-10: ejecutable separado, prohibido commitar en `app/` o `scripts/`).
  - Revisión externa F3.5 (MiMo-V2.5-pro, revisor Qwen3.8-Max) integrada: lock por phone ya cubierto por sesión (whatsapp.py:732); feedback diferenciado implementado; docs legacy atendidos por migración documentada; PINs A4/B2 añadidos; C-8 idempotencia confirmada (`set(merge=True)` sobre doc inexistente crea latches en cero).
  - Pins aditivos: PIN-014-A1/A2/A3/A4 en `tests/test_habeas_data_regression.py`, PIN-014-B1/B2 en `tests/test_m4_wave_a.py`; complementación COND-1: PIN-014-E2E en `tests/test_m4_wave_a.py` (/reset real → "doble propósito a crédito": search_catalog invocada, log [CATALOG-FORENSIC], funnel_phase == PHASE_1_PROFILING en todas las evaluaciones, respuesta con precio y sin script Habeas); prueba en vivo retenida por C-9.
  - **Denominador REAL certificado: 716 (711 tests/ + 5 scripts/); 716/716 PASSED; 0 failed; 0 skipped; Score 1.000 vía `npx agent-cli eval`. Desviación C6 CERRADA: el recuento real de pytest (716) coincide con el proyectado 716 tras la incorporación de PIN-014-E2E.**
  - Núcleos intactos: `clear_memory` y guard Fix B-011 (`memory_service.py:521-523`), `_process_and_send_egress_message` y Visual-Lock A2 (`whatsapp.py:2284-2310`), `juan_pablo_personality`, `prompts.py`, `resolve_cierre_route` y bandas 750/500/499.

**Previous:** AUD-LEGACY-JUDGE-012 (v10.56.1) — Purga de residuo CrediOrbe + C6 del Juez activado y alineado a la doctrina de 4 rutas — CERRADA (Success)
**Next:** Prueba en vivo /reset → "doble propósito a crédito" (C-9) + push beta v10.57.0 solo tras orden literal.

---
*Last updated: 2026-08-09*