# Estado del Proyecto - Bot-TiendaLasMotos

Versión: v10.73.0 | Hito: BOT-BUILD-PRICE-LOCK-T3-074 — Rescue T3 en PRICE-LOCK: $ sobrevive a enforce_length en variante residual + etiqueta forense anchor_merged_but_truncated (cierre C5-074/C5-064) — BUILD COMPLETE + C6 SYNC docs | Coherence Score: 1.000 (868 recolectados físico = 863 tests/ + 5 scripts/; 868/868 PASSED; 0 failed; 0 skipped)

### Current Position
**Phase:** BOT-BUILD-PRICE-LOCK-T3-074 (v10.73.0) — Rescue T3 (_price_lock_rescue_top4) en _coerce_caption_price_lock: línea compacta Ficha·💰 inyectada en top-4 cuando T0/T1/T2 pierden el precio (price-only si sin modelo; prohibido 'Ficha Tecnica:  ·' vacío); _price_lock_failure_reason emite anchor_merged_but_truncated (cierra C5-064). whatsapp.py zona mutable; C4 intacto; pines P17-P22 + mordidas (revert R1 → P22 FAIL; rescue off → P17/P18/P19 FAIL). CERRADO EN VIVO 2026-08-14 12:06 p.m. GMT-5: escenario 'moto automática a crédito', $8.329.000 visible post-coerción (rescue T3 price-only, caso COND-1), 0×429; colateral cosmético C5-076 registrado.
**Status:** Build completo (v10.72.0):
  - **Objetivo:** cerrar C5-050+C5-039 (HIGH #2): cliente GenAI instanciado por request amplificaba 429 RESOURCE_EXHAUSTED en Turn 1 y latencia/cuota (whatsapp.py :906/:1308/:1406 → ai_brain.py :274).
  - **Implementación:** app/services/genai_client_service.py — singleton cache por clave determinística (_client_key), locks sync/async, telemetría _CLIENT_REUSE_COUNTS; app/main.py — warm-up asíncrono en _run_deferred_initialization con _GENAI_WARMUP_TIMEOUT_S=30.0, asyncio.shield + wait_for, recuperación anti-zombie, app.state.genai_client_failed y /health enriquecido; app/services/ai_brain.py + app/services/audio_service.py — consumidores al cliente compartido, resolución ADC sin credentials= para estabilizar clave de cache, tag log `[GEMINI ERROR FORENSIC]`.
  - **Pins:** tests/test_genai_client_singleton_050.py P1–P9 (+ P5b/P5c): share same client, factory patched, ZSF None-on-error, reuse log, 429 forense sin PII, reset identity, audio dual-key, thread-safe, async reuse. tests/test_genai_client_warmup_050.py P10a/P10b: timeout 30s + natural completion success → genai_client_ready=True; timeout + failure → fail-closed real, no zombie.
  - **Eval:** Score 1.000 ≥ 0.9 — DEPLOY AUTHORIZED ✅. Deploy Cloud Run run 31668757288 (#465), 2026-08-13T04:59:17Z, success.
  - **Verificación en vivo:** 2026-08-14 02:50Z — cliente compartido ♻️ age_s=78345s, 0×429 RESOURCE_EXHAUSTED, /health sano.
  - **Cambio acotado:** app/services/genai_client_service.py (singleton cache/locks/telemetría), app/main.py (~60 líneas warm-up/health), app/services/ai_brain.py (1 edit tag log + ADC), app/services/audio_service.py (ADC), tests/test_genai_client_singleton_050.py (+22 líneas), tests/test_genai_client_warmup_050.py (nuevo, 114 líneas). Núcleos intactos: juan_pablo_personality, prompts.py, _fallback_response, run_checker, enforce_length, _build_pcc_fallback, egress_guard_service.py, PCC.
  - **Colaterales descubiertos en vivo:** C5-067..C5-074 (ver bloque Colaterales abiertos).

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
- **C5-037:** CERRADO EN VIVO 2026-08-12 (v10.71.0) — backstop PRICE-LOCK v2; prueba en vivo ✅ 6:24 p.m.: precio $8.329.000 visible + imagen + Ficha + cierre (escenario "moto automática a crédito").
- **C5-060:** text-only path PASO 1 con crédito (URL-Lock reject sin sustituto) decapita $ en _send_whatsapp_message :2782 sin wrapper. Diferido.
- **C5-061:** getter chains de ai_brain.py prefieren price (int) sobre formatted_price en 7 sitios → 💰 sin $ en rutas deterministas salvage/fallback. Requiere orden literal C-29.
- **C5-062:** CERRADO — espejo STATE/ROADMAP de v10.70.0 y tags faltantes curados en este WARP-SYNC (tag retroactivo v10.70.0 en 3f41148 + v10.71.0).
- **C5-063:** sin log del caption pre-coerción verbatim (forense de egreso ciego al contenido). Diferido; R3 mitiga con reason de T3.
- **C5-064:** CERRADO (v10.73.0) — _price_lock_failure_reason emite anchor_merged_but_truncated cuando el merge existió pero se perdió post-coerción; no_compact_anchor solo sin merge posible. Verificado por mordida P20 + log en vivo.
- **C5-065:** ancla SOAT duplicada visible: _ensure_soat_anchor añade "(SOAT, Matrícula y trámites incluidos)" aunque el modelo ya la emitió. Requiere orden literal C-29 (toca ai_brain.py). Diferido.
- **C5-066:** otel trace_exporter ERROR "Failed to export span batch"; sin impacto de negocio. Incluir en monitoreo Beta. Diferido.
- **C5-050 + C5-039:** CERRADO EN VIVO 2026-08-14 (v10.72.0) — cliente genai por-request reemplazado por singleton compartido + warm-up anti-zombie; verificación en vivo 02:50Z: 0×429, /health sano.
- **C5-067** (LOW): ROADMAP.md aún lista colaterales de PRICE-LOCK-037 sin C5-065/C5-066 (micro-deriva documental). Diferido.
- **C5-068** (LOW): identidad git local sin configurar — commits autoralizados con hostname (tobiasgaitangallego@MacBook-Air-de-Tobias.local); configurar user.name/user.email.
- **C5-069** (MEDIUM): warm-up genai sin retry background: fallo duro de ADC en arranque = 503 permanente hasta restart (decisión de producto). Diferido.
- **C5-070** (LOW): typo legacy de proyecto en audio ("tiendali_las_motos") preexistente; sin regresión con R2. Diferido.
- **C5-071** (LOW): alertas/dashboards GCP que filtren por el tag viejo [GEMINI 429 FORENSIC] requieren update manual (0 refs en repo; análogo a C5-053).
- **C5-072** (LOW): acoplamiento implícito test_audio_regression ↔ fixture isolate_genai_shared_clients (documentado; sin acción).
- **C5-073** (LOW): warm-up hardcodea project="tiendalasmotos" mientras audio resuelve vía env/ADC; divergencia = 1 creación extra de cliente en primer uso de audio (no regresión).
- **C5-074:** CERRADO EN VIVO (v10.73.0) — Rescue T3 _price_lock_rescue_top4 + pines P17-P22 (P22 greeting-filter determinista). Prueba en vivo 2026-08-14 12:06 p.m. GMT-5 (Beta run #466): $8.329.000 visible post-coerción, rescue T3 operando, 0×429.
- **C5-075** (LOW): prefijo '💰 Precio:' duplicado en saludo no-canónico que ya lo contiene — cosmético, fuera de scope, documentado en P22.
- **C5-076** (LOW): Rescue T3 price-only sin nombre de modelo en el texto. Detección: prueba en vivo v10.73.0, turno 2026-08-14 12:06 p.m. GMT-5 (escenario "Hola, quiero una moto automática a crédito"): _FICHA_MODEL_RE no matcheó y _price_lock_rescue_top4 inyectó solo la línea "💰 Precio: $8.329.000 (incluye SOAT, Matrícula, y trámites)" (caso COND-1 price-only del build 074); la imagen llegó vía CANON-015 pero el caption no nombra la moto ni lleva "Ficha Tecnica: <modelo>". PASO 1 pide información detallada + imagen + precio; el texto cumple precio pero omite el detalle del modelo. Impacto cosmético-comercial; sin pérdida de $ ni regresión. Adyacentes: C5-075 (prefijo 💰 duplicado), familia C5-060/C5-064. Estado propuesto: DIFERIDO (cola P5 de colaterales). Evidencia física: captura WhatsApp 12:06 p.m. (caption sin modelo + imagen Victory New Life) + commit 46f3a94 (v10.73.0) en origin/beta.
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

**Previous:** BOT-BUILD-GENAI-SINGLETON-050 (v10.72.0) — Singleton cliente GenAI compartido + warm-up anti-zombie (cierre C5-050/C5-039).
**Next:** bundle C-29 (C5-061+C5-065, AGUARDA ORDEN LITERAL de Tobias) → E2E WhatsApp → observabilidad (C5-066, C5-071) → C5-045 → colaterales C5-067..C5-073, C5-075. C-30 agotada; C-31 sin emitir (no requerida para 074: whatsapp.py zona mutable).

### Tooling local (MCP, sin bump documental — BOT-BUILD-GRAPHIFY-MCP-024)
- `graphify-backend` MCP registrado en ~/.config/opencode/opencode.json (bloque local vía /opt/homebrew/bin/uv + graphifyy 0.9.38 + graph.json; timeout 30000; enabled true). Invariante serena intacto (SHA-256 canónico 24545b4f…bbffc). Completado: reinicio + panel MCP verificado (graphify-backend Connected + serena Connected) + graph_stats coherente con GRAPH_REPORT.md — 2026-08-11.

---
*Last updated: 2026-08-15*
