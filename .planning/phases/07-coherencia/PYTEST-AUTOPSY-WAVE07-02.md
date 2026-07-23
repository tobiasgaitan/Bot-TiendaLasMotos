# PYTEST AUTOPSY — WAVE 07-02 (Migración de Lógica de Crédito Ciego)

**Ticket:** BOT-BUILD-COHERENCE-WAVE07-02-BLIND-CREDIT-001
**Rol:** OPENCODE BUILDER (Ingeniero Build)
**Fecha:** 2026-07-23
**Resultado:** ✅ SUCCESS — Suite verde, Coherence Score **1.000** (≥ 0.95)

---

## 1. Resumen Ejecutivo

Se implementó el fallback determinista de **Crédito Ciego** en la capa de infraestructura para la herramienta `calculate_credit_score`. Si el LLM omite parámetros (o los envía nulos/vacíos), el backend inyecta los 7 defaults del ticket **antes de la ejecución final** de la herramienta, eliminando la dependencia de que el prompt fuerce esta instrucción.

## 2. Cambios Aplicados

### 2.1 `app/services/ai_brain.py` — Única modificación (scope quirúrgico)

**a) Bloque de módulo nuevo (antes de `class CerebroIA`):**
- `BLIND_CREDIT_DEFAULTS` — dict canónico con los 7 valores del ticket:
  `entidad="Brilla de Gases"`, `ocupacion_y_contrato="Empleado"`, `ingresos_demostrables="SMLV"`, `historial_datacredito="Sin experiencia"`, `plan_celular="Sí"`, `reportes="No"`, `inicial="10%"`.
- `_BLIND_CREDIT_ALIASES` — variantes de llave que el LLM puede usar (`ocupacion`, `datacredito`) consultadas antes de inyectar.
- `_is_filled(value)` — None y cadenas vacías/espacios cuentan como ausente.
- `_apply_blind_credit_defaults(f_args, prospect_data)` — inyección con **prioridad de resolución preservada: f_args (+aliases) > prospect_data (CRM) > default**. Devuelve copia (no muta el payload original). **Zero-Silent-Failures:** `logger.exception` obligatorio en el `except` y retorno fail-open de los args originales.

**b) Punto de interceptación (dentro del handler `elif f_name == "calculate_credit_score"`):**
```python
f_args = _apply_blind_credit_defaults(f_args, prospect_data)
```
ubicado DESPUÉS de las compuertas de rechazo (PHASE_1_PROFILING y FAQ_ONLY) y ANTES del `try:` de ejecución → cubre ambas rutas de evaluación (ScoringService directo y legacy `evaluate_profile`).

### 2.2 Decisiones de diseño (arqueología defensiva)

1. **`inicial: "10%"` se inyecta como metadato canónico en f_args, NO se cablea a los cálculos.** La rama ciega (sin Habeas) ya hardcodea `m_price * 0.10` y las ramas con consentimiento usan `inicial=0` — pineado por `test_brilla_conmutacion.py:130` (`calculate_payment.assert_called_once_with(inicial=0, ...)`) y `test_pcc_ficha_tecnica.py` (`inicial=996900.0` = 10% de 9.129.000). Cablear el default habría roto esos pins y la paridad financiera. El valor inyectado hace explícito el default del ticket sin alterar una sola cuota.
2. **El CRM no se pisa:** sin la verificación de `prospect_data`, un prospecto con `ocupacion="Independiente"` extraído al CRM habría sido degradado a `"Empleado"` cuando el LLM omite el arg. La inyección solo actúa cuando NI f_args NI CRM tienen el dato.
3. **Rama ciega intacta:** el flujo sin Habeas (simulación + `HabeasDataBypassInterrupt`) no lee f_args; la inyección es inocua ahí. Cero cambios fuera del handler (constraint).

### 2.3 `tests/test_blind_credit_fallback.py` — NUEVO (13 tests)

- 1 contrato: `BLIND_CREDIT_DEFAULTS` == spec del ticket (verbatim).
- 8 unitarios: payload vacío/None → 7 defaults; nulos/blancos (parametrizado ×3) → default; valores LLM preservados; aliases (`ocupacion`, `datacredito`) bloquean inyección; CRM bloquea inyección; input no mutado; fallo de conversión → fail-open + `logger.exception` (caplog).
- 2 integración (dispatcher real vía `pensar_respuesta` con chat scriptado): payload VACÍO → `evaluate_profile` recibe los 6 kwargs de scoring con defaults; payload parcial (`ocupacion_y_contrato="Independiente"`) → preservado + resto completado.

## 3. Constraints del Ticket — Verificación

| Constraint | Estado | Evidencia |
|---|---|---|
| No modificar `app/core/prompts.py` | ✅ | `git status`: prompts.py sin tocar en esta wave |
| No alterar lógica fuera del handler `calculate_credit_score` | ✅ | Único call-site añadido: 1 línea dentro del handler; helper nuevo a nivel módulo (aditivo, cero callers previos) |
| No romper tests existentes | ✅ | 466 passed + 2 subtests (baseline Wave 07-01: 453; +13 nuevos) |
| Zero-Silent-Failures (`logger.exception` en bloque de inyección) | ✅ | `except` del helper con `logger.exception` + test dedicado con caplog |

**Pines de compatibilidad respetados (descubiertos en reconocimiento previo):**
- `test_cerebro_ia_scoring_service_direct_alignment` (ScoringService REAL, score 980): los args inyectados (`entidad`, `reportes`, `inicial`) no alimentan `calculate_score` → score inalterado. Verde.
- Pins de `calculate_payment` (inicial=0 en rama con consentimiento; 10% hardcodeado en rama ciega): intactos por diseño (ver 2.2.1).
- `test_proactive_credit.py` / `test_pcc_ficha_tecnica.py`: aserciones de rechazo PHASE_1 y FAQ_ONLY ejecutan ANTES de la inyección → comportamiento idéntico. Verdes.

## 4. Logs de Verificación

### 4.1 Suite completa (`.venv/bin/python -m pytest tests/ -q`)
```
....................................                                     [100%]
466 passed, 2 subtests passed in 77.11s (0:01:17)
```

### 4.2 Gate anti-RuntimeWarning (`-W error::RuntimeWarning`)
```
466 passed, 2 subtests passed in 76.80s (0:01:16)
```

### 4.3 Tests nuevos (aislados)
```
.venv/bin/python -m pytest tests/test_blind_credit_fallback.py -q
.............                                                            [100%]
13 passed in 0.58s
```

### 4.4 Coherence Eval (`npx agent-cli eval`)
```
━━━ EVAL REPORT ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Tests passed : 471
  Tests failed : 0
  Total        : 471
  Score        : 1.000 (threshold: 0.9)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ SCORE 1.000 ≥ 0.9 — DEPLOY AUTHORIZED ✅
```

## 5. Incidentes de Build y Resolución

1. **`insert_before_symbol` duplicó la línea `class CerebroIA:`** → `IndentationError` detectado vía `py_compile` antes de correr tests. Resolución: borrado de la línea huérfana (1 edit).
2. **Falso negativo inicial en tests de integración:** el prospect de prueba sin `moto_interest` era clasificado `PHASE_1_PROFILING` → el handler rechazaba la herramienta (comportamiento correcto del sistema, mal arnés del test). Resolución: prospect con `moto_interest="TVS Raider 125"` + catálogo y `calculate_payment` mockeados. Ningún código de producción fue tocado para "hacer pasar" el test.

## 6. Fuera de Alcance (respetado)

- El prompt XML (`app/core/prompts.py`) conserva la `REGLA DE CREDITO CIEGO (Paso 2)` dentro de `<PASO_2_SIMULACION_CIEGA>` — su eventual adelgazamiento es decisión del Auditor (el ticket prohíbe tocarlo en esta wave).
- La rama duplicada de simulación ciega post-`try` (asimetría documentada en waves previas) NO fue normalizada.

## 7. Estado Final

- `pytest tests/ -q`: **466 passed, 2 subtests, 0 failed, 0 RuntimeWarnings.**
- `npx agent-cli eval`: **Coherence Score 1.000 ≥ 0.95.**
- DETENERSE aquí. En espera de certificación del Auditor para **Wave 07-03** (Evaluación de `<NOMENCLATURA_TECNICA_FIRESTORE>`).
