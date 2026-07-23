# PYTEST AUTOPSY — Wave 05-06: Latencia Forense y Cierre de Etapa 3 (RF-5)

**Ticket:** BOT-BUILD-ETAPA3-WAVE06-LATENCY-CLOSE-001
**Fecha:** 2026-07-22
**Ejecutor:** OPENCODE BUILDER
**Resultado:** ✅ **CERTIFICADO — 431/431 + 2 subtests PASSED, 0 failed, 0 RuntimeWarnings, Coherence Score 1.000 — ETAPA 3 (RF-5) CERRADA**

---

## 1. Veredicto cuantitativo

| Métrica | Baseline pre-wave | Post-wave | Delta |
|---|---|---|---|
| Suite directa (`pytest tests/ -q`) | 423 passed + 2 subtests | **431 passed + 2 subtests** | **+8 pins forenses, 0 regresiones** |
| Modo estricto (`-W error::RuntimeWarning`) | — | **431 passed** | **0 RuntimeWarnings** |
| Arnés eval (`npx agent-cli eval`) | — | **436 total, 0 failed** | **Score 1.000 ≥ 0.95** ✅ |
| Archivos creados | — | **1 (`tests/test_latency_forensics.py`)** | Alcance exacto del ticket |
| Remediaciones Zero-Silent-Failures | 2 sitios `except: pass` | **0 sitios** | Mandato de auditoría §3 |
| RF-5 en REQUIREMENTS.md | Open | **Done** | Sincronía GSD |

Inmunización BOT-174 contra el contaminante heredado:
`pytest tests/test_pcc_ficha_tecnica.py tests/test_latency_forensics.py -q` → **53 passed**.

---

## 2. Escenarios de caos ejecutados (vector corregido: httpx + firestore.AsyncClient)

### LAT-1 — Latencia ≥10s en Meta API (`patch httpx.AsyncClient.send`)

**Mecánica:** compuerta determinista (`asyncio.Event`) en lugar de un sleep fijo de 10s —
simula latencia Meta **no acotada** (superset del escenario 10s) con el test ejecutándose
en milisegundos. Cadena real de egreso (`_pipeline_egress` → `_process_and_send_egress_message`
→ `_send_whatsapp_message` → `whatsapp_service` singleton real → httpx mockeado); el impl
corre como tarea concurrente mientras el envío queda EN VUELO.

**Aserción certificada:** con Meta bloqueado en vuelo, `save_message:model` (estado del
turno) **ya está persistido** — `timeline.index(save:model) < timeline.index(meta:send_start)`.
El hilo de estado no se bloquea detrás de la red externa; al liberar la compuerta el embudo
completa limpio. Nota: `mark_as_read` (READ-FIRST) se mockea a nivel servicio — excepción
sancionada de acuse, fuera del conjunto de envíos (Wave 05-01 §2).

### LAT-2 — Timeout Firestore (latencia 10s > db_timeout=5)

- **LAT-2a (contrato):** `_ContingencySnapshot` es el documento vacío controlado
  (`exists is False`, `to_dict() == {}`) — anti-AttributeError pineado.
- **LAT-2b (vector):** `mock_firestore_with_latency(10.0)` con `db_timeout=5` (default de
  `app/core/config.py` — coincide con el ticket sin parcheo). `_firestore_io` eleva
  `asyncio.TimeoutError` **explícito** (Zero-Silent-Failures — comportamiento sancionado por
  `test_bot_bug_044`: jamás tragar el fallo retornando el snapshot) y la escritura cancelada
  por `wait_for` **jamás se confirma** (`write_confirmed is False`) — la colección
  `prospectos` no se corrompe.
- **LAT-2c (embudo):** bajo timeout en el save de usuario, el turno aborta con mensaje de
  contingencia ("intermitencias") y **cero mutación transicional** (`generate_and_update_summary`,
  `set_human_help_status`, `update_prospect_summary`, `get_prospect_data` jamás invocados).

### LAT-3 — Fallo intermitente `calculate_credit_score` (side_effect en cerebro)

**Freno Cognitivo certificado:**
(a) el Juez **jamás audita** una respuesta inexistente (`analyze_response` no llamado);
(b) el único texto que egresa es el **fallback supervisado oficial** (1 solo envío);
(c) **cero alucinación** de marcadores sintéticos de precio (`not re.search(r"\$\s?\d", texto)`);
(d) mandato v9.8.3: `set_human_help(True)` → `DEPRIORITIZED` ≺ envío del fallback.

**⚠️ HALLAZGO FORENSE (pin de comportamiento vigente, NO normalizado):** la rama
`JUDGE_CRITICAL_ERROR` ordena **send ≺ save(model)** del fallback — asimetría respecto de
la rama de rechazo del Juez (**save ≺ send**, pineada por ORDER-FALLBACK en Wave 05-01).
Ambas persisten el estado y marcan human-help antes de la red; solo difiere el orden
save/send del propio fallback. Pineada como vigente (Feathers) en LAT-3 con documentación
explícita; su normalización queda como candidata a fase futura con aprobación del Auditor.

---

## 3. Auditoría Zero-Silent-Failures (remediaciones mandadas)

Escaneo AST del eje transaccional reveló exactamente 2 bloques `except …: pass` sin logger.
Remediados con **observabilidad únicamente** (control de flujo idéntico — siguen tragando
la excepción opcional, ahora con registro forense y correlation ID):

| # | Sitio | Contexto | Remediación |
|---|---|---|---|
| 1 | `app/routers/whatsapp.py` (HANDOFF en `_pipeline_egress`) | `except ImportError: pass` — import de `notification_service` | `logger.warning` con E.164 (canal opcional, ausencia forense) |
| 2 | `app/services/memory_service.py` (`update_last_interaction`) | `except Exception: pass` — observación Langfuse opcional | `logger.warning` con E.164 (Langfuse no bloquea Firestore) |

Nota de alcance: el ticket lista `files_to_modify` = solo docs, pero el mandato
`resilience_audit` exige la ausencia total de estos bloques; las 2 líneas de logger son la
única vía de satisfacerlo. Se reportan transparentemente al Auditor como micro-remediaciones
mandadas (sin cambio de lógica de control). Regresión de los archivos tocados verificada:
24/24 (egress + E2E + ORDER + infra_33 + bot_bug_044).

| Aserción de auditoría | Resultado |
|---|---|
| AUD-1: cero `except: pass` sin logger en el eje (3 archivos) | ✅ 0 violaciones post-remediación (pin AST) |
| AUD-2: `e.response.text` obligatorio en manejadores HTTPStatusError | ✅ ≥2 por archivo (router + servicio Meta), pin AST |
| AUD-3: Correlation ID (E.164 + wamid) en traza raíz | ✅ `update_current_trace(user_id=E.164, session_id=wa_E164, metadata.msg_id=wamid)` pin funcional |

---

## 4. Sincronía documental GSD ejecutada

| Acción | Archivo | Estado |
|---|---|---|
| RF-5 (Fragmentación de God Node) marcado **Done** con referencias de certificación | `.planning/REQUIREMENTS.md` | ✅ |
| Phase actual = Milestone 3 - Etapa 3 **COMPLETED** (v10.46.0, resumen de las 6 waves, Next = despliegue beta F5) | `.planning/STATE.md` | ✅ |
| Hito Etapa 3 agregado a Tasks Completadas (v10.46.0) + fecha de actualización | `.planning/ROADMAP.md` | ✅ |

---

## 5. Cumplimiento de constraints

| Constraint | Estado | Evidencia |
|---|---|---|
| Lógica comercial `ai_brain.py` / `juan_pablo_personality` intacta | ✅ | 0 archivos de lógica tocados (solo 2 líneas de logger forense) |
| Visual-Lock (PCC Pro) / Markdown intactos | ✅ | Sin cambios; pins PEI/MVI siguen verdes |
| Guardrail `register_wamid` intacto | ✅ | Frontera sin cambios |
| Locks de sesión `asyncio.Lock` por E.164 intactos | ✅ | Sin cambios |

---

## 6. Comandos de verificación ejecutados

```bash
# Baseline pre-wave
.venv/bin/python -m pytest tests/ -q                                    # 423 passed, 2 subtests
# Regresión de los archivos remediados
.venv/bin/python -m pytest tests/test_pipeline_egress_integrity.py tests/test_webhook_integrity_e2e.py \
  tests/test_state_persistence_order.py tests/test_infra_33_timeout.py tests/test_bot_bug_044.py -q   # 24 passed
# Pins nuevos aislados
.venv/bin/python -m pytest tests/test_latency_forensics.py -v           # 8 passed
# Inmunización contra el contaminante heredado
.venv/bin/python -m pytest tests/test_pcc_ficha_tecnica.py tests/test_latency_forensics.py -q   # 53 passed
# Suite completa, ambos modos
.venv/bin/python -m pytest tests/ -q                                    # 431 passed, 2 subtests
.venv/bin/python -m pytest tests/ -q -W error::RuntimeWarning           # 431 passed (0 RuntimeWarnings)
# Prueba de Fuego
npx agent-cli eval                                                      # 436 total, 0 failed — Score 1.000 — DEPLOY AUTHORIZED
```

---

## 7. Cierre de Etapa 3 (RF-5) — estado final del God Node

| Métrica | Inicio Etapa 3 (pre 05-01) | Final (post 05-06) |
|---|---|---|
| `_handle_message_background_impl` | Monolito ~1140 líneas / 5 ramas acopladas a globals | **Orquestador switch lineal puro: 231 líneas de código efectivo (345 físicas)** |
| Pipelines | 0 | **6** (`_pipeline_reaction_debounce`, `_pipeline_media_vision`, `_pipeline_text_cognitive`, `_pipeline_audio`, `_pipeline_egress` + egreso unificado `_process_and_send_egress_message`) |
| Costuras DI | 0 (globals leídos inline) | **4 kwargs runtime** propagados (catalog / vision_factory / db_client / meta_sender) + senders + resolve_query_aliases |
| Fire-and-forget en el eje | 0 verificado | **0 certificado por AST** (`test_zero_fire_and_forget.py`) |
| Silent failures (`except: pass`) | 2 | **0** |
| Tests | 373 + 2 subtests | **431 + 2 subtests** (+58 pins: 12 CH/E2E/ORDER, 4 FF, 8 DI, 11 MVI/AI, 15 PRI/TCI/PEI, 8 LAT/AUD) |
| Coherence Score | — | **1.000** |

- [x] 423+N tests PASSED → **431/431 + 2 subtests** (arnés eval: 436)
- [x] 0 RuntimeWarnings
- [x] Coherence Score ≥ 0.95 → **1.000**
- [x] RF-5 marcado **Done** en REQUIREMENTS.md
- [x] STATE.md / ROADMAP.md sincronizados (Milestone 3 - Etapa 3 COMPLETED)
- [x] Autopsia final entregada

**DETENIDO según mandato del ticket. En espera de certificación del Auditor para el
despliegue a beta (F5).**
