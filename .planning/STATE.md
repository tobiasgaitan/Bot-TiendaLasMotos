# Estado del Proyecto - Bot-TiendaLasMotos

Versión: v10.75.0 | Hito: BOT-BUILD-PARITY-C31-077 — Restauración de paridad repo↔Firestore de juan_pablo_personality bajo orden literal C-31 (cierre C5-080/C5-083) — BUILD COMPLETE | Coherence Score: 1.000 (881 recolectados físico = 876 tests/ + 5 scripts/; 881/881 PASSED; 0 failed; 0 skipped)

### Current Position
**Phase:** BOT-BUILD-PARITY-C31-077 (v10.75.0) — restauración de paridad repo↔Firestore de `juan_pablo_personality` bajo orden literal C-31. Injerto verbatim de `<REGLA_DE_CIERRE_DE_FASE>` en `app/core/prompts.py` (L80→L81) y `app/core/personality.json["system_instruction"]`; canal único `scripts/sync_full_prompt.py` con triple aserción post-sync y evidencia archivada. Gate D4 detectó deltas adicionales no autorizados en Firestore vivo (hot reload revirtió consentimiento confirmado y gas-gate); se canonicalizó Firestore al SSOT repo certificado preservando el bloque vivo. Eval 881/881 Score 1.000.
**Status:** BUILD COMPLETE (v10.75.0):
  - **Objetivo:** cerrar la deriva repo↔Firestore de `juan_pablo_personality` tras hot reload manual de `<REGLA_DE_CIERRE_DE_FASE>` (C5-080 cerrado en vivo) sin perder la regla viva y sin regresión de la doctrina certificada.
  - **Implementación:** `app/core/prompts.py` + `app/core/personality.json` — injerto aditivo del bloque `<REGLA_DE_CIERRE_DE_FASE>`; `scripts/sync_full_prompt.py` — write forense local→Firestore y read-back con `parity_byte_exact`, `crediorbe_eradicated_remote`, `brilla_and_nuestro_sistema_present_remote`.
  - **Pins estáticos locales:** `test_fix_catalog_profile_001.py`, `test_brilla_conmutacion.py`, `test_firestore_nomenclature_extraction.py`, `test_fix_habeas_extraction_004.py`, `test_no_entity_hardcode_in_user_strings.py`, `test_fix_catalog_profile_001_v2.py`, `test_cierre_rutas_010.py` → todos verdes. Guard FIX-E `test_firestore_personality_matches_ssot_forensic_triple_assertion` pasa tras sync write.
  - **Mordidas:** M1 quitar bloque solo de `prompts.py` → pin `pj == py` FAIL; M2 quitar bloque de ambos espejos → `sync_full_prompt.py --check` `parity_byte_exact` FAIL.
  - **Eval:** Score 1.000 ≥ 0.9 — DEPLOY AUTHORIZED ✅. 881/881 PASSED; collect-only 881 (876 tests/ + 5 scripts/).
  - **Cambio acotado:** 2 archivos de espejo SSOT + canal de sync intacto. C4 intacto: sin toques a `ai_brain.py`, `_fallback_response`, `enforce_length`, `egress_guard_service.py`.
  - **Colaterales:** C5-083 registrado (drift no autorizado por hot reload: ventana 2026-08-15 03:30→05:25 UTC, remote sha `d719107b…`; consentimiento y gas-gate revertidos; resuelto por canonicalización repo→Firestore). Pendiente operacional: `POST /api/admin/refresh-config` en Beta para invalidar caché de instancias calientes.

### Posición anterior (BOT-BUILD-BUFFER-PCC-076)
**Phase:** BOT-BUILD-BUFFER-PCC-076 (v10.75.0) — `clear_messages(wa_id)` en `app/services/message_buffer.py` drena `_buffers` preservando `_active_tasks` y WAMID registries; drenaje de frontera en `app/routers/whatsapp.py` solo para `msg_type != "reaction"`; bypass PCC estrecho en `app/services/agentic_loop_service.py` para `PHASE_2_HABEAS_DATA` post-habeas con identidad pendiente y `bot_response` pregunta legítima de recolección de identidad. 5 pines P1-P5 + mordidas M1'/M1''/M2/M3. Eval 881/881 Score 1.000.
**Status:** BUILD COMPLETE (v10.75.0):
  - **Objetivo:** cerrar la re-agregación de mensajes previos en un turno de reacción 👍 (Fix A) y la colisión `PHASE_2_HABEAS_DATA` × PCC estricto que exige $/imagen mientras la instrucción de fase los prohíbe (Fix B).
  - **Implementación:** `app/services/message_buffer.py` — `async def clear_messages(wa_id)`; `app/routers/whatsapp.py` — `await message_buffer.clear_messages(user_phone)` bajo `if msg_type != "reaction"`; `app/services/agentic_loop_service.py` — `identity_pending_post_habeas` + `_is_identity_collection_prompt(bot_response)`.
  - **Pins:** `tests/test_reaction_buffer_phase_bypass_076.py` P1-P5 (5 pines). Mordidas: M1' borrar active_task → P1 FAIL; M1'' comentar drenaje frontera → P5 FAIL; M2 bypass sin chequeo de prompt → P3b FAIL; M3 ignorar habeas_data_accepted → P4 FAIL.
  - **Eval:** Score 1.000 ≥ 0.9 — DEPLOY AUTHORIZED ✅. 881/881 PASSED; collect-only 881 (876 tests/ + 5 scripts/).
  - **Cambio acotado:** 3 archivos de producción + 17 archivos de tests con mocks de `message_buffer` (una línea `.clear_messages = AsyncMock()` por mock) + test nuevo. C4 intacto: sin toques a `ai_brain.py`, `prompts.py`, `personality.json`, `_fallback_response`, `enforce_length`, `egress_guard_service.py`.
  - **Colaterales:** C5-078 (`_build_pcc_fallback` ciego a fase; podría emitir $/imagen en `PHASE_2_HABEAS_DATA`; DIFERIDO).

### Posición anterior
**Phase:** BOT-BUILD-C29-075 (v10.74.0) — _canonical_top_price en ai_brain.py (precedencia SSOT: price numérico>0 → build_commercial_price recompute en try/except exception-safe + logger.exception sin PII → formatted_price → price string → precio → '') reemplaza 9 getter chains int-over-formatted; _ensure_soat_anchor idempotente (_SOAT_MENTION_RE \bsoat\b IGNORECASE; mención → retorno byte-idéntico; append solo si \$[\d.,]+\b y sin mención; PRICE_PACKAGE_ANCHOR SSOT). Orden literal C-29; C4 intacto; 8 pines P1-P7+P3b + mordidas M1'/M1''/M2/M5/M3/M4. Review externa F3.5 (sign-off P3b + RF-2) + F4.5-bis DIFF APTO D1-D9. Eval 876/876 Score 1.000.
**Status:** BUILD COMPLETE (v10.74.0):
  - **Objetivo:** cerrar C5-061 (💰 sin $ en rutas deterministas salvage/fallback por getter chains int-over-formatted en 9 sitios) + C5-065 (ancla SOAT duplicada visible por pre-check literal evadible).
  - **Implementación:** app/services/ai_brain.py — helper _canonical_top_price (recompute-first exception-safe, guard price>0) en 9 call sites (L1390, L1442, L2243, L2269, L2347, L2438, L2457, L2581, L3335) + _ensure_soat_anchor idempotente con _SOAT_MENTION_RE y PRICE_PACKAGE_ANCHOR.
  - **Pins:** tests/test_c29_salvage_price_soat_074.py P1-P7+P3b (8 pines). Mordidas: M1' formatted-first → P2 FAIL; M1'' sin guard price>0 → P7 FAIL; M2/M5 check débil → P3/P3b FAIL; M3 sin append → P4 FAIL; M4 inline reintroducida → P6 FAIL.
  - **Eval:** Score 1.000 ≥ 0.9 — DEPLOY AUTHORIZED ✅. 876/876 PASSED; collect-only 876 (871 tests/ + 5 scripts/).
  - **Review externa:** F3.5 (findings 1-4: sign-off P3b + RF-2 recompute-first/guard/nits) + F4.5-bis DIFF APTO (D1-D9 OK, SIN HALLAZGOS).
  - **Cambio acotado:** app/services/ai_brain.py + tests/test_c29_salvage_price_soat_074.py bajo orden literal C-29. Núcleos intactos: juan_pablo_personality, prompts.py, _fallback_response, enforce_length, egress_guard_service.py, whatsapp.py.
  - **Colaterales:** C5-077 (getter chain int-over-formatted en L2728, builder de contexto LLM; fuera de scope C-29).


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
- **C5-061:** CERRADO (v10.74.0) — getter chains de ai_brain.py preferían price (int) sobre formatted_price en 9 sitios (redefinido 7→9 con evidencia física: L1390, L1442, L2243, L2269, L2347, L2438, L2457, L2581, L3335) → 💰 sin $ en rutas deterministas. Cerrado vía _canonical_top_price (recompute-first + guard price>0) bajo orden literal C-29.
- **C5-062:** CERRADO — espejo STATE/ROADMAP de v10.70.0 y tags faltantes curados en este WARP-SYNC (tag retroactivo v10.70.0 en 3f41148 + v10.71.0).
- **C5-063:** sin log del caption pre-coerción verbatim (forense de egreso ciego al contenido). Diferido; R3 mitiga con reason de T3.
- **C5-064:** CERRADO (v10.73.0) — _price_lock_failure_reason emite anchor_merged_but_truncated cuando el merge existió pero se perdió post-coerción; no_compact_anchor solo sin merge posible. Verificado por mordida P20 + log en vivo.
- **C5-065:** CERRADO (v10.74.0) — ancla SOAT duplicada visible por pre-check literal case-sensitive evadible. Cerrado vía _SOAT_MENTION_RE (\bsoat\b IGNORECASE) idempotente bajo orden literal C-29; contrato P3b pineado (sign-off Finding 1).
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
- **C5-077** (LOW): getter chain int-over-formatted en L2728 (builder de contexto LLM, callback search_catalog) — mismo anti-patrón de C5-061 alimentando contexto del modelo, no la línea 💰 de egreso. Fuera de scope C-29 y fuera del universo vigilado de P6. Diferido.
- **C5-078** (LOW): `_build_pcc_fallback` en `ai_brain.py` es ciego a fase: si se activa durante `PHASE_2_HABEAS_DATA` post-habeas con identidad pendiente, puede emitir una respuesta con $/imagen, violando la instrucción de fase. Mitigado por el bypass estrecho de PCC-076 en `agentic_loop_service.py` para respuestas de recolección de identidad, pero el fallback en sí no fue modificado (requeriría orden literal C4). Diferido; monitorear en Beta.
- **C5-080** (CLOSED EN VIVO, v10.75.0): hot reload manual de `<REGLA_DE_CIERRE_DE_FASE>` en Firestore `configuracion/juan_pablo_personality` aplicado en producción. Cerrado bajo orden literal C-31 con injerto verbatim en `app/core/prompts.py` + `app/core/personality.json` y re-sync por `scripts/sync_full_prompt.py`. Evidencia archivada: `scripts/evidence/fix_e_prompt_sync_20260815T150101Z.json` (`parity_byte_exact=true`).
- **C5-083** (CLOSED, v10.75.0): deriva no autorizada repo↔Firestore causada por el hot reload de C5-080: ventana de mutación 2026-08-15 03:30→05:25 UTC, remote sha `d719107b…`, local sha `bce83315…`; el remoto revirtió silenciosamente la regla de consentimiento confirmado y el gas-gate de rutas R2–R4. Resuelto por canonicalización repo→Firestore tras gate D4; eval 881/881. Pendiente operacional: `POST /api/admin/refresh-config` en Beta para invalidar caché de instancias calientes.
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

**Previous:** BOT-BUILD-PRICE-LOCK-T3-074 (v10.73.0) — Rescue T3 PRICE-LOCK + etiqueta forense anchor_merged_but_truncated (cierre C5-074/C5-064).
**Next:** Operación `POST /api/admin/refresh-config` en Beta para invalidar caché de instancias calientes → E2E WhatsApp → observabilidad (C5-066, C5-071) → C5-045 → colaterales C5-067..C5-073, C5-075, C5-076, C5-077, C5-078. C-29, C-30 y C-31 ejecutadas y agotadas.

### Tooling local (MCP, sin bump documental — BOT-BUILD-GRAPHIFY-MCP-024)
- `graphify-backend` MCP registrado en ~/.config/opencode/opencode.json (bloque local vía /opt/homebrew/bin/uv + graphifyy 0.9.38 + graph.json; timeout 30000; enabled true). Invariante serena intacto (SHA-256 canónico 24545b4f…bbffc). Completado: reinicio + panel MCP verificado (graphify-backend Connected + serena Connected) + graph_stats coherente con GRAPH_REPORT.md — 2026-08-11.

---
*Last updated: 2026-08-16*
