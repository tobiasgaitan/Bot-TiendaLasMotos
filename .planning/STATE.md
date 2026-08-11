# Estado del Proyecto - Bot-TiendaLasMotos

Versión: v10.67.0 | Hito: BOT-BUILD-PCC-VALID-026 — Palanca a: contrato Visual-Lock literal en fr/nudge/forced_instruction + Palanca b: stash efímero + salvage determinista con caption canónico PASO 1 + pops OBL-1 antes de cada return — BUILD COMPLETE + C6 SYNC docs | Coherence Score: 1.000 (816 recolectados proyectado = 811 tests/ + 5 scripts/; 808 tests recolectables + 3 tests en audio + 5 scripts = 816; 56/56 protegidos PASSED; 0 failed; 0 skipped)

### Current Position
**Phase:** BOT-BUILD-PCC-VALID-026 (v10.67.0) — Palancas a+b: contrato Visual-Lock literal en guías + salvage determinista PASO 1 — build completo certificado (816/816), C6 SYNC docs aplicado.
**Status:** Build completo:
  - Palanca (a): 4 inserciones aditivas exigiendo 'Ficha Tecnica: <modelo>' literal en reject_msg (:2828), fr repetida (:2819), nudge empty-candidate (:2360) y forced_instruction retry (:1323).
  - Palanca (b): stash efímero _credit_tool_rejected_this_turn en prospect_data (:2816-2818, patrón EGRESS-CANON-015); rama salvage determinista en max-attempts (:1348-1363) → _build_canonical_paso1_caption (saludo Juan Pablo + Ficha Tecnica: + $ + imagen + cierre canónico) si flag stashado ∧ Top Result stashado. _build_pcc_fallback y run_checker intocados.
  - OBL-1: pops idempotentes con guard `if prospect_data:` antes de cada return (:1354/:1362/:1382/:1410). R1-R4 de revisión externa integrados (R1: guard anti-None en :1362; R2: normalización de guards; R3: docstring suavizado; R4: P6-NULL-PROSPECT-DATA).
  - **Pins:** P1-REPRO-VALIDADOR, P2-NUDGE-CONTRATO, P3-E2E-CUMPLE, P4-SALVAGE-DETERMINISTA, P5-SALVAGE-NO-CREDIT, P6-NULL-PROSPECT-DATA (6 tests). Denominador 810→816 proyectado (811 tests/ + 5 scripts/; test_audio_vision_hardening_018.py excluido por import ffmpeg preexistente). 56/56 protegidos PASSED; 0 failed; 0 skipped. -W error::RuntimeWarning limpio.
  - **Eval:** Score 1.000 ≥ 0.9 — DEPLOY AUTHORIZED ✅.
  - Cambio acotado: app/services/ai_brain.py (7 hunks, +53/-4) + tests/test_pcc_valid_026.py (nuevo). Núcleos intactos: _fallback_response, juan_pablo_personality, prompts.py, personality.json, resolve_cierre_route, clear_memory/B-011, _process_and_send_egress_message, enforce_length, _determine_funnel_phase, C-22.2.
  - Colateral: **C5-044 registrado** (b3 — early exit salvage diferido).

### Evidencia determinista del fix (tool-loop budget)
- P1a-3LEG: bucle de 3 legs; TOOL REJECTION de calculate_credit_score → exención A′ preserva el turno de texto autoritativo (cap 90s excedido y permitido por ceiling 120s).
- P1b-4LEG: forced turn; el cap por ratio actúa SOLO si no hay exención; con rechazo de crédito el texto se emite dentro del ceiling.
- P2-PER-INNER-LOOP: log [PCC-BUDGET] por turno dentro del inner-loop (turn/total, elapsed, cap, ratio).
- P3-RATIO-075: límites del cap: 90s = 120s × 0.75 (antes 60s = 0.5 fijo).
- P5-LOG-ZSF: half-A aserta MODEL_TEXT esperado (turno de texto emitido; nacimiento correcto); verify_log lógico.
- P6-NO-CREDIT: sin rechazo de crédito → sin exención → cut por ratio normal + degradación.
- P7-ABSOLUTE-CEILING: exención limitada al ceiling absoluto 120s; más allá → cut/degradación (no se permiten turnos infinitos).

### Colaterales abiertos
- **C5-028:** enriquecer _build_pcc_fallback con summary del catálogo.
- **C5-031 (H4):** revisar GEMINI_CALL_TIMEOUT_S (18s → Turn 1 TimeoutError en frío).
- **C-21:** flag canonical=False.
- **C5-033 (C-24):** compuerta paso_1_completed en _determine_funnel_phase (diferida).
- **C5-034 (L1):** call site :1689 (_create_tools, log-only) no consume fase congelada → inconsistencia cosmética de log vs tag Langfuse.
- **C5-035 (L4):** edge case fc múltiples simultáneos (handoff + search_catalog) y condición T1; también cubre exposición extra de trigger_human_handoff en ventana T1 (inerte sin rama de ejecución).
- **C5-036 (F3):** interacción T1 con max_turns=3 — dos desobediencias (re-search + crédito) pueden consumir el budget antes del texto final → _build_pcc_fallback. Trade-off acotado; evaluar bump a 4 como tarea propia.
- **C5-042 / C5-043:** registrados (BOT-BUILD-TOOLLOOP-025).
- ~~**C5-041:** CERRADO — minScale=1 físico en Cloud Run confirmado en revisión 00447; header de consola stale (cosmético).~~

**Previous:** BOT-BUILD-DEADLINE-BUDGET-023 (v10.65.0) — C-23/T1-T5
**Next:** F5 (prueba en vivo: /reset → "doble propósito a crédito" → happy path + "¿cuánto queda la cuota?" → PASO 2/3/4). Luego C5-028/C5-031 bajo decisión de Tobias.

### Tooling local (MCP, sin bump documental — BOT-BUILD-GRAPHIFY-MCP-024)
- `graphify-backend` MCP registrado en ~/.config/opencode/opencode.json (bloque local vía /opt/homebrew/bin/uv + graphifyy 0.9.38 + graph.json; timeout 30000; enabled true). Invariante serena intacto (SHA-256 canónico 24545b4f…bbffc). Pendiente: reinicio de OpenCode y verificación del panel MCP (COND-1 v2: persistir sesiones activas antes de reiniciar).

---
*Last updated: 2026-08-10*
