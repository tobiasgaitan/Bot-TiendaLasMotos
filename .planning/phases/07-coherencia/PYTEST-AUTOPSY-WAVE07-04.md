# PYTEST AUTOPSY — WAVE 07-04 (Prueba de Fuego E2E Integral)

**Ticket:** BOT-BUILD-COHERENCE-WAVE07-04-E2E-FIRE-TEST-001
**Rol:** OPENCODE BUILDER (Ingeniero Build)
**Fecha:** 2026-07-23
**Resultado:** ✅ SUCCESS — 4/4 escenarios de fuego, Suite verde, Coherence Score **1.000** (≥ 0.95)

---

## 1. Resumen Ejecutivo

Se certificó E2E (router REAL + `CerebroIA` REAL con Gemini scriptado + Juez REAL con C4 desactivado) que las migraciones de las Waves 07-01 (prompt XML + herramientas de conocimiento), 07-02 (fallback de Crédito Ciego) y 07-03 (nomenclatura Firestore en backend) operan correctamente en el flujo completo: **reset → audio → crédito ciego → cuota → habeas data → FAQ → ubicaciones**.

**Único archivo creado:** `tests/test_e2e_coherence_fire.py` (4 tests). Cero modificaciones a `prompts.py`, `ai_brain.py`, `faq_service.py` (constraints verificados vía `git status`).

## 2. Arnés E2E

- **Router real:** `_handle_message_background_impl` (mismo patrón que `test_audio_post_reset_credit_intent_no_fallback`).
- **Cerebro real:** `CerebroIA` con chat de Gemini scriptado por turno (function-call → text), de modo que el dispatch de herramientas, la inyección de Crédito Ciego, `faq_service`, el Phase-Gate y los guardrails visuales ejecutan **código de producción**.
- **Juez real** con `_client=None` (auditoría semántica desactivada — patrón C9-GRACE).
- Frontera mockeada: memory, storage, audio (transcripción), whatsapp sender, catálogo del router, egreso consolidado.

## 3. Escenarios y Evidencia

### Scenario 1 — `test_scenario_1_blind_credit_audio_injects_brilla_defaults` (Waves 07-01+02)
Audio "Hola, quiero saber el precio de la Boxer y cómo financiarla" con moto en CRM y sin datos personales; el LLM invoca `calculate_credit_score` con payload **VACÍO**.
- ✅ `calculate_payment` recibió `entidad="Brilla de Gases"` e `inicial=912900.0` (10%).
- ✅ Spy sobre `_apply_blind_credit_defaults`: llamado exactamente 1 vez con `args == {}` (la inyección de Wave 07-02 interceptó el payload omitido).
- ✅ Egreso: `aproximadamente de $450,000` (regex `\$\d{1,3}(,\d{3})+` ✓) + `politica-de-privacidad` (Habeas inmediato).
- ✅ Cero "Disculpa, no estoy seguro", `set_human_help_status(True)` jamás invocado, transcripción de audio ejecutada.

### Scenario 2 — `test_scenario_2_faq_query_uses_query_faq_not_catalog` (Wave 07-01)
Texto "¿Necesito codeudor para el crédito?".
- ✅ Spy sobre `get_faq_answer`: 1 llamada; `search_items` del cerebro: **0 llamadas** (query_faq, NO search_catalog).
- ✅ Respuesta con la matriz migrada (`Reportados: Requieren Cédula + 10% de inicial OBLIGATORIA.`).
- ✅ Sin `![` ni precios (regex) en el egreso.
- ✅ Embudo retomado: el function-response hacia Gemini incluye la directiva "Habeas Data" y el **Phase-Gate** (ai_brain.py:922) cerró hacia la firma (`política de privacidad`).

### Scenario 3 — `test_scenario_3_location_query_returns_five_branches` (Wave 07-01)
Texto "¿Dónde están ubicadas sus tiendas?".
- ✅ Spy sobre `get_location_info`: 1 llamada; `search_items`: 0 llamadas.
- ✅ Las 5 sedes presentes con 5 links de Maps; sin `![`.
- ✅ Embudo retomado: la pregunta pendiente `¿Desde qué ciudad nos escribes?` viajó en el function-response; el egreso cierra con pregunta.

### Scenario 4 — `test_scenario_4_full_funnel_reset_to_profiling` (07-01+02+03)
6 turnos reales secuenciales por el router:
1. `/reset` → `delete_prospect_completely` awaited + ack determinista "reiniciada por completo".
2. Audio "Me interesa la VICTORY MRX 125" → **PASO 1**: saludo "Juan Pablo" + `![Victory MRX 125](...)` + `$9.129.000` (Visual-Lock intacto).
3. "¿Cuánto sería la cuota?" → **PASO 2/3/4**: `entidad="Brilla de Gases"` en el motor + cuota con formato + script Habeas + frase inmutable `emoji de pulgar arriba (👍)`.
4. "Sí" → **PASO 5a**: solicitud de "nombre completo" y "ciudad".
5. "Carlos Pérez, Bogotá" → **MATRIZ**: primera pregunta de perfilamiento ("¿a qué te dedicas?").
6. "Empleado" → **MATRIZ**: segunda pregunta ("¿qué tipo de contrato?").
- ✅ Transversal: 6 cerebros consumidos (cola vacía), cero fallback humano en los 5 turnos cognitivos, `generate_and_update_summary` awaited ≥1 (pipeline de extracción de Wave 07-03 activo).

## 4. Incidentes de Build y Resolución (forense)

1. **`motor_financiero` pisado por el router:** `whatsapp.py:879` inyecta el motor de módulo dentro del cerebro (`cerebro_ia.motor_financiero = motor_financiero`), ignorando el motor inyectado al cerebro en el arnés → el egreso mostraba "Estimación de cuota base no disponible temporalmente." Detección: sonda forense fuera de pytest imprimiendo el egreso real. Resolución de arnés: parchear `motor_financiero` a nivel router con el motor mock (cero cambios de app).
2. **Turno `/reset` consume fábrica de cerebros:** el router instancia `CerebroIA` ANTES de interceptar el comando (línea 878) → `IndexError` en la cola. Resolución: cerebro dummy encolado para el turno 1 (jamás recibe inferencia).
3. **Aserción de cierre de FAQ demasiado estricta:** el Phase-Gate sancionado (`is_profiling` sin Habeas) reescribe el cierre y anexa el script de transición con la URL de privacidad → el egreso no termina en "?". Resolución: la aserción de "embudo retomado" ahora verifica la manifestación real del sistema (directiva Habeas en payload + `política de privacidad` en egreso), no la forma literal del texto scriptado.

## 5. Logs de Verificación

### 5.1 Escenarios de fuego (aislados)
```
.venv/bin/python -m pytest tests/test_e2e_coherence_fire.py -q
....                                                                     [100%]
4 passed in 0.62s
```

### 5.2 Suite completa (`.venv/bin/python -m pytest tests/ -q`)
```
.........................................................                [100%]
487 passed, 2 subtests passed in 75.33s (0:01:15)
```

### 5.3 Gate anti-RuntimeWarning (`-W error::RuntimeWarning`)
```
487 passed, 2 subtests passed in 77.13s (0:01:17)
```

### 5.4 Coherence Eval (`npx agent-cli eval`)
```
━━━ EVAL REPORT ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Tests passed : 492
  Tests failed : 0
  Total        : 492
  Score        : 1.000 (threshold: 0.9)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ SCORE 1.000 ≥ 0.9 — DEPLOY AUTHORIZED ✅
```

## 6. Constraints del Ticket — Verificación

| Constraint | Estado | Evidencia |
|---|---|---|
| No modificar `app/core/prompts.py` | ✅ | Wave 07-04 solo creó el archivo de tests |
| No modificar `app/services/ai_brain.py` | ✅ | Spies con `wraps=` (sin alterar comportamiento) |
| No modificar `app/services/faq_service.py` | ✅ | Intacto |
| Coherence ≥ 0.95 | ✅ | 1.000 |

## 7. Estado Final — Etapa 4 lista para certificación

- Suite: **487 passed + 2 subtests, 0 failed, 0 RuntimeWarnings** (baseline Etapa 3: 435 → +52 tests en las 4 waves de coherencia).
- `npx agent-cli eval`: **Coherence Score 1.000**.
- Las 4 migraciones quedan certificadas E2E: prompt XML estricto + herramientas de conocimiento (07-01), fallback determinista de Crédito Ciego (07-02), nomenclatura Firestore en backend (07-03), y el embudo completo reset→audio→crédito→habeas→perfilamiento (07-04).
- **Pendiente para producción (fuera del rol Builder):** sincronizar el prompt refactorizado a Firestore vía `scripts/patch_prompt.py`.
- DETENERSE aquí. En espera de certificación del Auditor para **cierre de Etapa 4 y despliegue a beta (F5)**.
