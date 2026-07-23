# PYTEST AUTOPSY — WAVE 07-01 (Refactorización Semántica y Migración de Base de Conocimiento)

**Ticket:** BOT-BUILD-COHERENCE-WAVE07-01-PROMPT-TOOLS-001
**Rol:** OPENCODE BUILDER (Ingeniero Build)
**Fecha:** 2026-07-23
**Resultado:** ✅ SUCCESS — Suite verde, Coherence Score **1.000** (≥ 0.95)

---

## 1. Resumen Ejecutivo

Se ejecutó la refactorización semántica del documento de personalidad (`JUAN_PABLO_SYSTEM_INSTRUCTION` en `app/core/prompts.py` — fuente de verdad del repo sincronizada a Firestore `configuracion/juan_pablo_personality`) y la migración del bloque `<KNOWLEDGE_BASE>` al backend como herramientas function-calling deterministas (`query_faq`, `query_locations`).

**Nota de arqueología:** el archivo físico `juan_pablo_personality.docx` NO existe en el repositorio. La personalidad vive en Firestore y su fuente de verdad visible en el repo es `app/core/prompts.py` (ver cabecera del módulo). La intervención se aplicó sobre esa constante; `tmp_prompt_to_sync.txt` fue regenerado vía `generate_prompt_file.py` para mantener la sincronía del artefacto de despliegue.

## 2. Cambios Aplicados

### 2.1 `app/core/prompts.py` — Refactor XML estricto
- Estructura de bloques: `<SISTEMA_BASE>`, `<REGLAS_DE_ORO_Y_MATRIZ_DE_CALIDAD>` (C1–C9 verbatim), `<PROTOCOLO_DE_COMPETENCIA>`, `<REGLAS_ANTI_ALUCINACION>`, `<CONSULTA_DE_CONOCIMIENTO>`, `<PROTOCOLO_COMERCIAL>`, `<MATRIZ_PERFILAMIENTO>`, `<NOMENCLATURA_TECNICA_FIRESTORE>`.
- **Fix entidad financiera:** cero referencias a `crediorbe` en el prompt (verificado por pin automatizado); PASO 2 unificado a "Brilla de Gases" (script legal Habeas Data verbatim, sin tocar una coma).
- **Fix numeración:** `REGLA DE CREDITO CIEGO (Paso 2)` — etiqueta errónea `(Paso 4)` eliminada. Consistente con `memory_service.py:178` ("PASO 2 de Simulación Ciega").
- **Consolidación:** PASO 2 (Habeas Data) + REGLA DE CREDITO CIEGO fusionados en `<PASO_2_SIMULACION_CIEGA>` dentro de `<PROTOCOLO_COMERCIAL>`.
- **Eliminación KNOWLEDGE_BASE:** `<knowledge_base>`/`<locations>`/`<credit_matrix_rules>` extirpados del prompt. Reemplazados por `<CONSULTA_DE_CONOCIMIENTO>` que ordena al LLM invocar `query_faq` (requisitos/documentos) y `query_locations` (sedes/direcciones), con refuerzo `BLOQUEO DE CONOCIMIENTO` en `<REGLAS_ANTI_ALUCINACION>`.
- **NOMENCLATURA_TECNICA_FIRESTORE:** consolida `moto_interest` + `habeas_data_accepted` (antes punto 3 de SISTEMA_BASE) y mantiene `sys_admin_users` sin modificación (constraint del ticket).

### 2.2 `app/services/faq_service.py` — NUEVO (SSOT de conocimiento)
- `FAQ_RULES`: 4 reglas verbatim de `<credit_matrix_rules>` (Empleados/Reportados/Extranjeros/Brilla) con keywords por tema.
- `LOCATIONS`: 5 sedes verbatim de `<locations>` con keywords por ciudad/barrio.
- `get_faq_answer(query)`: matching por keywords con normalización de acentos (NFKD); sin match → matriz completa (anti-alucinación: consultas abstractas como "codeudor" reciben las 4 reglas, no una regla inventada).
- `get_location_info(query)`: matching por ciudad/barrio; "Santa Marta" → sus 3 sedes; sin match → las 5 sedes.

### 2.3 `app/services/ai_brain.py` — Registro de herramientas
- Import: `from app.services.faq_service import get_faq_answer, get_location_info`.
- `_create_tools`: 2 `FunctionDeclaration` nuevas (`query_faq`, `query_locations`) con `query` requerido y descripciones REGLA DE ORO anti-memoria. Toolset base pasa de `[handoff, catalog]` a `[handoff, catalog, faq, locations]` (siempre presentes, con o sin `calculate_credit_score`).
- Dispatcher `_generate_with_retry_async`: rama `elif f_name in ("query_faq", "query_locations")` que ejecuta la función del servicio, anexa `funnel_instruction` (paridad con search_catalog/credit) y devuelve `Part.from_function_response`. Fallo del servicio → `logger.exception` + degradado controlado (Zero-Silent-Failures), sin re-raise.

### 2.4 `tests/test_pcc_ficha_tecnica.py` — Ajuste de pin por cambio de interfaz
- `test_create_tools_omits_credit_when_faq_abstract`: conteos actualizados 3→5 (con credit) y 2→4 (sin credit) con justificación en docstring. Única aserción existente tocada; la lógica del test (presencia/ausencia de credit) intacta.

### 2.5 `tests/test_faq_and_location_tools.py` — NUEVO (18 tests)
- 7 unitarios `get_faq_answer` (4 temas + matriz completa genérica/vacía + insensibilidad acento/caso).
- 6 unitarios `get_location_info` (Santa Marta→3 sedes, Gaira, Riohacha, Zona Bananera, genérica/vacía→5).
- 2 registro: tools presentes con y sin `omit_credit`.
- 3 integración dispatcher (chat scriptado): payload determinista viaja al LLM en el function response; fallo del servicio degrada con log forense.

### 2.6 `tmp_prompt_to_sync.txt` — Regenerado vía `generate_prompt_file.py`.

## 3. Constraints del Ticket — Verificación

| Constraint | Estado | Evidencia |
|---|---|---|
| No alterar embudo (Pasos 1–5) | ✅ | PASO 1/3/4/5 verbatim; PASO 2 script verbatim (solo re-encerrado en `<PASO_2_SIMULACION_CIEGA>`) |
| No eliminar Visual-Lock (PCC Pro) ni Markdown de imágenes | ✅ | C1 Visual-Lock + `![Nombre_Moto](URL_devuelta_por_search_catalog)` presentes (pin automatizado) |
| No modificar `sys_admin_users` | ✅ | Se mantiene en `<NOMENCLATURA_TECNICA_FIRESTORE>` con nota de no uso comercial |
| No romper tests existentes | ✅ | 453 passed + 2 subtests (baseline 435 + 18 nuevos = 453); 0 regresiones |

**Pines de compatibilidad descubiertos y respetados:**
- `tests/test_semantic_plumbing.py` exige el literal `REGLA DE CREDITO CIEGO` en el prompt ensamblado (PHASE_1 y PHASE_2) → conservado dentro del bloque consolidado.
- `_assemble_skip_greeting_prompt` reescribe líneas con `paso 1` → línea `- PASO 1 (Enganche): ...` conservada; `test_assemble_skip_greeting_prompt_rewrites_paso1` verde.

## 4. Logs de Verificación

### 4.1 Suite completa (`.venv/bin/python -m pytest tests/ -q`)
```
........................................................................ [ 79%]
........................................................................ [ 94%]
.......................                                                  [100%]
453 passed, 2 subtests passed in 76.75s (0:01:16)
```

### 4.2 Gate anti-RuntimeWarning (`-W error::RuntimeWarning`)
```
453 passed, 2 subtests passed in 77.67s (0:01:17)
```

### 4.3 Tests nuevos (aislados)
```
.venv/bin/python -m pytest tests/test_faq_and_location_tools.py -q
..................                                                       [100%]
18 passed in 0.69s
```

### 4.4 Coherence Eval (`npx agent-cli eval`)
```
━━━ EVAL REPORT ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Tests passed : 458
  Tests failed : 0
  Total        : 458
  Score        : 1.000 (threshold: 0.9)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ SCORE 1.000 ≥ 0.9 — DEPLOY AUTHORIZED ✅
```
(El arnés eval cuenta 458 por su propia selección con 2 skipped; gate ≥ 0.95 superado con 1.000.)

## 5. Incidente de Build y Resolución

Durante la refactorización del prompt, `replace_symbol_body` dejó el cuerpo viejo concatenado tras el nuevo (`""".strip() = """...`), produciendo `SyntaxError: cannot assign to function call` detectado de inmediato al regenerar `tmp_prompt_to_sync.txt`. Resolución quirúrgica: borrado del segmento huérfano vía regex (`serena_replace_content`), validación AST + 18 pines semánticos del prompt (bloques XML, fixes, prohibiciones) ejecutados como script de verificación — todos PASS antes de correr la suite.

## 6. Fuera de Alcance (respetado)

- Firestore en producción NO fue tocado: la sincronización del prompt es vía `scripts/patch_prompt.py` desde Cloud Shell (decisión del Auditor/Deployment).
- La lógica de Crédito Ciego en backend (`calculate_credit_score`, scoring) NO fue tocada — corresponde a **Wave 07-02**.
- `config_service.py`/`scoring_service.py` conservan sus llaves `crediorbe` (mapeo de links financieros Firestore); el ticket solo ordenaba unificar la entidad **en el PASO 2 del prompt**.

## 7. Estado Final

- `pytest tests/ -q`: **453 passed, 2 subtests, 0 failed, 0 RuntimeWarnings.**
- `npx agent-cli eval`: **Coherence Score 1.000 ≥ 0.95.**
- DETENERSE aquí. En espera de certificación del Auditor para **Wave 07-02** (Migración de lógica de Crédito Ciego al backend).
