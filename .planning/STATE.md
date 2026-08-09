# Estado del Proyecto - Bot-TiendaLasMotos

Versión: v10.60.0 | Hito: BOT-BUILD-PCC-LOOP-017 — Cierre del bucle del guard de PCC y conexión del path degradado al fallback honesto de DRIFT-CANON-016 + Top Result | Coherence Score: 1.000 (denominador REAL 741 = 736 tests/ + 5 scripts/)

### Current Position
**Phase:** BOT-BUILD-PCC-LOOP-017 (minor v10.60.0) — Cierre del bucle del guard PCC: call-sites degradados conectados a `_fallback_response(reason="empty_candidate")` con Top Result + Fix-A anti-loop en retries — CERRADA (Build + Eval certificados)
**Status:** Build ejecutado contra plan arquitectónico aprobado BOT-PLAN-PCC-LOOP-017:
  - Fix-A: cláusula anti-loop `PROHIBIDO volver a invocar search_catalog` en retries post-tool-response (C-15:2193-2198) y guardrail (C-14:2265-2272); retiro de `tools` de `GenerateContentConfig` en 2197/2270/3021 cuando `search_catalog_called and catalog_returned_results`. Forced Turn 2154 INTACTO.
  - Fix-B: call-sites 2089, 2106, 2175, 2199-2201, 2214, 2324, 3026-3027 invocan `_fallback_response(texto, history, reason="empty_candidate")` condicional cuando existen resultados de catálogo, con anexo determinista del Top Result (nombre + precio $ + imagen Markdown). `_fb_reason` bug None corregido (`or "empty_candidate"`).
  - Guard PCC 1292-1298 (max validation attempts): redirigido a fallback honesto + Top Result SOLO cuando `final_text` vacío/whitespace; `final_text` no vacío preserva comportamiento legacy (`_validate_output` + `_ensure_soat_anchor`) — sin regresión en flujos image-caption/Ficha Tecnica.
  - `_fallback_response` (3243-3254), `juan_pablo_personality`, `Forced Turn 2154`, `resolve_cierre_route`, `clear_memory`/guard B-011, `_process_and_send_egress_message` INTACTOS carácter por carácter.
  - +8 ítems: 5 pins nuevos (PINs 1-4 en `tests/test_pcc_loop_017_regression.py` + `tests/test_drift_canon_016_regression.py`) + 3 pins renovados/adicionales en `tests/test_fix_catalog_search_regression_005.py` (T2 honesto, T3 legacy preservado, T2 original transpuesto).
  - **Denominador REAL certificado: 741 (736 tests/ + 5 scripts/); 741/741 PASSED; 0 failed; 0 skipped; Score 1.000 vía `npx agent-cli eval`.**
  - Núcleos intactos: `_fallback_response`, `juan_pablo_personality`, `prompts.py`, `resolve_cierre_route`, `clear_memory`/guard B-011, `_process_and_send_egress_message`.

**Previous:** BOT-BUILD-EGRESS-CANON-015 (v10.58.0) — Egreso determinista de imagen y modelo + fix regresión E2E — CERRADA (Success)
**Next:** F5 (eval + sync + push beta v10.60.0) + prueba en vivo: /reset → "Hola, quisiera una moto doble propósito a crédito" → recomendación del Top Result (VICTORY MRX 125) con precio $ e imagen firebasestorage, moto_interest canónico en Firestore, CERO "Se me quedó colgado el sistema", CERO Empty Candidate en retries con resultados válidos.

---
*Last updated: 2026-08-09*
