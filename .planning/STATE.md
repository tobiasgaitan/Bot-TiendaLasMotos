# Estado del Proyecto - Bot-TiendaLasMotos

Versión: v10.63.0 | Hito: BOT-BUILD-EMPTY-CANDIDATE-021-RF2 — Hardening + pins review #2 | Coherence Score: 1.000 (786 recolectados = 781 tests/ + 5 scripts/; 786/786 PASSED; 0 failed; 0 skipped)

### Current Position
**Phase:** BOT-BUILD-EMPTY-CANDIDATE-021 (v10.63.0) — Fix-1/2/3/4 ejecutado y certificado.
**Status:** Build completo:
  - Fix-1 (C-22.1): retry inline reparado — reenvío de response_parts + nudge. El historial curado ahora contiene los resultados.
  - Fix-2 (C-22.2): directriz anti-deadlock turn-scoped en function_response search_catalog (credit-condicional, NUNCA juan_pablo_personality).
  - Fix-3 (C-22.3): joiner \n + reorden Ficha/💰/⭐/imagen en _build_pcc_fallback. Caption post-egreso 4 líneas con 💰 intacto.
  - Fix-4 (C-22.1): log finish_reason/safety en vacíos (Zero-Silent-Failures).
  - Pin 005-T1 actualizado; P-HAPPY/P-RECOVERY/P-EGRESS-💰 nuevos.
   - **Pins:** 42 tests; 786 recolectados = 781 tests/ + 5 scripts/; 786/786 PASSED; 0 failed; 0 skipped (M4-003). -W error::RuntimeWarning limpio.
  - **Eval:** Score 1.000 ≥ 0.9 — DEPLOY AUTHORIZED ✅.
  - Núcleos intactos: _fallback_response, juan_pablo_personality, prompts.py, personality.json, resolve_cierre_route, clear_memory/B-011, _process_and_send_egress_message, enforce_length.
  - PASO 2 vivo para turnos siguientes (fase ≥ PHASE_2 con moto canónica).

### Evidencia Vertex (read-only, Fase 1)
- **Run 1 (7.8s):** finish_reason=UNEXPECTED_TOOL_CALL — modelo intentó calculate_credit_score (EXCEPCIÓN), tools=[] bloqueó → candidato vacío. safety_ratings=None.
- **Run 2 (16.8s):** finish_reason=STOP — PASO 1 perfecto (saludo Juan Pablo + VICTORY MRX 125 + $9.969.000 + imagen + pregunta cierre). Mismo payload, comportamiento no-determinista.
- **Conclusión:** NO es bloqueo de safety; el dead-lock cognitivo del prompt produce empty candidate a alta probabilidad. Los Fix-1 y Fix-2 lo resuelven con dos capas de defensa.

### Evidencia prod (Cloud Logging 00:17-00:19 UTC 10-ago)
- Turn 1: TimeoutError a 18s exactos (GEMINI_CALL_TIMEOUT_S → H4 amplificador documentado, fuera de alcance).
- Turn 2: Empty Candidate in Turn 2 a 3.4s (no timeout — UNEXPECTED_TOOL_CALL confirmado).
- Egress: ✂️ Coerción 250→191 chars. Caption enviado: disculpa + Ficha + ⭐ (💰 truncado).
- JUDGE approved el fallback. Score=410.

### Trade-off vigente (C6)
C-20b: el fallback degradado emite `Ficha Tecnica: <top_name>` SIN summary técnico. C5-028 abierto.

### Tickets abiertos post-F5
- **C5-028:** enriquecer _build_pcc_fallback con summary del catálogo.
- **C5-031 (H4):** revisar GEMINI_CALL_TIMEOUT_S (18s → Turn 1 TimeoutError en frío) y deadline inner-loop que descarta respuestas recuperadas.
- **C-21:** flag canonical=False.

### Remediación post-review (BOT-BUILD-EMPTY-CANDIDATE-021-RF)
- R1: Pin anti-deadlock en P-HAPPY + P-NO-CREDIT (tests/test_empty_candidate_021.py).
- R2: Refino C-22.2 — condición `phase == "PHASE_1_PROFILING"` ∧ keyword crediticia, sin "cuotas" (ai_brain.py :2734-2735).
- R3: Limpieza imports no usados (test_empty_candidate_021.py).
- R4: SSOT documental unificado — MAESTRO.md / STATE.md raíz eliminados; v10.63.0 portado a docs/DOCUMENTO_MAESTRO.md (Directivas #6/#7).
- R5: Fórmula M4-003 "784 recolectados = 779 tests/ + 5 scripts/" en .planning/STATE.md + .planning/ROADMAP.md + DOCUMENTO_MAESTRO.

**Previous:** BOT-BUILD-MOTO-CANON-020 (v10.62.0) — C-20a-e
**Next:** Prueba en vivo F5 + C5-028/C5-031/C-21 bajo decisión de Tobias.

---
*Last updated: 2026-08-09*
