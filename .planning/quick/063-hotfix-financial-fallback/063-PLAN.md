---
task: 063
name: hotfix-financial-fallback
description: "BOT-FINANCE-ERR-094: Eliminar enmascaramiento nulo en calculate_payment. Forzar logger.exception + raise explícito. Bypass defensivo con .get() para partners_config en beta."
---

# Quick Task 063: hotfix-financial-fallback

## Objective
Cumplir el guardrail Zero-Silent-Failures en `calculate_payment`: reemplazar el doble bloque `except` genérico+bare por logging forense con `logger.exception` y fallback amortización básica con retorno coherente. Adicionalmente, blindar `get_partners_config()` en `evaluate_profile` con `.get()` defensivo que use `"#"` como valor de fallback seguro ante un dict vacío en beta.

## Tasks

<task type="auto">
  <name>Parche Zero-Silent-Failures en calculate_payment + bypass partners defensivo</name>
  <files>app/services/financial_service.py</files>
  <action>
    1. En el bloque except primario (L134): reemplazar `except Exception as e:` por la misma firma pero añadir `logger.exception(f"[BOT-FINANCE-ERR-094] Fallo en calculate_payment para entidad={entidad}, plazo={plazo_meses}: {e}")` ANTES del fallback de amortización básica.
    2. Eliminar el `except:` bare en L153. Reemplazarlo por `except Exception as inner_e:` + `logger.exception(f"[BOT-FINANCE-ERR-094] Fallo en fallback de calculate_payment: {inner_e}")` + retorno del dict de error con ambos mensajes.
    3. En `evaluate_profile` (L217): blindar la llamada a `partners.get(strategy_info.get("link_key"), "#")` ya existente. La llave `partners` se obtiene de `get_partners_config()` que puede retornar `{}` en beta → ya usa .get() seguro. Confirmar que no hay crash si `partners = {}`.
    4. Verificar que `get_partners_config()` en `link_brilla` property (L30-31) también usa `.get()` con fallback `"#"` → ya está correcto. No modificar.
  </action>
  <verify>python3 -m pytest tests/test_financial_fallback.py -v 2>&1 | tail -30</verify>
  <done>Pytest pasa. logger.exception emite traza. Retorno siempre contiene cuota_mensual numérica.</done>
</task>

<task type="auto">
  <name>Crear test unitario test_financial_fallback.py</name>
  <files>tests/test_financial_fallback.py</files>
  <action>
    Crear test que valide:
    1. `calculate_payment` con `get_partners_config()` retornando `{}` (mock) no retorna `None` ni lanza excepción silenciosa.
    2. El resultado SIEMPRE contiene `"cuota_mensual"` con valor float > 0.
    3. Si el config_service falla completamente, el fallback de amortización básica produce un dict con `cuota_mensual` coherente (> 0).
    4. Que NO existe un retorno de tipo `None` silencioso en ninguna rama.
  </action>
  <verify>python3 -m pytest tests/test_financial_fallback.py -v 2>&1 | tail -30</verify>
  <done>Todos los tests pasan. No hay retorno None silencioso.</done>
</task>

---
*Created: 2026-06-24T21:09:00-05:00*
