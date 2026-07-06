---
task: 087
name: Hotfix Bypass Interceptor Collision
description: El orquestador de WhatsApp (app/routers/whatsapp.py) está interpretando incorrectamente el cortocircuito HabeasDataBypassInterrupt como un fallo de generación, agotando los reintentos y disparando el JUDGE_FALLBACK. Esto destruye la respuesta válida de simulación + script legal.
---

# Quick Task 087: Hotfix Bypass Interceptor Collision

## Objective
Evitar que el orquestador de WhatsApp interprete `HabeasDataBypassInterrupt` como un error de generación. Para ello, se propagará la excepción desde `CerebroIA.pensar_respuesta` y se capturará en `app/routers/whatsapp.py`, tratándola como una aprobación inmediata (`is_approved=True`) para enviar la respuesta simulada + script legal sin pasar por el Juez de Fundamentación ni el flujo de supervisor.

## Tasks

<task type="auto">
  <name>Propagar HabeasDataBypassInterrupt en CerebroIA</name>
  <files>
    - app/services/ai_brain.py
  </files>
  <action>
    Modificar el bloque `except HabeasDataBypassInterrupt` en `pensar_respuesta` para que propague la excepción (`raise`) en lugar de capturarla y retornar un string.
  </action>
  <verify>
    No aplica directamente de forma aislada, requiere cambios en el router y tests.
  </verify>
  <done>
    La excepción HabeasDataBypassInterrupt se propaga desde pensar_respuesta.
  </done>
</task>

<task type="auto">
  <name>Capturar HabeasDataBypassInterrupt en el router de WhatsApp</name>
  <files>
    - app/routers/whatsapp.py
  </files>
  <action>
    Modificar el bucle de procesamiento en `app/routers/whatsapp.py` (para mensajes de texto y audio) para capturar específicamente `HabeasDataBypassInterrupt`, asignar la respuesta contenida en la excepción, marcar `is_approved=True` y abortar el reintento de forma exitosa.
  </action>
  <verify>
    Ejecutar pytest para verificar que los tests pasen.
  </verify>
  <done>
    El router intercepta la excepción HabeasDataBypassInterrupt y la procesa con aprobación inmediata.
  </done>
</task>

<task type="auto">
  <name>Adaptar Pruebas Unitarias</name>
  <files>
    - tests/test_pcc_ficha_tecnica.py
  </files>
  <action>
    Actualizar los tests `test_habeas_data_gate_before_credit_score` y `test_habeas_bypass_interrupt_e2e` para que capturen `HabeasDataBypassInterrupt` al llamar a `pensar_respuesta` y realicen las aserciones sobre el contenido de la excepción.
  </action>
  <verify>
    .venv/bin/pytest tests/test_pcc_ficha_tecnica.py
  </verify>
  <done>
    Los tests pasan exitosamente tras capturar y validar la excepción.
  </done>
</task>

---
*Created: 2026-07-02*
