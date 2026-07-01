---
task: 084
name: hotfix-e2e-exception-shortcircuit
description: Crear HabeasDataBypassInterrupt para cortocircuito limpio del while loop en pensar_respuesta
---

# Quick Task 084: hotfix-e2e-exception-shortcircuit

## Objective
Reemplazar el `return response_message` corrupto (L1440) por una excepción de negocio `HabeasDataBypassInterrupt` que se propaga limpiamente a través de los `except Exception` intermedios hasta el `while` loop maestro de `pensar_respuesta`, garantizando un cortocircuito síncrono hacia el webhook de Meta.

## Tasks

<task type="auto">
  <name>Crear excepción HabeasDataBypassInterrupt</name>
  <files>app/core/exceptions.py</files>
  <action>Crear archivo con clase HabeasDataBypassInterrupt(Exception)</action>
  <verify>python3 -c "from app.core.exceptions import HabeasDataBypassInterrupt; print('OK')"</verify>
  <done>Import exitoso sin errores</done>
</task>

<task type="auto">
  <name>Inyectar raise + re-raises en ai_brain.py</name>
  <files>app/services/ai_brain.py</files>
  <action>1. Import HabeasDataBypassInterrupt. 2. Reemplazar return response_message por raise. 3. Añadir 2 re-raises antes de catches genéricos. 4. Envolver while loop en try/except.</action>
  <verify>python3 -c "from app.services.ai_brain import CerebroIA; print('OK')"</verify>
  <done>Import exitoso y sintaxis válida</done>
</task>

<task type="auto">
  <name>Test E2E del cortocircuito</name>
  <files>tests/test_pcc_ficha_tecnica.py</files>
  <action>Añadir test_habeas_bypass_interrupt_e2e que llame pensar_respuesta y verifique $ en respuesta</action>
  <verify>python -m pytest tests/test_pcc_ficha_tecnica.py -v --tb=short</verify>
  <done>Todos los tests pasan incluyendo el nuevo E2E</done>
</task>

---
*Created: 2026-07-01*
