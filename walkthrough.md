# Walkthrough — Quick Task 067: correccion_contratos_pruebas_firestore

Se ha completado la tarea de corregir las discrepancias nomenclaturales y variables en la suite de pruebas unitarias alineándolas a la estructura oficial del `EXTRACTION_SCHEMA` de Firestore (`ocupacion`, `datacredito`), así como la corrección del valor canónico de `forma_pago` y la validación estricta de alertas del guardrail PCC Pro.

## Cambios Realizados

1. **Alineación de `forma_pago` (`tests/test_agentic_loop_async.py`)**:
   - Se reemplazó el valor de prueba `"forma_pago": "credito"` por el valor canónico real en base de datos `"forma_pago": "Crédito - 0 inicial"`.

2. **Extracción y Validación de Parámetros (`app/services/financial_service.py`)**:
   - Se actualizó el método `evaluate_profile` para capturar y priorizar los parámetros `'ocupacion'` y `'datacredito'` de forma de mantener alineación con el `EXTRACTION_SCHEMA`. Se conservaron los fallobacks anteriores para asegurar compatibilidad.

3. **Corrección de Parámetros en Suite de Pruebas (`tests/test_agentic_loop_async.py`)**:
   - Se alinearon todas las llamadas a `evaluate_profile` para utilizar los parámetros `'ocupacion'` y `'datacredito'`.

4. **Alertas del Guardrail PCC Pro (`tests/test_pcc_ficha_tecnica.py`)**:
   - Se inyectó verificación explícita para asegurar que la mutación de una llave requerida (como `summary` o `price`) active la alerta de fallo de validación del guardrail `PCC Pro` (retornando `success=False` y `broken_guardrail='PRICE_CONSISTENCY_CHECK'`) en lugar de pasar de largo con un retorno vacío.

## Evidencia de Verificación

- **Suite de Pruebas**: Todos los 156 tests unitarios pasan exitosamente local y en el pipeline.
- **Score de Coherencia**: Obtenido un score perfecto de **1.000** verificado vía `npx agent-cli eval`.
- **Commit GitHub**: Sincronizado en la rama `beta` remota con el hash de commit final `b7a510b`.

---
*Completado: 2026-06-25*
