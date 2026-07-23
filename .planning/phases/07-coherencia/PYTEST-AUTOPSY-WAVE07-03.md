# PYTEST AUTOPSY — WAVE 07-03 (Evaluación de Nomenclatura Firestore)

**Ticket:** BOT-BUILD-COHERENCE-WAVE07-03-FIRESTORE-NOMENCLATURE-001
**Rol:** OPENCODE BUILDER (Ingeniero Build)
**Fecha:** 2026-07-23
**Resultado:** ✅ SUCCESS — Suite verde, Coherence Score **1.000** (≥ 0.95)

---

## 📜 DOCUMENTO DE DECISIÓN

### ¿Se mantiene o se migra `<NOMENCLATURA_TECNICA_FIRESTORE>`? → **SE MIGRA AL BACKEND (ESCENARIO B). Sección ELIMINADA del prompt.**

### Evidencia forense (step_1 del ticket)

| Componente | Hallazgo |
|---|---|
| `extract_prospect_data` | **NO existe** en el codebase (grep exhaustivo). La única vía de extracción es `generate_summary`. |
| `CerebroIA.generate_summary` (ai_brain.py:2471) | La extracción usa LLM **con structured output**: `response_mime_type="application/json"` + `response_schema=EXTRACTION_SCHEMA`. El LLM NO mapea campos por instrucciones del prompt conversacional: el JSON de salida queda forzado al schema fijo definido EN CÓDIGO. |
| `EXTRACTION_SCHEMA` (ai_brain.py, módulo) | Schema JSON fijo con los campos Firestore del prospecto (nombre, ciudad, moto_interest, habeas_data_accepted, ocupacion, datacredito, forma_pago, vivienda, servicios_publicos, ponytail_*...). Vive en backend desde antes de esta wave. |
| `memory_service._merge_extracted_data` | Mapea `extracted` 1:1 → Firestore con validación 100% code-side (`_is_field_valid`, `_LATCH_TRUE_FIELDS`, `_CRM_PROTECTED_FIELDS`). Cero lectura del prompt. |
| `sys_admin_users` | **No existe en NINGÚN archivo de código** (grep total). Solo estaba en el prompt (colección interna del Dashboard, sin uso comercial). |
| `<datos_ya_capturados>` (ai_brain.py:1496) | En runtime, los nombres de campo reales del CRM se inyectan al prompt dinámicamente — otra razón por la que el bloque estático era redundante. |

### Veredicto contra los criterios del ticket

- **Escenario A (extracción vía LLM con mapeo por prompt): NO aplica.** Aunque el extractor ES un LLM, el mapeo de campos NO depende del prompt conversacional: depende del `response_schema` de código (structured output). El prompt dedicado del extractor ("Extractor PII Juan Pablo") define reglas de sesgo, pero los nombres de campo salen del schema de código.
- **Escenario B (schema fijo en código): APLICA.** *"El schema ya está definido en código, no necesita estar en el prompt."* → nomenclatura migrada/documentada en `ai_brain.py` (comentario canónico sobre `EXTRACTION_SCHEMA`) y sección eliminada de `app/core/prompts.py`.

## 2. Cambios Aplicados

### 2.1 `app/services/ai_brain.py` — documentación del schema (migración)
- Comentario canónico sobre `EXTRACTION_SCHEMA`: lo declara ÚNICA AUTORIDAD de mapeo dato→campo Firestore, documenta los campos obligatorios (constraint), el consumo por `_merge_extracted_data`, y preserva el conocimiento de `sys_admin_users` como referencia técnica de backend (colección interna, fuera del schema del prospecto). **Cero cambios de lógica.**

### 2.2 `app/core/prompts.py` — eliminación de la sección
- `<NOMENCLATURA_TECNICA_FIRESTORE>` extirpada (incluye `sys_admin_users`, autorizado por el criterio del Escenario B que supera el "por ahora" de Wave 07-01).
- Prompt: 5391 → 5004 caracteres (−387, ~7% menos tokens) **sin pérdida de funcionalidad**: C3 (`habeas_data_accepted`) y el script legal del PASO 2 conservan sus referencias de campo funcionales (verificadas por pin).
- `tmp_prompt_to_sync.txt` regenerado vía `generate_prompt_file.py`.

### 2.3 `tests/test_firestore_nomenclature_extraction.py` — NUEVO (17 tests)
- 4 pines de decisión: bloque y `sys_admin_users` fuera del prompt; referencia funcional `habeas_data_accepted` conservada; `sys_admin_users` fuera del schema del prospecto.
- 10 de contrato de schema (parametrizados): 4 campos obligatorios + 5 de perfilamiento presentes; schema OBJECT con `required=[summary, extracted]`.
- 3 de comportamiento de extracción (`generate_summary` con Gemini mockeado): campos extraídos llegan a `result['extracted']` + **pin de autoridad backend** (`config.response_schema == EXTRACTION_SCHEMA`, `response_mime_type == "application/json"`); flag físico `habeas_data_accepted_sent` (link presente/ausente); fallo de Gemini → fallback seguro sin re-raise.

## 3. Constraints del Ticket — Verificación

| Constraint | Estado | Evidencia |
|---|---|---|
| No romper la extracción existente | ✅ | 3 tests de comportamiento sobre `generate_summary` + suite completa verde |
| No alterar lógica de persistencia en `memory_service.py` | ✅ | Archivo intocado (`git status` limpio para ese path) |
| No eliminar campos obligatorios del schema (nombre, ciudad, moto_interest, habeas_data_accepted) | ✅ | `EXTRACTION_SCHEMA` intocado; 4 tests parametrizados pinean su presencia |
| Coherence ≥ 0.95 | ✅ | 1.000 |

**Pines de compatibilidad respetados:** `REGLA DE CREDITO CIEGO`, `PASO 1`, `<PASO_2_SIMULACION_CIEGA>`, `query_faq`/`query_locations`, C1 Visual-Lock — todos re-verificados por script AST tras la edición del prompt (8/8 PASS).

## 4. Logs de Verificación

### 4.1 Suite completa (`.venv/bin/python -m pytest tests/ -q`)
```
.....................................................                    [100%]
483 passed, 2 subtests passed in 75.64s (0:01:15)
```

### 4.2 Gate anti-RuntimeWarning (`-W error::RuntimeWarning`)
```
483 passed, 2 subtests passed in 75.16s (0:01:15)
```

### 4.3 Tests nuevos (aislados)
```
.venv/bin/python -m pytest tests/test_firestore_nomenclature_extraction.py -q
.................                                                        [100%]
17 passed in 0.42s
```

### 4.4 Coherence Eval (`npx agent-cli eval`)
```
━━━ EVAL REPORT ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Tests passed : 488
  Tests failed : 0
  Total        : 488
  Score        : 1.000 (threshold: 0.9)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ SCORE 1.000 ≥ 0.9 — DEPLOY AUTHORIZED ✅
```

## 5. Incidente de Build y Resolución

- **Aserción de identidad vs igualdad:** el pin `config.response_schema is EXTRACTION_SCHEMA` falló porque `GenerateContentConfig` (pydantic) copia/normaliza el dict. Se corrigió a igualdad profunda (`==`), que es la aserción semánticamente correcta para el contrato. Ningún código de producción modificado.

## 6. Fuera de Alcance (respetado)

- `memory_service.py` sin tocar (constraint).
- `EXTRACTION_SCHEMA` sin cambios estructurales (solo comentario de documentación).
- Sincronización del prompt a Firestore producción: pendiente vía `scripts/patch_prompt.py` (decisión de Deployment, como en waves previas).

## 7. Estado Final

- `pytest tests/ -q`: **483 passed, 2 subtests, 0 failed, 0 RuntimeWarnings.**
- `npx agent-cli eval`: **Coherence Score 1.000 ≥ 0.95.**
- Decisión entregada: **MIGRADA al backend (Escenario B)** — sección eliminada del prompt, schema documentado en código, extracción pineada por 17 tests.
- DETENERSE aquí. En espera de certificación del Auditor para **Wave 07-04** (Prueba de Fuego E2E).
