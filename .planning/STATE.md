# Estado del Proyecto - Bot-TiendaLasMotos

Versión: v10.62.0 | Hito: BOT-BUILD-MOTO-CANON-020 — Cierre estructural PCC (degradación conforme I-1) | Coherence Score: 1.000 (nominal 780)

### Current Position
**Phase:** BOT-BUILD-MOTO-CANON-020 (v10.62.0) — C-20a-e ejecutado y certificado.
**Status:** Build completo:
  - C-20a: 5 fallback inline convertidos a `_build_pcc_fallback`. Pin anti-drift AST activo.
  - C-20b: loop externo reestructurado. I-1: toda salida de `pensar_respuesta` es texto validado por `run_checker` o fallback conforme de `_build_pcc_fallback`. Eliminado código muerto + guard contradictorio (1316/1334).
  - C-20c: `GEMINI_TIMEOUT_BUDGET_S` consumido en producción → `RuntimeError` no-reintentable en `_call_gemini_with_retry_async`.
  - C-20d: test deadline determinista (`PCC_DEADLINE_BUDGET_S = -1.0`, no flaky con langfuse).
  - C-20e: 6 pins de contrato congelando blast radius de Fix A en los 4 callers de whatsapp (incl. visión 1418 y modelo parcial).
  - **Pins:** 39 tests 020; suite pytest 780 passed, 2 subtests passed; -W error::RuntimeWarning limpio.
  - **Eval:** Score 1.000 ≥ 0.9 — DEPLOY AUTHORIZED ✅.
  - Núcleos intactos: `_fallback_response`, `juan_pablo_personality`, `prompts.py`, `resolve_cierre_route`, `clear_memory`/guard B-011, `_process_and_send_egress_message`.

### Trade-off vigente (C6)
C-20b: el fallback degradado emite `Ficha Tecnica: <top_name>` (nombre del modelo) SIN summary técnico del catálogo. Pérdida aceptada como trade-off intencional del cierre estructural. Afecta captions técnicos de imagen y degradaciones PCC con resultados de catálogo. Ticket C5-028 abierto (post-F5) para enriquecer `_build_pcc_fallback` con summary via `self._catalog_service`.

### Ticket post-F5 abierto
- **C5-028:** enriquecer `_build_pcc_fallback` con `summary` del catálogo via `self._catalog_service` cuando `top_name` no vacío y el catálogo está disponible. Pendiente decisión de Tobias.
- **C-21:** evaluar persistir interés crudo con flag `canonical=False` en lugar de descarte total por Fix A.

### Trade-off documentado (FIX-2A)
audio/vision: `wait_for` deja worker `to_thread` corriendo, reintento lanza llamada Gemini duplicada (hasta 3). Aceptado, heredado de FIX-2A existente en ai_brain.

**Previous:** BOT-BUILD-MOTO-CANON-018 (v10.60.0) — Fix A/B/C capa 1 + C19b — CERRADA
**Next:** F5 (prueba en vivo beta: /reset → "Hola, quisiera una moto doble propósito a crédito") + C5-028 y C-21 post-F5.

---
*Last updated: 2026-08-09*
