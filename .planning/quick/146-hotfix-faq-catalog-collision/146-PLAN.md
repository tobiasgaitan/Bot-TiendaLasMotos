---
task: 146
name: Hotfix FAQ-Catalog Collision in Auto-Repair Loop
description: El bucle de auto-reparación post-generación (BOT-QA-LOOP-107) entra en pánico porque is_catalog_query se evalúa como True por la keyword global 'moto', ignorando que run_checker determinó un bypass_strict exitoso por intención de FAQ pura sin moto_interest en CRM.
---

# Quick Task 146: Hotfix FAQ-Catalog Collision

## Objective
Forzar `is_catalog_query = False` sincrónicamente en `ai_brain.py` cuando `run_checker` retorna bypass semántico exitoso (`success=True` con `bypass_strict`), impidiendo que el retry loop del supervisor de formato penalice FAQs abstractas con reglas de validación de catálogo.

## Causa Raíz
**Archivo:** `app/services/ai_brain.py` líneas 659-683.

El guardia (L661) activa el bloque de validación si `mentions_moto OR is_moto_query`. Si el usuario pregunta "¿tienen motos de segunda?" (keyword "moto"), `is_moto_query=True` y se invoca `run_checker`. El checker retorna `success=True` (bypass FAQ). Sin embargo, en el siguiente ciclo del `while`, `is_catalog_query` sigue siendo el valor calculado en L659, y si la respuesta del LLM menciona alguna keyword de ficha, puede romper la validación en el retry. El problema estructural es que no existe un log forense explícito del bypass exitoso y la variable no se resetea tras confirmarse el bypass.

## Tasks

<task type="auto">
  <name>Force is_catalog_query=False on bypass and add forensic log</name>
  <files>app/services/ai_brain.py</files>
  <action>
    En el bloque POST-GENERATION VALIDATION HOOK (líneas 654-693):
    1. Añadir log forense INFO cuando run_checker retorna success=True con bypass semántico.
    2. Extraer el flag `bypass_strict` del resultado de run_checker para re-evaluar is_catalog_query.
    3. Modificar la firma de retorno de run_checker para incluir `bypass_strict` en el dict de retorno.
    4. En ai_brain.py: si validation["success"] y validation.get("bypass_strict"), forzar is_catalog_query=False y hacer return inmediato (ya existe en L691 pero añadir log).
    El cambio real es en agentic_loop_service.run_checker: exponer `bypass_strict` en el dict de retorno exitoso.
    Luego en ai_brain.py: after validation, if bypass was applied, log it explicitly.
  </action>
  <verify>cd /Users/tobiasgaitangallego/Bot-TiendaLasMotos && python3 -m pytest tests/ -x -q 2>&1 | tail -5</verify>
  <done>225/225 tests PASSED con el nuevo comportamiento de bypass explícito</done>
</task>

---
*Created: 2026-07-09*
