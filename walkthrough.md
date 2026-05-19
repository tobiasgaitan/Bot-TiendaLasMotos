# Walkthrough — Quick Task 035: Purga de Llaves Legacy y Firma de calculate_credit_score

Se ha completado la tarea de purgar de forma física y estricta los fallbacks a llaves obsoletas/legacy (`name`, `city`, `payment_method`) en `ai_brain.py` para cumplir con el esquema canónico unificado. También se alineó la firma de la herramienta `calculate_credit_score` inyectando los parámetros `entidad` y `reportes` requeridos por la lógica del motor financiero.

## Cambios Realizados

1. **Purga de Llaves Legacy (`ai_brain.py`)**:
   - Eliminados todos los fallbacks obsoletos de `prospect_data.get("name")`, `prospect_data.get("city")` y `prospect_data.get("payment_method")` en la lógica de transiciones de fases de funnel y prompt reinforcement, usando únicamente `nombre`, `ciudad` y `forma_pago`.

2. **Alineación de `calculate_credit_score` (`ai_brain.py`)**:
   - Actualizada la declaración de la herramienta `credit_function` para registrar y describir los parámetros `entidad` y `reportes`.
   - Modificado el bloque de despacho de `calculate_credit_score` para mapear y propagar `entidad` y `reportes` al método de evaluación de perfiles.

3. **Alineación del Motor Financiero (`app/services/financial_service.py`)**:
   - Modificado `evaluate_profile` para aceptar explícitamente `entidad` y `reportes` como parámetros y retornarlos en la respuesta consolidada de perfilamiento.

4. **Actualización de Tests de No Regresión**:
   - Corregidos y actualizados los tests en `tests/test_competitor_protocol.py`, `tests/test_habeas_data_regression.py`, y `tests/test_proactive_credit.py` para utilizar estrictamente las llaves canónicas (`nombre`, `ciudad`, `forma_pago`) en lugar de las legacy.
   - Verificado el correcto funcionamiento del test de integridad `tests/test_pcc_ficha_tecnica.py` que previene el enmascaramiento nulo de `Ficha Tecnica:`.

## Resultados de Verificación

Se obtuvo un score perfecto de **1.000** en la auditoría de coherencia automática:

```text
━━━ GSD EVAL — Coherence Score Gate ━━━
ℹ Project root: /Users/tobiasgaitangallego/Bot-TiendaLasMotos

Running pytest...
95 passed, 2 skipped in 3.49s

━━━ EVAL REPORT ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Tests passed : 95
  Tests failed : 0
  Total        : 95
  Score        : 1.000 (threshold: 0.9)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ SCORE 1.000 ≥ 0.9 — DEPLOY AUTHORIZED ✅
```

## Estado Final

- **Rama**: `beta`
- **Último Commit**: `9c76019` - `docs(sync): update Documento Maestro, STATE, and ROADMAP for v10.1.0`
- **Integridad y Despliegue**: 100% verificado y subido a origen de forma exitosa.
