# Estado del Proyecto - Bot-TiendaLasMotos

Versión: v10.71.0 | Hito: BOT-BUILD-PRICE-LOCK-037 — Backstop PRICE-LOCK v2 en pipeline de egreso (cierre definitivo C5-037) — BUILD COMPLETE + C6 SYNC docs | Coherence Score: 1.000 (849 recolectados físico = 844 tests/ + 5 scripts/; 849/849 PASSED; 0 failed; 0 skipped)

### Current Position
**Phase:** BOT-BUILD-PRICE-LOCK-037 (v10.71.0) — Backstop PRICE-LOCK v2: wrapper idempotente sobre enforce_length (T0/T1/T2/T3) + R2 split Ficha-párrafo + R1.4 unicidad + regexes plural/delimitador/punto-final/incluye-case en app/routers/whatsapp.py; 16 pines (P1-P16) + 10 mordidas. C4 intacto. Cierre de negocio pendiente de prueba en vivo.
**Status:** Build completo:
  - Fix A: `_build_canonical_paso1_caption` (~:3547) — joiner `\\n\\n`→`\\n` + saludo genérico "¡Hola! Soy Juan Pablo, asesor de Tienda Las Motos." para nombre vacío/desconocido.
  - Fix B: `_format_gemini_error_body` (~:725 helper + ~:811 call site) — `e.details`→`json.dumps`, fallback `e.response.text`/`e.message`/`str(e)` con `str(message)[:200]`, colapso a 1 línea, cap ~800 con marca truncado, rama final no-vacía, try/except total.
  - **Pins:** P1-CAPTION-4L-PRIMER-CONTACTO, P2-CAPTION-4L-NOMBRE, P3-SALUDO-GENERICO, P4-JOINER-FIX3-PARITY, P5-ZSF-SINGLE-LINE, P5b-ZSF-TRUNCATED-BODY, P6-ZSF-NEVER-RAISES-AND-NOT-EMPTY (7 tests). Denominador físico 829 (824 tests/ + 5 scripts/). 829/829 PASSED; 0 failed; 0 skipped. Score 1.000.
  - **Eval:** Score 1.000 ≥ 0.9 — DEPLOY AUTHORIZED ✅.
  - Cambio acotado: app/services/ai_brain.py (3 edits: ~:3547 hunk A, ~:725 helper + ~:811 call site, `str(message)[:200]` en `_fallback()`) + tests/test_salvage_caption_028.py (nuevo). Núcleos intactos: juan_pablo_personality, prompts.py, _fallback_response, run_checker, enforce_length, _build_pcc_fallback, egress_guard_service.py.
  - Colaterales: C5-052 (greeting whitespace-only, preexistente) y C5-053 (alertas por tag `[GEMINI ERROR MESSAGE]` eliminado; 0 refs en repo, no verificable externamente).

### Evidencia determinista del fix (tool-loop budget)
- P1a-3LEG: bucle de 3 legs; TOOL REJECTION de calculate_credit_score → exención A′ preserva el turno de texto autoritativo (cap 90s excedido y permitido por ceiling 120s).
- P1b-4LEG: forced turn; el cap por ratio actúa SOLO si no hay exención; con rechazo de crédito el texto se emite dentro del ceiling.
- P2-PER-INNER-LOOP: log [PCC-BUDGET] por turno dentro del inner-loop (turn/total, elapsed, cap, ratio).
- P3-RATIO-075: límites del cap: 90s = 120s × 0.75 (antes 60s = 0.5 fijo).
- P5-LOG-ZSF: half-A aserta MODEL_TEXT esperado (turno de texto emitido; nacimiento correcto); verify_log lógico.
- P6-NO-CREDIT: sin rechazo de crédito → sin exención → cut por ratio normal + degradación.
- P7-ABSOLUTE-CEILING: exención limitada al ceiling absoluto 120s; más allá → cut/degradación (no se permiten turnos infinitos).

### Colaterales abiertos
- **C5-052:** greeting whitespace-only en `_build_canonical_paso1_caption` (preexistente, ruta `str(user_name or "").strip()`); evaluar normalización.
- **C5-037:** CERRADO EN BETA (v10.71.0) — backstop PRICE-LOCK v2; cierre de negocio pendiente de prueba en vivo (criterio: caption con 💰 visible + imagen en escenario "moto automática a crédito").
- **C5-060:** text-only path PASO 1 con crédito (URL-Lock reject sin sustituto) decapita $ en _send_whatsapp_message :2782 sin wrapper. Diferido.
- **C5-061:** getter chains de ai_brain.py prefieren price (int) sobre formatted_price en 7 sitios → 💰 sin $ en rutas deterministas salvage/fallback. Requiere orden literal C-29.
- **C5-062:** CERRADO — espejo STATE/ROADMAP de v10.70.0 y tags faltantes curados en este WARP-SYNC (tag retroactivo v10.70.0 en 3f41148 + v10.71.0).
- **C5-063:** sin log del caption pre-coerción verbatim (forense de egreso ciego al contenido). Diferido; R3 mitiga con reason de T3.
- **C5-064:** _price_lock_failure_reason emite no_compact_anchor cuando el ancla existió pero fue truncada; etiqueta propuesta anchor_merged_but_truncated. Diferido (forense-only).
- **C5-050 + C5-039 (HIGH #2, raíz única):** cliente genai instanciado por request (whatsapp.py :906/:1308/:1406 → ai_brain.py :274) amplifica 429 RESOURCE_EXHAUSTED en Turn 1 y latencia/cuota. Enfoque: singleton/pool + forense del cuerpo 429.
- **C5-045:** gate F5 debe exigir explícitamente 0 failed en stdout antes del push (exit-code del deploy-gate no basta).
- **C5-046:** flaky tests/test_regression_203.py::test_raider_125_helper_path_414444.
- **C5-047:** pregunta de identidad "¿con quién tengo el gusto?" fuera de orden en PASO 1 con crédito.
- **C5-058:** perímetro M4-003 del Maestro decía 817+5=822; CURADO en este WARP-SYNC a 824+5=829.
- **C5-059:** snapshot KB Documento Maestro.docx queda desactualizado tras este WARP-SYNC (header F5 + perímetro); realinear en el próximo hito documental (gobernanza C5-054: el repo vivo prevalece).
- **C5-053:** alertas externas por eliminación del tag `[GEMINI ERROR MESSAGE]` en Fix-B (0 referencias restantes en repo; no verificables, observación pasiva).
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

**Previous:** BOT-BUILD-SALVAGE-CAP-028 (v10.69.0) — Caption salvage 4 líneas + log ZSF HTTP Gemini
**Next:** C5-050+C5-039 (singleton cliente genai, HIGH #2) vía OPENCODE PLANNER. C5-061 (getter chains formatted_price-first en ai_brain.py) pendiente de orden literal C-29 de Tobias.

### Tooling local (MCP, sin bump documental — BOT-BUILD-GRAPHIFY-MCP-024)
- `graphify-backend` MCP registrado en ~/.config/opencode/opencode.json (bloque local vía /opt/homebrew/bin/uv + graphifyy 0.9.38 + graph.json; timeout 30000; enabled true). Invariante serena intacto (SHA-256 canónico 24545b4f…bbffc). Completado: reinicio + panel MCP verificado (graphify-backend Connected + serena Connected) + graph_stats coherente con GRAPH_REPORT.md — 2026-08-11.

---
*Last updated: 2026-08-12*
