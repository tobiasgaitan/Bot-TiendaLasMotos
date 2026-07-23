# PYTEST AUTOPSY — Wave 05-05: Fragmentación texto-cognitivo + consolidación egreso (Etapa 3)

**Ticket:** BOT-BUILD-ETAPA3-WAVE05-FRAGMENT-TEXT-EGRESS-001
**Fecha:** 2026-07-22
**Ejecutor:** OPENCODE BUILDER
**Resultado:** ✅ **CERTIFICADO — 423/423 + 2 subtests PASSED, 0 failed, 0 RuntimeWarnings, Coherence Score 1.000**

---

## 1. Veredicto cuantitativo

| Métrica | Baseline pre-wave | Post-wave | Delta |
|---|---|---|---|
| Suite directa (`pytest tests/ -q`) | 408 passed + 2 subtests | **423 passed + 2 subtests** | **+15 pins de paridad, 0 regresiones** |
| Modo estricto (`-W error::RuntimeWarning`) | — | **423 passed** | **0 RuntimeWarnings** |
| Arnés eval (`npx agent-cli eval`) | — | **428 passed + 2 skipped** | **Score 1.000 ≥ 0.95** ✅ |
| Archivos `app/` modificados | — | **1 (`app/routers/whatsapp.py`)** | Alcance exacto (extracción intra-archivo) |
| Archivos creados | — | **3 (tests de integridad de pipelines)** | Alcance exacto del ticket |

Inmunización BOT-174 contra el contaminante heredado (los 3 archivos nuevos coleccionan
DESPUÉS de `test_pcc_ficha_tecnica.py`): `pytest tests/test_pcc_ficha_tecnica.py
tests/test_pipeline_reaction_integrity.py tests/test_pipeline_text_cognitive_integrity.py
tests/test_pipeline_egress_integrity.py -q` → **60 passed** (todos los arneses que
alcanzan el guard configuran `get_or_create_prospect` explícito).

---

## 2. Extracción ejecutada (sprout methods intra-archivo — movimiento VERBATIM)

Cirugía programática con aserciones de frontera en cada corte (cero transcripción
manual). El primer intento abortó limpio por off-by-one detectado por las aserciones;
segundo intento exitoso sin tocar una instrucción lógica.

| Pipeline | Origen | Destino | Contrato |
|---|---|---|---|
| `_pipeline_reaction_debounce` | rama `if msg_type == "reaction"` (L813–849, 36 líneas) | función módulo L1714–1775 | `(payload, db_client=None, meta_sender=None, **ctx) -> Optional[str]` — devuelve el cuerpo agregado; **None = salida temprana** (tarea superada / cuerpo vacío). El impl muta `msg_type→"text"` solo con retorno no-None (paridad exacta del fall-through pineado por E2E-REACTION) |
| `_pipeline_text_cognitive` | rama `if msg_type == "text"` (L1007–1251, 245 líneas) | función módulo L1778–2065 | `(payload, catalog=None, db_client=None, meta_sender=None, **ctx) -> tuple` — `(response_text, prospect_data)`; **None = fallback del Juez / error crítico ya enviado** |
| `_pipeline_egress` | bloque post-rama `if response_text:` (L1271–1328, 58 líneas: HANDOFF + PHASE_GATE) | función módulo L2068–2155 | `(response_text, image_url=None, meta_sender=None, **ctx) -> None` — consolida HANDOFF/PHASE_GATE y **delega el envío unificado en `_process_and_send_egress_message`** |

### Decisión de diseño auditable — consolidación del egreso SIN romper CH-5

El ticket ordena "consolidar `_pipeline_egress` (L1765–1822 + `_process_and_send_egress_message`)
en un único método coherente". El pin heredado **CH-5** (`test_characterization_etapa1`)
exige `mock_egress.assert_called_once_with(PHONE, text, phone_number_id=…)` sobre el
nombre `_process_and_send_egress_message`, y 2 pins más lo parchean (CH-3, E2E-IMAGE
vía `_pipeline_media_vision`). Por tanto: `_pipeline_egress` absorbe la orquestación
post-rama (HANDOFF + PHASE_GATE) y **delega** el envío unificado llamando a
`_process_and_send_egress_message(user_phone, response_text, phone_number_id=…)` con
la firma exacta preservada. El método queda "único y coherente" desde la perspectiva
del orquestador (un solo punto de egreso) sin romper los 25 patch targets heredados.
`image_url`/`meta_sender`/`payload`/`db_client` quedan como costuras RESERVADAS por
simetría de firma (documentado en cada docstring), igual que en waves 03/04.

### Orquestador final — criterio <300 cumplido

| Métrica `_handle_message_background_impl` | Wave 05-03 | Wave 05-04 | **Wave 05-05** |
|---|---|---|---|
| Span físico (líneas, docstring incluido) | 1167 | 633 | **345** |
| Líneas de código efectivas (sin blancos/comentarios) | 839 | 433 | **231** |

**231 < 300 líneas de código efectivo** ✅ — switch lineal puro: extracción →
idempotencia buffer → READ-FIRST (mark_as_read) → bifurcación por tipo
(reaction/media/text/audio) → delegación al pipeline → egreso consolidado →
envolvente catastrófico `CRITICAL_CODE_FAULT` intacto. La gestión de sesión
(apertura CRM, comandos /reset y /update, blindaje zombi, human-gate) permanece
inline por alcance del ticket.

---

## 3. Pins instaurados (15 tests)

### tests/test_pipeline_reaction_integrity.py (5)

| Pin | Aserción | Evidencia |
|---|---|---|
| PRI-1 | "Paridad de escritura habeas_data_accepted_sent" | `update_prospect_summary(PHONE, "", {"habeas_data_accepted": True, "ponytail_status": "PENDING"})` await­ed (bloqueante); retorno "Sí" |
| PRI-2 | Salidas tempranas | Tarea superada ⇒ None sin agregación ni escritura; cuerpo vacío ⇒ None |
| PRI-3 | Debounce | Cuerpo agregado prevalece; `clear_buffer` await­ed |
| PRI-4 | "Patch targets de MessageBuffer sobreviven" | Buffer global parcheado controla ventana/superseding/agregación |
| PRI-5 | "register_wamid intacto" + cableado | `add_message(PHONE, "Sí", wamid)` pre-delegación; reacción 👍 continúa como text con cuerpo mutado alimentando `_pipeline_text_cognitive` (quick-138) |

### tests/test_pipeline_text_cognitive_integrity.py (5)

| Pin | Aserción | Evidencia |
|---|---|---|
| TCI-1 | "Paridad de invocación a pensar_respuesta (mismos argumentos)" | 1 await con input=message_body, context, history, skip_greeting y prospect_data["phone"] inyectado |
| TCI-2 | "Paridad de escrituras Firestore" + "generate_and_update_summary bloqueante" | sync(last_bot_question anclado) ≺ re-fetch ≺ pensar ≺ save(model=aprobada) |
| TCI-3 | "Human-help post-sync y fallback del Juez preservados" (mandato v9.8.3) | 3 intentos ⇒ set_human_help(True) → DEPRIORITIZED → save(model fallback) → envío fallback; retorno (None, prospect) |
| TCI-4 | "Patch targets de CerebroIA/catálogo sobreviven" | kwarg catalog prioritario; fallback al global parcheado |
| TCI-5 | Cableado | impl delega con ctx completo (cerebro_ia de sesión incl.) y egresa el texto retornado |

### tests/test_pipeline_egress_integrity.py (5)

| Pin | Aserción | Evidencia |
|---|---|---|
| PEI-1 | "Paridad de llamadas al envío unificado" | Firma exacta CH-5: `(PHONE, text, phone_number_id=…)`; cero efectos colaterales |
| PEI-2 | HANDOFF | set_human_help(True) → DEPRIORITIZED → transferencia → `notify_human_handoff`; sin envío unificado |
| PEI-3 | PHASE_GATE + costura catalog | Imagen dinámica `Mira esta {Nombre}\n\n{texto}` + save(model); kwarg prioritario / fallback "RAIDER 125" al global |
| PEI-4 | Bypass moto confirmada | Sin imagen; texto despojado al envío unificado |
| PEI-5 | "Visual-Lock PCC Pro intacto" + BOT-125 | Markdown `![alt](url)` → `_send_whatsapp_image` con caption limpio + eco save(model) posterior al envío |

Regresión integral pre-suite del subconjunto de alto riesgo (waves 01–04 + concurrencia):
**65 passed** (E2E/ORDER/CH/DI/MVI/AI/audio_regression/identity/zombie/zero_silent/
router_concurrency/eventloop_latency).

---

## 4. Cumplimiento de constraints del ticket

| Constraint | Estado | Evidencia |
|---|---|---|
| Sin movimiento a submódulos | ✅ | Los 5 pipelines + egreso viven en `app/routers/whatsapp.py`; namespace plano intacto |
| Lógica comercial `ai_brain.py` / `juan_pablo_personality` intacta | ✅ | 0 archivos tocados fuera del router |
| Visual-Lock (PCC Pro) / Markdown intactos | ✅ | Movimiento VERBATIM + pin PEI-5 |
| Guardrail `register_wamid` intacto | ✅ | Frontera sin cambios + pin PRI-5 |
| Locks de sesión `asyncio.Lock` por E.164 intactos | ✅ | `_handle_message_background`/`_get_session_lock` sin cambios |
| Sin `asyncio.create_task` en escrituras de estado | ✅ | `test_zero_fire_and_forget.py` 4/4 PASSED |
| Envolvente catastrófico intacto | ✅ | `CRITICAL_CODE_FAULT` cubre las 4 delegaciones + egreso |

---

## 5. Comandos de verificación ejecutados

```bash
# Baseline pre-wave
.venv/bin/python -m pytest tests/ -q                                    # 408 passed, 2 subtests
# Regresión quirúrgica post-extracción (alto riesgo, waves 01–04 + concurrencia)
.venv/bin/python -m pytest tests/test_webhook_integrity_e2e.py tests/test_state_persistence_order.py \
  tests/test_characterization_etapa1.py tests/test_audio_regression.py tests/test_di_seams_integrity.py \
  tests/test_pipeline_media_vision_integrity.py tests/test_pipeline_audio_integrity.py \
  tests/test_identity_legal_gate.py tests/test_zero_silent_failures_whatsapp.py \
  tests/test_zombie_recovery_flow.py tests/test_router_concurrency.py tests/test_eventloop_latency.py -q
                                                                        # 65 passed, 2 subtests
# Pins nuevos aislados
.venv/bin/python -m pytest tests/test_pipeline_reaction_integrity.py -v      # 5 passed
.venv/bin/python -m pytest tests/test_pipeline_text_cognitive_integrity.py -v # 5 passed
.venv/bin/python -m pytest tests/test_pipeline_egress_integrity.py -v         # 5 passed
# Inmunización contra el contaminante heredado
.venv/bin/python -m pytest tests/test_pcc_ficha_tecnica.py tests/test_pipeline_reaction_integrity.py \
  tests/test_pipeline_text_cognitive_integrity.py tests/test_pipeline_egress_integrity.py -q   # 60 passed
# Suite completa, ambos modos
.venv/bin/python -m pytest tests/ -q                                    # 423 passed, 2 subtests
.venv/bin/python -m pytest tests/ -q -W error::RuntimeWarning           # 423 passed (0 RuntimeWarnings)
# Prueba de Fuego
npx agent-cli eval                                                      # 428 passed, 0 failed — Score 1.000 — DEPLOY AUTHORIZED
```

---

## 6. Cierre

- [x] 408+N tests PASSED → **423/423 + 2 subtests** (arnés eval: 428 + 2 skipped)
- [x] 0 RuntimeWarnings (verificado con `-W error::RuntimeWarning`)
- [x] Coherence Score ≥ 0.95 → **1.000**
- [x] `_handle_message_background_impl` = **231 líneas de código efectivo (<300)** — orquestador switch lineal puro
- [x] Autopsia entregada

**DETENIDO según mandato del ticket. En espera de certificación del Auditor para
arrancar Wave 05-06 (latencia forense + cierre de Etapa 3).**
