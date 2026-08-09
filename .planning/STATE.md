# Estado del Proyecto - Bot-TiendaLasMotos

Versión: v10.58.0 | Hito: BOT-BUILD-EGRESS-CANON-015 — Egreso determinista de imagen y modelo + fix regresión E2E | Coherence Score: 1.000 (denominador REAL 723 = 718 tests/ + 5 scripts/)

### Current Position
**Phase:** BOT-BUILD-EGRESS-CANON-015 (minor v10.58.0) — Egreso determinista: imagen siempre desde `imagen_url` de la ficha del Top Result (independiente del eco del LLM) + modelo presentado alineado a matches[0] vía retry + sustitución SSOT con `recommended_model` — CERRADA (Build + Eval certificados; C-16 pendiente)
**Status:** Build ejecutado contra plan arquitectónico aprobado BOT-PLAN-EGRESS-CANON-015 + ADD-02:
  - Stash efímero `_catalog_top_name`/`_catalog_top_image` en tool-exec (`ai_brain.py:2494`), pop antes de persistencia (patrón `_score_resultado`).
  - Backstop en `_pipeline_egress` (`whatsapp.py:2305-2327`): `enforce_urls` primero + log de `url_report.summary()` (no bindeado a `_`); `needs_inject` cuando falta/extirpada/wrong-model; Strategy A desde ficha con caption limpia; PEI-5 preservado en eco correcto.
  - Formatter con énfasis TOP RESULT (`ai_brain.py:2397`) + guard post-generación con retry (`ai_brain.py:2199-2236`) para alinear texto a matches[0].
  - Sustitución SSOT en `egress_guard_service.py` con kw `recommended_model` + helper `image_owner_model`.
  - Whitelist NO extendida (auteco.com.co permanece fuera; default-deny intacto).
  - Fix de regresión en `tests/test_e2e_coherence_fire.py`: `update_prospect_moto_interest` como `AsyncMock` (patrón FUNNEL-SKIP-014).
  - Orden literal C-12 de Tobias (2026-08-09) autorizó toques en `ai_brain.py` en :2397, :2494, :2199-2236.
  - 7 pins nuevos en `tests/test_egress_canon_015.py`: inyección canónica, retry alignment, M2 intacto, sustitución por stem no único, wrong-model canonical host, bypass PEI-5, no persistencia del stash.
  - **Denominador REAL certificado: 723 (718 tests/ + 5 scripts/); 723/723 PASSED; 0 failed; 0 skipped; Score 1.000 vía `npx agent-cli eval`.**
  - Núcleos intactos: `juan_pablo_personality`, `prompts.py`, `resolve_cierre_route`, `clear_memory`, guard B-011, `_process_and_send_egress_message` (solo kw-only `recommended_model=None`, firma PEI-1 intacta, CH-5 respetado).

**Previous:** BOT-BUILD-FUNNEL-SKIP-014 (v10.57.0) — Cierre incidente salto de fase post-reset/Wave A — CERRADA (Success)
**Next:** F5 (eval + sync + push beta v10.58.0) + prueba en vivo: /reset → "doble propósito a crédito" → Top Result + imagen firebasestorage + moto_interest canónico.

---
*Last updated: 2026-08-09*