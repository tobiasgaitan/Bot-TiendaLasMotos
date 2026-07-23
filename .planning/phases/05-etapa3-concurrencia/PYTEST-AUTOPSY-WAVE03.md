# PYTEST AUTOPSY — Wave 05-03: Costuras de Inyección de Dependencias (Etapa 3)

**Ticket:** BOT-BUILD-ETAPA3-WAVE03-DI-SEAMS-001
**Fecha:** 2026-07-22
**Ejecutor:** OPENCODE BUILDER
**Resultado:** ✅ **CERTIFICADO — 397/397 + 2 subtests PASSED, 0 failed, 0 RuntimeWarnings, Coherence Score 1.000**

---

## 1. Veredicto cuantitativo

| Métrica | Baseline pre-wave | Post-wave | Delta |
|---|---|---|---|
| Suite directa (`pytest tests/ -q`) | 389 passed + 2 subtests | **397 passed + 2 subtests** | **+8 pins DI nuevos, 0 regresiones** |
| Modo estricto (`-W error::RuntimeWarning`) | — | **397 passed** | **0 RuntimeWarnings** |
| Arnés eval (`npx agent-cli eval`) | — | **402 passed + 2 skipped** | **Score 1.000 ≥ 0.95** ✅ |
| Archivos `app/` modificados | — | **1 (`app/routers/whatsapp.py`)** | Alcance exacto del ticket |
| Archivos creados | — | **1 (`tests/test_di_seams_integrity.py`)** | Alcance exacto del ticket |

Inmunización BOT-174 verificada contra el contaminante heredado:
`pytest tests/test_pcc_ficha_tecnica.py tests/test_di_seams_integrity.py -q` → **53 passed**
(todos los tests nuevos que alcanzan el guard configuran `get_or_create_prospect` explícito —
mandato §3 de PYTEST-AUTOPSY-WAVE01).

Cambios de Wave 05-02 presentes en el árbol (docstring de vestigio + purga `_get_session`
+ `_track_task`): **intactos** — esta wave es estrictamente aditiva sobre ese estado.

---

## 2. Costuras instauradas (sprout_method_optional_deps)

Regla aplicada: cada pipeline acepta kwargs opcionales **keyword-only con default `None`**;
`None` resuelve el singleton global del módulo **EN TIEMPO DE LLAMADA** (nunca en def-time).
Cero cambios en call-sites existentes (los 25 patch targets y los pins
`assert_called_once_with(phone, text, phone_number_id=…)` quedan intactos).

### 2.1 God Node — `_handle_message_background_impl` (los 5 pipelines: REACTION/IMAGE/RESET/TEXT/AUDIO)

| Dependencia | Firma (nueva) | Resolución runtime (sitio) | Consumos re-enrutados |
|---|---|---|---|
| `catalog_service` | `catalog=None` | `catalog = catalog or catalog_service` (tras `_ensure_services()`) | 14 sitios: proyección visión, match multimodal, rehidratación de precio, CerebroIA ×3, refresh `/update`, `resolve_query_aliases` ×2, `search` ×2, `_items` ×2, `normalize_transcription`, `search_catalog` ×2 |
| `VisionService` (factoría) | `vision_factory=None` | `vision_factory = vision_factory or VisionService` | 2 sitios `vision_factory(db_client)` — **instanciación por llamada preservada** (media L-media y setup de sesión) |
| `db` (Firestore) | `db_client=None` | `db_client = db_client or db` | Guard de la rama media (`if db_client:`) + ambos puntos de instanciación |
| `whatsapp_service` (Meta) | `meta_sender=None` | `meta_sender = meta_sender or whatsapp_service` (junto al **import diferido**, protocolo READ-FIRST) | `mark_as_read`, confirmación `/reset`, confirmación `/update` |

### 2.2 Pipelines internos de egreso/consulta

| Pipeline | Costura | Resolución runtime |
|---|---|---|
| `_send_whatsapp_message` | `meta_sender=None` (keyword-only) | `meta_sender or whatsapp_service` tras el import diferido (cubre también el retry degradado BOT-BUILD-205) |
| `_send_whatsapp_image` | `meta_sender=None` (keyword-only) | `meta_sender or whatsapp_service` tras el import diferido |
| `resolve_query_aliases` | `catalog=None` (posicional-compatible) | `catalog or catalog_service` (paridad posicional heredada: 2º argumento) |

### 2.3 Decisiones de diseño auditables

1. **"5 pipelines del God Node"** = las 5 ramas pineadas en Wave 05-01 (E2E-TEXT/IMAGE/AUDIO/
   REACTION/RESET). Sin extracción de código (constraint): los kwargs viven en la firma del
   God Node y alimentan las 5 ramas vía locales resueltos. Los helpers de egreso/consulta
   reciben su propia costura para la fragmentación RF-5 de waves 05-04/05-05.
2. **No-propagación a call-sites:** el God Node NO pasa sus locales resueltos a
   `_send_whatsapp_message`/`_send_whatsapp_image`/`_process_and_send_egress_message`.
   Motivo forense: 5 pins heredados (`test_identity_legal_gate` ×4, `test_zero_silent_failures`
   ×1) hacen `assert_called_with(phone, text, phone_number_id=…)` exacto sobre los senders —
   añadir un kwarg en el call-site los rompería. Cada pipeline resuelve su propia costura.
3. **Paridad de lectura de `db` (prueba de alcanzabilidad):** la resolución única tras la
   primera `_ensure_services()` es exacta porque (a) `catalog_service`/`VisionService` jamás
   se re-vinculan durante la llamada (solo se mutan vía `.initialize()` en init, fuera del
   embudo), y (b) la 2ª `_ensure_services()` de la rama media es inalcanzable con `db=None`
   (está anidada dentro del guard `if db_client:`); en la ruta texto/audio ningún init
   intermedio antecede al setup de sesión. Cero divergencia respecto a la lectura directa
   del global.
4. **`_ensure_services_sync`, `webhook_handler`, `task_processor`: NO tocados** — init y
   fronteras públicas (constraint de firmas públicas); siguen leyendo los globals directos.

---

## 3. Pins instaurados — `tests/test_di_seams_integrity.py` (8 tests)

| Pin | Aserción del ticket cubierta | Mecánica |
|---|---|---|
| DI-1 firma | "nunca en def-time" + constraint firmas públicas | `inspect.signature`: los 4 kwargs del God Node son `KEYWORD_ONLY` con default `None`; `meta_sender` en ambos senders; `catalog` en `resolve_query_aliases`; `webhook_handler`/`task_processor`/`_handle_message_background` libres de costuras |
| DI-2 catalog | "Mock de catalog_service pasado como kwarg es usado en lugar del global" | Rama TEXT con `catalog=mock` + global parcheado con centinela: `mock.search` invocado, centinela intacto |
| DI-3 vision_factory | "Mock de vision_factory pasado como kwarg es invocado en lugar de VisionService(db)" | Rama IMAGE: factoría inyectada llamada 1 vez con `db_client`; `VisionService` global parcheado jamás llamado |
| DI-4 db_client | "Mock de db_client pasado como kwarg es usado en lugar del global db" | Identidad estricta: el argumento de la factoría ES el `db_client` inyectado y NO el centinela global `db` |
| DI-5 meta_sender | "Mock de meta_sender pasado como kwarg es usado en lugar de whatsapp_service" | Rama RESET: `mark_as_read` + `send_text_message` await­ed en el inyectado; centinela del módulo fuente intacto |
| DI-6 senders | Costura de egreso + fallback | Llamada directa a `_send_whatsapp_message`/`_send_whatsapp_image` con kwarg (prioridad) y sin kwarg (singleton diferido resuelve el patch) |
| DI-7 aliases | Costura de consulta | `resolve_query_aliases` con kwarg, con 2º posicional (paridad) y con fallback al global parcheado |
| DI-8 regresión | "Los 25 patch targets existentes siguen funcionando" | Rama IMAGE **sin kwargs**: los globals parcheados (`VisionService`, `db`, `catalog_service`, `whatsapp_service` fuente) dirigen el flujo — prueba de resolución en tiempo de llamada |

Higiene async: todas las superficies awaited son `AsyncMock`; la factoría se mockea con
`MagicMock` síncrono (se invoca, no se await­ea); cortocircuito de la rama IMAGE vía
`analyze_image` con `side_effect=RuntimeError` → manejador de contingencia existente
(egreso real resuelto contra el servicio parcheado). 0 RuntimeWarnings.

---

## 4. Cumplimiento de constraints del ticket

| Constraint | Estado | Evidencia |
|---|---|---|
| Sin `default=global` en firmas (def-time) | ✅ | DI-1 (pin estático `inspect.signature`) |
| Sin extracción a submódulos | ✅ | `git diff`: solo `app/routers/whatsapp.py` (aditivo) |
| Firmas públicas intactas (`webhook_handler`, `task_processor`, `_handle_message_background`) | ✅ | DI-1 + diff |
| Sin `create_task` en escrituras de estado | ✅ | `test_zero_fire_and_forget.py` 4/4 PASSED |
| Lógica comercial `ai_brain.py` / `juan_pablo_personality` intacta | ✅ | 0 archivos tocados fuera de `app/routers/whatsapp.py` |
| Visual-Lock (PCC Pro) y formato Markdown intactos | ✅ | Solo renombres de receptor (`catalog_service`→`catalog`) alrededor; bloques sin cambio lógico |
| Guardrail idempotencia `register_wamid` intacto | ✅ | Sin cambios en la frontera |
| Locks de sesión `asyncio.Lock` por E.164 intactos | ✅ | `_handle_message_background`/`_get_session_lock` sin cambios |
| Factoría visión: instanciación por llamada preservada | ✅ | `vision_factory(db_client)` en ambos sitios; DI-3 verifica 1 sola invocación por llamada |
| Import diferido de `whatsapp_service` preservado | ✅ | Resolución junto al import; DI-8 verifica parche del módulo fuente |

---

## 5. Comandos de verificación ejecutados

```bash
# Baseline pre-wave (estado Wave 05-02 en árbol)
.venv/bin/python -m pytest tests/ -q                                    # 389 passed, 2 subtests
# Pins nuevos aislados
.venv/bin/python -m pytest tests/test_di_seams_integrity.py -v          # 8 passed
# Regresión quirúrgica de alto riesgo (caracterización/E2E/ORDER/audio/zombie/zero-silent/aliases/FF)
.venv/bin/python -m pytest tests/test_characterization_etapa1.py tests/test_webhook_integrity_e2e.py \
  tests/test_state_persistence_order.py tests/test_audio_regression.py tests/test_zombie_recovery_flow.py \
  tests/test_zero_silent_failures_whatsapp.py tests/test_judge_alias_context.py \
  tests/test_zero_fire_and_forget.py -q                                 # 35 passed
# Inmunización contra el contaminante heredado (mandato Wave 05-01 §3)
.venv/bin/python -m pytest tests/test_pcc_ficha_tecnica.py tests/test_di_seams_integrity.py -q   # 53 passed
# Suite completa, ambos modos
.venv/bin/python -m pytest tests/ -q                                    # 397 passed, 2 subtests
.venv/bin/python -m pytest tests/ -q -W error::RuntimeWarning           # 397 passed (0 RuntimeWarnings)
# Prueba de Fuego
npx agent-cli eval                                                      # 402 passed, 0 failed — Score 1.000 — DEPLOY AUTHORIZED
```

---

## 6. Cierre

- [x] 389+N tests PASSED → **397/397 + 2 subtests** (arnés eval: 402 + 2 skipped)
- [x] 0 RuntimeWarnings (verificado con `-W error::RuntimeWarning`)
- [x] Coherence Score ≥ 0.95 → **1.000**
- [x] Alcance exacto: `app/routers/whatsapp.py` (solo kwargs opcionales) + `tests/test_di_seams_integrity.py`
- [x] Autopsia entregada

**DETENIDO según mandato del ticket. En espera de certificación del Auditor para arrancar
Wave 05-04 (extracción estructural de pipelines sobre estas costuras).**
