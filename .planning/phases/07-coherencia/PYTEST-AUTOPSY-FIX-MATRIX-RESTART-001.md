# PYTEST AUTOPSY — FIX MATRIX RESTART 001 (Mapeo semántico de ingresos)

**Ticket:** BOT-BUILD-FIX-MATRIX-RESTART-001
**Rol:** OPENCODE BUILDER (Ingeniero Build)
**Fecha:** 2026-07-24
**Resultado:** ✅ SUCCESS — Suite **509 passed + 2 subtests**, RuntimeWarning gate verde, Coherence Score **1.000** (≥ 0.95). **PENDIENTE certificación del Auditor.**

---

## 1. Resumen Ejecutivo

Se ejecutó FIX-1 (alcance aprobado por el Auditor: **solo `ingresos_mensuales`**) sobre `app/services/ai_brain.py`, erradicando la causa raíz del reinicio de matriz post-8/8 detectado por el Auditor en producción (bot re-preguntó 'ingresos mensuales' tras respuesta 'Dos mínimos').

**Diagnóstico forense (BOT-PLAN-VALIDATE-MATRIX-RESTART-001) que corrige la hipótesis original:** el campo `ingresos_mensuales` **EXISTÍA** en el EXTRACTION_SCHEMA desde FIX-4A (commit `3431e27`). La causa raíz era su **descripción**: ordenaba 'solo dígitos' y solo mapeaba 'el mínimo'→SMLV. 'Dos mínimos' no encajaba en ningún patrón y el *bias negativo estricto* la desechaba **en cada turno** → el campo jamás persistía en Firestore → checklist FIX-4B lo marcaba PENDIENTE → re-pregunta. Evidencia decisiva: los otros 4 campos FIX-4A del mismo turno SÍ persistieron (`gastos_mensuales`='500000' desde '500 mil'), descartando deploy-lag y ausencia de campo.

**Archivos tocados:**
| Archivo | Cambio |
| :--- | :--- |
| `app/services/ai_brain.py` | FIX-1: enmienda ADITIVA de la `description` de `EXTRACTION_SCHEMA.extracted.ingresos_mensuales` (único cambio de producción) |
| `tests/test_fix_matrix_restart_001.py` | **Creado** — 3 pins (FIX-1a/1b/1c) |

Cero cambios a: `type` del campo (STRING), `required` del schema (sigue siendo los 4 originales: nombre, ciudad, moto_interest, habeas_data_accepted), los otros 14 campos del EXTRACTION_SCHEMA, `_build_profiling_checklist` (FIX-4B), `_determine_funnel_phase`, CIERRE DE FASE, instrucciones FIX-A/B/C de la v2, `_merge_extracted_data` / `_is_field_valid`.

## 2. Fix ejecutado y evidencia

### FIX-1 (CRÍTICO) — Descripción con mapeo de múltiplos SMLV (L124-133)
- **Enmienda aditiva de texto:** la nueva descripción instruye mapeo obligatorio de salarios mínimos con el SMLV vigente explícito (1.705.905 COP): 'el mínimo'/'un mínimo'/'SMLV' → '1705905'; **'dos mínimos'/'2 mínimos' → '3411810'** (caso real del incidente); 'tres mínimos' → '5117715'; regla general N × 1705905; expresiones de monto ('2 palos' → '2000000', '500 mil' → '500000'). El bias negativo se conserva SOLO para ausencia real: "si el usuario NO mencionó ingresos, dejar vacío; pero si los mencionó en CUALQUIER forma... NUNCA dejar vacío".
- **Pins (3/3 verdes):**
  - `test_fix1a_ingresos_description_has_smlv_multiplier_mapping` — pin estático anti-regresión: la descripción contiene la regla de múltiplos, los 3 valores SMLV precalculados, los mapeos de monto, el bias correctamente acotado, y `type`/`required` intactos.
  - `test_fix1b_checklist_source_fields_exist_in_extraction_schema` — anti-clase-de-bug: las 8 fuentes del checklist FIX-4B (ocupacion, ingresos_mensuales, datacredito, gastos_mensuales, tiene_gas_natural, vivienda, plan_celular, servicios_publicos) ⊆ EXTRACTION_SCHEMA; valores dígito sobreviven `_is_field_valid`.
  - `test_fix1c_mapped_income_survives_merge_and_completes_checklist` — **reproducción del escenario exacto del incidente**: Firestore con 7/8 (estado forense real) + `ingresos_mensuales='3411810'` extraído → `_merge_extracted_data` lo acepta → checklist alcanza `<siguiente_pendiente>COMPLETO</siguiente_pendiente>` sin PENDIENTEs.

## 3. Gates de verificación

| Gate | Resultado |
| :--- | :--- |
| `.venv/bin/python -m pytest tests/ -q` | ✅ **509 passed, 2 subtests passed** (85s) — eran 506 + 3 pins nuevos |
| `.venv/bin/python -m pytest tests/ -q -W error::RuntimeWarning` | ✅ **509 passed, 2 subtests passed** (84s) |
| `npx agent-cli eval` | ✅ **Score 1.000** (514 passed, 2 skipped; umbral 0.95) |
| Pins nuevos del ticket | ✅ **3/3** en `tests/test_fix_matrix_restart_001.py` |
| Regresión pins v1+v2 | ✅ **19/19** (14 de `test_fix_catalog_profile_001.py` + 5 de `test_fix_catalog_profile_001_v2.py`) verdes sin modificación |

## 4. Notas forenses para el Auditor

1. **Por qué el pin de mapeo es estático y no LLM-E2E:** el extractor es Gemini; el compliance del mapeo 'Dos mínimos'→'3411810' es probabilístico y no pineable de forma determinista en suite. El pin estático garantiza que la REGLA está en el schema; la verificación empírica del mapeo queda como gate post-deploy del Auditor (ver §5).
2. **Decisión de alcance respetada:** `gastos_mensuales` NO se endureció (funcionó en el E2E: '500 mil'→'500000'); queda como candidato de hardening si el Auditor observa la misma clase de fallo en ese campo.
3. **Trigger determinista de CIERRE (hipótesis 1 del Auditor):** NO implementado — roza el constraint 'PROHIBIDO alterar la lógica del embudo' y el incidente se explicó al 100% por pérdida del dato. Si post-fix el CIERRE falla CON 8/8 persistido, amerita ticket aparte.
4. **El valor SMLV (1.705.905) quedó explícito en el schema:** coherente con la MATRIZ del prompt Firestore ('Ingresos (SMLV: 1.705.905 COP)'). Si el SMLV cambia, hay que actualizar ambos lugares (schema + prompt) — candidato a nota en el ticket de configuración (ex-FIX-E).

## 5. Post-deploy recomendado (Auditor, 48h)

- E2E: responder **'Dos mínimos'** a la pregunta de ingresos → verificar en Firestore `ingresos_mensuales='3411810'` → matriz alcanza 8/8 → **CIERRE DE FASE sin reinicio**.
- Revisar logs `🔍 [AUDIT PII]` para confirmar que el extractor emite el campo en el JSON de respuesta.

---

**ESTADO:** Build completo. DETENIDO a la espera de certificación del Auditor.
