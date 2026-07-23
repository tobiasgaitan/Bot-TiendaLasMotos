# PYTEST AUTOPSY — Wave 05-01: Red de Caracterización (Etapa 3)

**Ticket:** BOT-BUILD-ETAPA3-WAVE01-CHARACTERIZATION-001
**Fecha:** 2026-07-22
**Ejecutor:** OPENCODE BUILDER
**Resultado:** ✅ **CERTIFICADO — 385/385 + 2 subtests PASSED, 0 failed, 0 RuntimeWarnings, Coherence Score 1.000**

---

## 1. Veredicto cuantitativo

| Métrica | Baseline pre-wave | Post-wave | Delta |
|---|---|---|---|
| Suite directa (`pytest tests/ -q`) | 373 passed + 2 subtests | **385 passed + 2 subtests** | **+12 pins nuevos, 0 regresiones** |
| Modo estricto (`-W error::RuntimeWarning`) | — | **385 passed** | **0 RuntimeWarnings** |
| Arnés eval (`npx agent-cli eval`) | — | **390 passed + 2 skipped** | **Score 1.000 ≥ 0.95** ✅ |
| Cambios en `app/` | — | **0 archivos** | Cumple constraint CERO cambios en app/ |

Archivos creados (alcance exacto del ticket, ninguno modificado):
- `tests/test_webhook_integrity_e2e.py` (6 pins E2E)
- `tests/test_state_persistence_order.py` (6 pins ORDER)

Cambio incidental fuera de alcance: `.serena/project.yml` (regeneración de metadatos del toolchain Serena al activar el proyecto; no es código de aplicación).

---

## 2. Pins instaurados (Algoritmo de Feathers — comportamiento ACTUAL pineado)

### tests/test_webhook_integrity_e2e.py

| Pin | Rama | Comportamiento capturado |
|---|---|---|
| E2E-TEXT | Texto | Embudo completo: READ-FIRST → save(user) → LINEAR BLOCKING → Juez (1 auditoría) → egreso imagen con PCC Pro (precio canónico referenciado a fábrica, ficha, URL canónica). **Pin vigente: doble `save_message("model")` (pre-egreso L1558 + eco intra-egreso L1906)** — CH-5 no lo observa porque mockea el egreso completo. Normalizable SOLO en 05-05 con aprobación del Auditor. |
| E2E-IMAGE | Imagen | download → VisionService → match canónico → `update_prospect_summary(moto_interest + ponytail PENDING)` [BOT-PONYTAIL-200] → Visual Lock inyecta imagen/precio omitidos por el LLM → egreso con URL canónica. **Pin vigente: el Juez NO audita la rama imagen.** |
| E2E-AUDIO | Audio | download → transcribe → alineación fonética → save(user=**transcripción**, blinding fix) → summary con `last_bot_question` del historial → Juez (1 auditoría) → egreso texto PCC Pro. |
| E2E-REACTION | Reacción 👍 | debounce → intercept persiste `{"habeas_data_accepted": True, "ponytail_status": "PENDING"}` bloqueante → cuerpo mutado a `"Sí"` alimenta `pensar_respuesta` (quick-138). |
| E2E-RESET | `/reset` | wipe nuclear → clear buffer → confirmación "reiniciada"; **jamás invoca pensar_respuesta**; `_active_resets` liberado (blindaje finally L1270-1273). |
| E2E-STATUSES | Acuses Meta | Frontera responde 200 y delega a BackgroundTasks (1 tarea, `_handle_statuses_background`); el handler persiste con **await bloqueante** vía `update_whatsapp_status` (E.164 normalizado, errors propagados) [ARCH-BULK-META-010]. |

### tests/test_state_persistence_order.py (Sincronía de Oficio: estado Firestore precede red Meta)

| Pin | Invariante ordenado (índices de línea de tiempo) |
|---|---|
| ORDER-TEXT | create → update_last → transition → summary → save(user) → save(model pre-egreso) ≺ 1er envío Meta. Eco save(model) intra-egreso posterior pineado (vigente). |
| ORDER-IMAGE | create_prospect_if_missing → update_prospect_summary → summary ≺ pensar_respuesta ≺ egreso imagen. |
| ORDER-AUDIO | save(user=transcripción) ≺ generate_and_update_summary ≺ 1er envío. |
| ORDER-REACTION | update_prospect_summary(habeas+PENDING) ≺ pensar_respuesta ≺ egreso. |
| ORDER-RESET | delete_prospect_completely ≺ confirmación enviada. |
| ORDER-FALLBACK | [MANDATO v9.8.3] Juez agota 3 intentos → set_human_help_status(True) → ponytail DEPRIORITIZED → save(model fallback) ≺ envío fallback. Correlación CH-4 preservada. |

**Excepción sancionada pineada:** `mark_as_read` (protocolo READ-FIRST, L761-765) se registra fuera del conjunto de "envíos" — es acuse de lectura, no mensaje del embudo.

---

## 3. ⚠️ HALLAZGO FORENSE CRÍTICO (afecta a waves 05-02 en adelante)

### Contaminante: `tests/test_pcc_ficha_tecnica.py::test_brilla_gases_real_firestore_cuotas`

**Mecanismo raíz (verificado por bisección de suite + sondas):**

1. El test heredado ejecuta `patch.stopall()` y un barrido de `sys.modules` que **expulsa todo módulo cuyo repr contenga "mock" — incluido `unittest.mock`** (L1195-1199), además de instanciar clientes Firestore reales.
2. La siguiente ejecución de `from unittest.mock import Mock` (guard BOT-174, `whatsapp.py` L1389) **recarga clases NUEVAS** de `Mock`/`MagicMock`.
3. Todo mock creado ANTES de la expulsión pertenece a la clase ORIGINAL; `isinstance(m.return_value, Mock)` dentro del guard evalúa contra la clase RECARGADA → **`False`** → el guard toma la rama `await ms.get_or_create_prospect(...)` sobre un MagicMock síncrono → `TypeError: object MagicMock can't be used in 'await' expression` (L1396).
4. **Por qué solo fallaron los tests nuevos:** orden alfabético de colección — `test_characterization_etapa1` y otros tests del guard corren ANTES de `test_pcc_*`; los archivos nuevos (`test_state_persistence_order`, `test_webhook_integrity_e2e`) corren DESPUÉS.

**Patrón de inmunización adoptado (sancionado por el propio guard BOT-174):** configurar `ms.get_or_create_prospect = AsyncMock(return_value=<prospect_dict>)` explícitamente. El comentario del guard lo prescribe ("Si get_or_create_prospect ha sido mockeado con un valor explícito (no un Mock por defecto)") y es inmune a la polución de identidad de clases. Documentado en los docstrings de `_build_ms_mock` de ambos archivos nuevos.

**Mandato para waves 05-02…05-06:** todo test nuevo que alcance el guard BOT-174 DEBE configurar `get_or_create_prospect` explícito. La saneamiento del test contaminante (import-time real Firestore + cirugía de sys.modules) queda FUERA del alcance de Etapa 3 (constraint: cero modificación de archivos existentes) — se reporta como deuda candidata a Etapa 4.

---

## 4. Comandos de verificación ejecutados

```bash
# Baseline pre-wave
.venv/bin/python -m pytest tests/ -q                                    # 373 passed, 2 subtests
# Pins nuevos aislados
.venv/bin/python -m pytest tests/test_webhook_integrity_e2e.py tests/test_state_persistence_order.py -v   # 12 passed
# Inmunización verificada contra el contaminante
.venv/bin/python -m pytest tests/test_pcc_ficha_tecnica.py tests/test_webhook_integrity_e2e.py tests/test_state_persistence_order.py -q   # 57 passed
# Suite completa, ambos modos
.venv/bin/python -m pytest tests/ -q                                    # 385 passed, 2 subtests
.venv/bin/python -m pytest tests/ -q -W error::RuntimeWarning           # 385 passed, 2 subtests (0 warnings)
# Prueba de Fuego
npx agent-cli eval                                                      # 390 passed, 0 failed — Score 1.000 — DEPLOY AUTHORIZED
```

---

## 5. Cierre

- [x] 378+N tests PASSED → **385/385 + 2 subtests** (arnés eval: 390 + 2 skipped)
- [x] 0 RuntimeWarnings (verificado con `-W error::RuntimeWarning`)
- [x] Coherence Score ≥ 0.95 → **1.000**
- [x] CERO cambios en `app/` (constraint respetado; `git status` limpio salvo los 2 archivos nuevos de tests y metadatos Serena)
- [x] Autopsia entregada

**DETENIDO según mandato del ticket. En espera de certificación del Auditor para arrancar Wave 05-02 (Certificación cero fire-and-forget + higiene).**
