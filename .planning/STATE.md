# Estado del Proyecto - Bot-TiendaLasMotos

Versión: v10.66.0 | Hito: BOT-BUILD-TOOLLOOP-025 — Exención A′ del tool-loop budget PCC (ratio 0.75 + ceiling absoluto 120s + telemetría [PCC-BUDGET]) — BUILD COMPLETE + C6 SYNC docs | Coherence Score: 1.000 (810 recolectados = 805 tests/ + 5 scripts/; 810/810 PASSED; 0 failed; 0 skipped)

### Current Position
**Phase:** BOT-BUILD-TOOLLOOP-025 (v10.66.0) — Exención A′ del tool-loop budget PCC — build completo certificado (810/810), C6 SYNC docs aplicado.
**Status:** Build completo:
  - PCC_INNER_LOOP_BUDGET_RATIO (:181): constante env-tunable (default "0.75"); cap del inner-loop = PCC_DEADLINE_BUDGET_S × ratio (antes 0.5 fijo = 60s sobre 120s).
  - Exención A′ turno-scoped (:2294-2314): si elapsed > cap por ratio y credit_tool_rejected_this_turn y elapsed ≤ ceiling absoluto 120s → skip del cut (preserva el turno de texto autoritativo post-TOOL REJECTION C-23); de lo contrario cut + degradación.
  - Telemetría [PCC-BUDGET] por turno: log info turn/max_turns, elapsed, cap, ratio.
  - **Pins:** P1a-3LEG, P1b-4LEG, P2-PER-INNER-LOOP, P3-RATIO-075, P5-LOG-ZSF, P6-NO-CREDIT, P7-ABSOLUTE-CEILING (7 tests). R5/R6 integrados: monkeypatch PCC_DEADLINE_BUDGET_S=120.0 y PCC_INNER_LOOP_BUDGET_RATIO=0.75 en P1a/P1b/P2 + assert MODEL_TEXT en P5 half-A. 810 recolectados = 805 tests/ + 5 scripts/; 810/810 PASSED; 0 failed; 0 skipped. -W error::RuntimeWarning limpio.
  - **Eval:** Score 1.000 ≥ 0.9 — DEPLOY AUTHORIZED ✅.
  - Cambio acotado: app/services/ai_brain.py (2 hunks, +18/-6) + tests/test_toolloop_budget_025.py. Núcleos intactos: _fallback_response, juan_pablo_personality, prompts.py, personality.json, resolve_cierre_route, clear_memory/B-011, _process_and_send_egress_message, enforce_length, _determine_funnel_phase, C-22.2.

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
