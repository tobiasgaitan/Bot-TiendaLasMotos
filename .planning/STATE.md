# Estado del Proyecto - Bot-TiendaLasMotos

Versión: v10.65.0 | Hito: BOT-BUILD-DEADLINE-BUDGET-023 — Deadline dinámico frío/caliente Gemini + min-instances=1 — BUILD COMPLETE + C6 SYNC docs | Coherence Score: 1.000 (803 recolectados = 798 tests/ + 5 scripts/; 803/803 PASSED; 0 failed; 0 skipped)

### Current Position
**Phase:** BOT-BUILD-DEADLINE-BUDGET-023 (v10.65.0) — Deadline dinámico frío/caliente + min-instances=1 — build completo certificado (803/803), C6 SYNC docs aplicado.
**Status:** Build completo:
  - C-23 / T1 (:3211-3219): tools=dynamic_tools condicional en reenvío post-search (PHASE_1∧crédito∧¬rechazada). Cierra físicamente el abort UNEXPECTED_TOOL_CALL.
  - C-23 / T2 (:2326): nudge endurecido con prohibición dual search_catalog + calculate_credit_score.
  - C-23 / T3 (:2289 + :2782-2799): flag credit_tool_rejected_this_turn one-shot + cortocircuito defensivo en TOOL REJECTION con marcador de log distinto.
  - C-23 / T4 (:1162 + :1176 + :1191-1204): captura única de turn_phase pre-while + paso como forced_phase en los 2 call sites + tag Langfuse usa fase congelada.
  - C-23 / T5 (:1703 + :1729): parámetro forced_phase en _generate_with_retry_async + resolución condicionada.
  - Constante _CREDIT_TURN_KEYWORDS a nivel módulo (:158), reutilizada en C-22.2 (:2743).
  - RF (post-review): R1 — cortocircuito T3 emite function_response (no text Part), preserva pairing fc=fr ante doble calculate_credit_score paralelo. P7-PARALLEL-CREDIT nuevo (7 pines total).
  - **Pins:** P1-HAPPY-E2E, P2-FASE-CONGELADA, P3-CLASIFICADOR, P4-NO-UTC, P6-FLAG-ONE-SHOT, P7-PARALLEL-CREDIT (7 tests). 793 recolectados = 788 tests/ + 5 scripts/; 793/793 PASSED; 0 failed; 0 skipped. -W error::RuntimeWarning limpio.
  - **Eval:** Score 1.000 ≥ 0.9 — DEPLOY AUTHORIZED ✅.
  - Núcleos intactos: _fallback_response, juan_pablo_personality, prompts.py, personality.json, resolve_cierre_route, clear_memory/B-011, _process_and_send_egress_message, enforce_length, _determine_funnel_phase, C-22.2.
  - PASO 2 vivo para turnos siguientes (fase ≥ PHASE_2 con moto canónica).
  - **C6 + RF — Documentación**: L3 (stash visible en prospect_xml de attempt 2 con fase congelada = coherente); L5 (attempt 2 usa catálogo en estado actual, no snapshot). Review finding corregido (RF-R1: from_text → from_function_response en rama re-intento, preserva fc/fr pairing).

### Evidencia determinista del fix C-23
- Turn 1 (PHASE_1 + mención crédito): search_catalog OK → reenvío post-search con tools=dynamic_tools → modelo puede llamar calculate_credit_score.
- Turn 2: calculate_credit_score capturada → TOOL REJECTION controlado (NO UNEXPECTED_TOOL_CALL) → append error fr + flag=True.
- Turn 3: modelo recibe rechazo autoritativo + tools=[] (flag True) → genera PASO 1 (saludo + $ + imagen + Ficha Tecnica:).
- Defensivo: si modelo insiste credit en Turn 3 → cortocircuito con marcador de log distinto + text Part → tools=[] → modelo obligado a generar texto.

### Colaterales abiertos (podaron L1+L4; diferidos C5-034/C5-035)
- **C5-028:** enriquecer _build_pcc_fallback con summary del catálogo.
- **C5-031 (H4):** revisar GEMINI_CALL_TIMEOUT_S (18s → Turn 1 TimeoutError en frío).
- **C-21:** flag canonical=False.
- **C5-033 (C-24):** compuerta paso_1_completed en _determine_funnel_phase (diferida).
- **C5-034 (L1):** call site :1689 (_create_tools, log-only) no consume fase congelada → inconsistencia cosmética de log vs tag Langfuse.
- **C5-035 (L4):** edge case fc múltiples simultáneos (handoff + search_catalog) y condición T1; también cubre exposición extra de trigger_human_handoff en ventana T1 (inerte sin rama de ejecución).
- **C5-036 (F3):** interacción T1 con max_turns=3 — dos desobediencias (re-search + crédito) pueden consumir el budget antes del texto final → _build_pcc_fallback. Trade-off acotado; evaluar bump a 4 como tarea propia.

**Previous:** BOT-BUILD-EMPTY-CANDIDATE-021 (v10.63.0) — C-22.1/C-22.2/C-22.3/C-22.4
**Next:** F5 (prueba en vivo: /reset → "doble propósito a crédito" → happy path + "¿cuánto queda la cuota?" → PASO 2/3/4). Luego C5-028/C5-031 bajo decisión de Tobias.

---
*Last updated: 2026-08-10*
