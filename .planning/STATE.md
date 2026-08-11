# Estado del Proyecto - Bot-TiendaLasMotos

Versión: v10.68.0 | Hito: BOT-BUILD-SALUDO-027 — Palanca c: saludo cálido canónico + cierre "¿Con quién tengo el gusto?" en rejection fr de C-23 + Palanca d: frontera de reset por comando user (defensa en profundidad) — BUILD COMPLETE + C6 SYNC docs | Coherence Score: 1.000 (822 recolectados físico = 817 tests/ + 5 scripts/; 822/822 PASSED; 0 failed; 0 skipped)

### Current Position
**Phase:** BOT-BUILD-SALUDO-027 (v10.68.0) — Palancas c+d: saludo cálido canónico + cierre en rejection fr de C-23 + frontera reset defensa-en-profundidad — build completo certificado (822/822), C6 SYNC docs aplicado.
**Status:** Build completo:
  - Palanca (c): _greeting_clause (condicional a skip_greeting=False) + _closing_clause (condicional a prospect_data.nombre ausente) pre-loop (~:2314-2319); concatenación en reject_msg fr 1ª (c1) y fr repetida (c2) (~:2827-2840). Override D1 documentado.
  - Palanca (d): frontera de reset en _evaluate_skip_greeting (:124-139) — scan user "/reset" exact-match (SSOT), scoped_history, ZSF log [RESET-FRONTIER]. Defensa en profundidad: inerte en happy path (clear_memory purga todo, vacío ya fuerza saludo); activa solo en escenario residual de fallo parcial de purge. C5-048 decisión de producto.
  - Docstring: judge_service.py :201-205 soft-claimed "semántica heredada sin frontera de reset (ver C5-049)".
  - **Pins:** P1-FR-GREETING-CLAUSE, P2-FR-CLOSING-CANONICAL, P3-E2E-PRIMER-CONTACTO, P4-WARM-OMITE-SALUDO, P5-FR-CAPTURADO-CON-SALUDO, P6-RESET-FORCES-GREETING (6 tests). Denominador físico 822 (817 tests/ + 5 scripts/). 822/822 PASSED; 0 failed; 0 skipped. Score 1.000.
  - **Eval:** Score 1.000 ≥ 0.9 — DEPLOY AUTHORIZED ✅.
  - Cambio acotado: app/services/ai_brain.py (3 hunks, +17/−3) + app/routers/whatsapp.py (1 hunk, +16/−1) + app/services/judge_service.py (1 hunk, +4/−4 docstring) + tests/test_saludo_027.py (nuevo). Núcleos intactos: _fallback_response, juan_pablo_personality, prompts.py, personality.json, resolve_cierre_route, clear_memory/B-011, enforce_length, _determine_funnel_phase, C-22.2.
  - Colateral: **C5-049 registrado** (paridad judge vs router diferida — el juez no acota a post-reset; evaluar espejar frontier o suavizar docstring con pins dedicados).

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
- **C5-049:** paridad judge vs router — el juez no acota a post-reset (docstring soft-claimed); evaluar espejar frontier o añadir pins dedicados.
- ~~**C5-041:** CERRADO — minScale=1 físico en Cloud Run confirmado en revisión 00447; header de consola stale (cosmético).~~

**Previous:** BOT-BUILD-PCC-VALID-026 (v10.67.0) — Palancas a+b: Visual-Lock + salvage determinista
**Next:** F5 (prueba en vivo: /reset → "doble propósito a crédito" → happy path + "¿cuánto queda la cuota?" → PASO 2/3/4). Luego C5-028/C5-031 bajo decisión de Tobias.

### Tooling local (MCP, sin bump documental — BOT-BUILD-GRAPHIFY-MCP-024)
- `graphify-backend` MCP registrado en ~/.config/opencode/opencode.json (bloque local vía /opt/homebrew/bin/uv + graphifyy 0.9.38 + graph.json; timeout 30000; enabled true). Invariante serena intacto (SHA-256 canónico 24545b4f…bbffc). Pendiente: reinicio de OpenCode y verificación del panel MCP (COND-1 v2: persistir sesiones activas antes de reiniciar).

---
*Last updated: 2026-08-11*
