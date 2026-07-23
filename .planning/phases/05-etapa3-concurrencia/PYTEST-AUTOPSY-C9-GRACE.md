# PYTEST AUTOPSY — C9 Grace: Corrección de Flujo Post-Reset en Audio

**Ticket:** BOT-BUILD-ETAPA3-POST-RESET-C9-GRACE-001
**Ticket padre (Plan):** BOT-PLAN-ETAPA3-POST-RESET-AUDIO-FIX-001
**Fecha:** 2026-07-23
**Ejecutor:** OPENCODE BUILDER
**Resultado:** ✅ **CERTIFICADO — 435/435 + 2 subtests PASSED, 0 failed, 0 RuntimeWarnings — ventana de gracia C9 operativa**

---

## 1. Veredicto cuantitativo

| Métrica | Baseline pre-build (Wave 05-06) | Post-build | Delta |
|---|---|---|---|
| Suite directa (`pytest tests/ -q`) | 431 passed + 2 subtests | **435 passed + 2 subtests** | **+4 pins C9-GRACE, 0 regresiones** |
| Modo estricto (`-W error::RuntimeWarning`) | 431 passed | **435 passed** | **0 RuntimeWarnings** |
| Archivos modificados | — | **3 (1 src + 2 tests)** | Alcance exacto del ticket |
| `app/routers/whatsapp.py` | — | **0 líneas tocadas** | Mandato inquebrantable ✓ |
| `app/services/ai_brain.py` | — | **0 líneas tocadas** | Mandato inquebrantable ✓ |
| String de rechazo C9 | presente | **presente, verbatim** | Solo condicionado, jamás eliminado ✓ |

### Reporte de pytest (suite completa, venv `.venv/bin/python`)

```
$ .venv/bin/python -m pytest tests/ -q
435 passed, 2 subtests passed in 79.20s (0:01:19)

$ .venv/bin/python -m pytest tests/ -q -W error::RuntimeWarning
435 passed, 2 subtests passed in 78.27s (0:01:18)
```

### Suites de regresión del test_spec (una por una)

| Suite | Resultado |
|---|---|
| `tests/test_judge_service.py` + `tests/test_audio_regression.py` | **23 passed** |
| `tests/test_pipeline_audio_integrity.py` + `tests/test_pipeline_text_cognitive_integrity.py` (pins AI-1..5 / text) | **11 passed** |
| `tests/test_pcc_ficha_tecnica.py` (FAQ bypass C1/C9) | **45 passed** |
| `tests/test_latency_forensics.py` (LAT-1..3, rama JUDGE_CRITICAL_ERROR) | **8 passed** |

> **Nota de entorno:** el intérprete del sistema (`python3` Homebrew 3.14) carece del
> módulo `ffmpeg` y hace fallar la colección de `test_audio_regression.py` por causa
> ajena al cambio. Toda la evidencia se generó con el intérprete del proyecto
> (`.venv/bin/python`), idéntico al usado en las autopsias de las waves 05-01…05-06.

---

## 2. Cadena causal corregida (root cause certificado)

1. `/reset` → `delete_prospect_completely` (wipe nuclear). La confirmación se envía
   directo por Meta **sin persistirse** en historial.
2. Audio post-reset → `_pipeline_audio`: `create_prospect_if_missing` → save de la
   transcripción → `generate_and_update_summary` BLOQUEANTE → re-fetch con `ciudad`
   ausente (log forense: `Memory Synced. Identity: None`).
3. `skip_greeting` **ya era False** post-reset (`_evaluate_skip_greeting` con
   `current_message_saved=True` descarta el único mensaje legítimo) — la Opción A del
   ticket de Plan era un no-op; por eso se ejecutó la **Opción B**.
4. La respuesta de la IA contiene keywords de crédito → `_detect_credit_advance`
   (heurística de substrings, incluye `"requisitos"`) disparaba.
5. **Antes del fix:** C9 rechazaba ×3 intentos → fallback →
   `set_human_help_status(True)`: usuario fresco post-reset volcado a handoff humano
   en su primer contacto.
   **Después del fix:** C9 se condona en el primer turno legítimo; el criterio
   recupera plena vigencia desde el 2.º mensaje legítimo.

---

## 3. Implementación (2 cambios quirúrgicos en `app/services/judge_service.py`)

### Cambio 1 — Helper `_count_legitimate_user_messages(history)` (tras `_detect_credit_advance`)

Cuenta mensajes `role == "user"` excluyendo comandos/control con semántica
**IDÉNTICA** a `_evaluate_skip_greeting` del router (alineación **BOT-206**):
`reset`, `/reset`, `/update`, `/refresh_catalog`, prefijo `/`, `[System Note:` y
`sesión ha sido reiniciada`. Defensivo: `isinstance(msg, dict)` descarta entradas
no-dict del historial externo.

### Cambio 2 — Condicionamiento del bloque C9 en `analyze_response`

```python
if is_moving_to_credit and not has_city:
    # [BOT-BUILD-ETAPA3-POST-RESET-C9-GRACE-001] Ventana de gracia de 1 turno...
    if self._count_legitimate_user_messages(history) >= 2:
        return False, "C9_CITY_MISSING: El bot intenta avanzar a crédito sin haber preguntado la ciudad."
    logger.info("✅ [JUDGE] C9_CITY_MISSING condonado: primer turno legítimo ...")
```

**Calibración aprobada por el usuario:** umbral `>= 2`. Ambos pipelines pasan un
`history` que **incluye el turno actual** (texto: save en L857 antes de cargar
historial; audio: save de la transcripción antes del re-fetch), por lo que la gracia
es de **exactamente 1 turno**. El string de rechazo se conserva **verbatim**; solo se
condiciona su ejecución.

**Superficie de impacto:** `analyze_response` solo es invocado desde
`_pipeline_audio` (L1656) y `_pipeline_text_cognitive` (L1947). La firma pública del
Juez no cambió (`history` ya existía como parámetro). C1/C2/C3/C5-C8 permanecen
plenamente activos durante el turno de gracia — sin agujero de seguridad.

---

## 4. Matriz de certificación de tests

### Test existente actualizado (1)

| Test | Cambio | Resultado |
|---|---|---|
| `test_judge_service.py::test_judge_city_discovery_fail` | Añadido `history` con 2 mensajes legítimos (`hola`, `financiar`) para que C9 conserve sus dientes | ✅ PASS |

Sin esta actualización el test fallaría (historial vacío = conteo 0 = condonación) —
modificación sancionada por el ticket (§test_spec.update_existing).

### Tests nuevos (4)

| Test | Contrato pineado | Resultado |
|---|---|---|
| `test_judge_c9_condoned_first_legitimate_turn` | 1 mensaje legítimo + respuesta crédito + sin ciudad → `(True, "")` | ✅ PASS |
| `test_judge_c9_ignores_control_messages` | `[/reset (user), confirmación (model), [System Note: (user), 1 legítimo]` → conteo=1 → condonado | ✅ PASS |
| `test_judge_c9_reactivates_second_turn` | 2 mensajes legítimos + respuesta crédito + sin ciudad → `(False, "C9_CITY_MISSING...")` | ✅ PASS |
| `test_audio_regression.py::test_audio_post_reset_credit_intent_no_fallback` | **E2E con Juez REAL** (`_client=None`): audio post-reset con intención de crédito → `pensar_respuesta` ×1 (cero reintentos), `set_human_help_status(True)` jamás invocado, egreso con la respuesta aprobada (no el fallback) | ✅ PASS |

### Inocuidad verificada sobre tests preexistentes con Juez real

- `test_adversarial_security.py` (`ciudad="Bogotá"` poblada) — `has_city=True`, C9 no aplica. ✅
- `test_judge_alias_context.py` (sin keywords de crédito) — `is_moving_to_credit=False`. ✅
- Parity C2 / Brilla C7 / Scoring C6 en `test_judge_service.py` (todas con `ciudad` poblada). ✅

---

## 5. Cumplimiento de mandatos inquebrantables

| Mandato | Evidencia |
|---|---|
| PROHIBIDO tocar `app/routers/whatsapp.py` | `git diff --stat`: 0 líneas |
| PROHIBIDO tocar `app/services/ai_brain.py` | `git diff --stat`: 0 líneas |
| PROHIBIDO tocar `juan_pablo_personality.docx` | Fuera del diff |
| String C9 verbatim, solo condicionado | Diff §3 Cambio 2: `return False, "C9_CITY_MISSING: El bot intenta avanzar a crédito sin haber preguntado la ciudad."` intacto |
| Visual-Lock (PCC Pro) intacto | C1 sin cambios; `test_pcc_ficha_tecnica.py` 45 passed |
| Pins de integridad de pipelines (AI-1..5, text) | 11 passed — cero cambios estructurales |

```
$ git diff --stat
 app/services/judge_service.py  |  38 +++++++++++-
 tests/test_audio_regression.py | 130 ++++++++++++++++++++++++++++++++++
 tests/test_judge_service.py    |  79 ++++++++++++++++++++-
 3 files changed, 245 insertions(+), 2 deletions(-)
```

---

## 6. Observación fuera de alcance (documentada, NO construida)

**Asimetría audio/texto:** `_pipeline_audio` no propaga `is_faq_bypass` al Juez, a
diferencia de `_pipeline_text_cognitive` (`run_checker → bypass_strict`,
BOT-BRAIN-FAQ-ROOT-CAUSE-HUNT-147). Si emergen falsos positivos FAQ en el canal de
audio, corresponde un ticket de paridad separado. La ventana de gracia C9 de este
ticket no depende de ese mecanismo.

---

**CERTIFICACIÓN FINAL:** La corrección post-reset queda pineada a nivel unitario
(3 pins) y E2E con Juez real (1 pin). C9_CITY_MISSING conserva sus dientes desde el
segundo turno legítimo. Suite completa verde en modo normal y estricto.
