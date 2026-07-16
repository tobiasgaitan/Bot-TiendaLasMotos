---
task: 185
name: Router Greeting Alignment Hotfix
description: Modificar de forma quirúrgica el motor de prompts en app/services/ai_brain.py para unificar el comportamiento de saludos de forma determinista. Si skip_greeting es True, el sistema debe suprimir o reescribir de forma dinámica en tiempo de ejecución cualquier instrucción conflictiva del PASO 1 (Enganche de Valor) o cualquier sección que ordene dar bienvenidas y presentarse. Se debe garantizar que si skip_greeting es True, se inyecte una instrucción inquebrantable de iniciar la respuesta directamente con la presentación de la motocicleta, sin saludos ni presentaciones personales.
---

# Quick Task 185: Router Greeting Alignment Hotfix

## Objective
Garantizar de forma determinista que cuando `skip_greeting` sea `True`, la respuesta generada por el LLM no contenga ningún saludo, bienvenida ni presentación personal, reescribiendo quirúrgicamente en tiempo de ejecución la instrucción del sistema en `app/services/ai_brain.py` para evitar colisiones con el protocolo comercial (PASO 1).

## Tasks

<task type="auto">
  <name>Modificar ai_brain.py para Runtime Prompt Assembly de saludos</name>
  <files>[app/services/ai_brain.py]</files>
  <action>Modificar `app/services/ai_brain.py` para que, si `skip_greeting` es True, reescriba de manera dinámica la `base_instruction` eliminando o sustituyendo las instrucciones de saludo/presentación del PASO 1 y forzando que se comience directamente con la presentación de la moto.</action>
  <verify>.venv/bin/pytest tests/test_agentic_loop_async.py</verify>
  <done>El código implementa la reescritura de prompt dinámica, y todos los tests unitarios e integración pasan con éxito.</done>
</task>

<task type="auto">
  <name>Añadir test de regresión para saludos consecutivos de catálogo</name>
  <files>[tests/test_agentic_loop_async.py]</files>
  <action>Añadir un caso de prueba en `tests/test_agentic_loop_async.py` que realice búsquedas de catálogo consecutivas con un estado conversacional simulado y asegure con aserciones rígidas que la segunda respuesta no contenga saludos (Hola, Juan Pablo, etc.).</action>
  <verify>.venv/bin/pytest tests/test_agentic_loop_async.py</verify>
  <done>El test de regresión secuencial está añadido y pasa limpiamente.</done>
</task>

---
*Created: 2026-07-16*
