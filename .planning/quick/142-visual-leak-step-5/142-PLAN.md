---
task: 142
name: Resolve Visual Leak in Paso 5 Transition
description: "El bot duplica la imagen y el precio de la motocicleta durante la transición al Paso 5 (Captura de Identidad) tras procesar la reacción emoji. El modelo sufre sangrado de contexto al interpretar la traducción 'Sí' generada por el router, ejecutando la regla de visuales obligatorios fuera de la Fase 1."
---

# Quick Task 142: Resolve Visual Leak in Paso 5 Transition

## Objective
Prevent the LLM from duplicating the motorcycle image and price during the transition to Phase 2 (Paso 5 - Captura de Identidad) by injecting a semantic interruption directive in the prompt, and expand `test_whatsapp_reaction_payload_direct_legal_acceptance` with negative assertions to verify.

## Tasks

<task type="auto">
  <name>Inyectar directiva de interrupción semántica en ai_brain.py</name>
  <files>[app/services/ai_brain.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/services/ai_brain.py)</files>
  <action>Modificar la lógica en `elif phase == "PHASE_2_HABEAS_DATA":` para añadir la directiva solicitada: 'El consentimiento ya ha sido firmado en este turno. Tienes ESTRICTAMENTE PROHIBIDO incluir enlaces de imágenes (![]) o precios ($) en tu respuesta. Limítate exclusivamente a solicitar el nombre completo y la ciudad de forma concisa.'</action>
  <verify>python3 -c "from app.services.ai_brain import CerebroIA; print('CerebroIA importable')"</verify>
  <done>La directiva de interrupción semántica está correctamente inyectada para el bloque de PHASE_2_HABEAS_DATA.</done>
</task>

<task type="auto">
  <name>Expandir test_whatsapp_reaction_payload_direct_legal_acceptance en test_identity_legal_gate.py</name>
  <files>[tests/test_identity_legal_gate.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_identity_legal_gate.py)</files>
  <action>Expandir el test `test_whatsapp_reaction_payload_direct_legal_acceptance` para validar que la respuesta no contiene `![` ni `$`, agregando las aserciones negativas solicitadas.</action>
  <verify>pytest tests/test_identity_legal_gate.py</verify>
  <done>Las aserciones negativas `assert '![' not in response` y `assert '$' not in response` están integradas y el test pasa localmente.</done>
</task>

<task type="auto">
  <name>Ejecutar evaluación con agent-cli</name>
  <files>[]</files>
  <action>Ejecutar `npx @tobiasgaitan/agent-cli eval` para validar la coherencia general del sistema.</action>
  <verify>npx @tobiasgaitan/agent-cli eval</verify>
  <done>La evaluación de agent-cli se ejecuta con éxito y el score de coherencia es 1.000.</done>
</task>

---
*Created: 2026-07-09*
