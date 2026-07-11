---
task: 155
name: bot-vision-parser
description: Regresión en el enrutamiento de imágenes de catálogo debido a la eliminación del token rígido '[MOTO_DETECTADA]' en la salida del prompt del motor de IA
---

# Quick Task 155: bot-vision-parser

## Objective
Desacoplar el enrutamiento de imágenes de catálogo del token rígido '[MOTO_DETECTADA]' en app/routers/whatsapp.py. Modificar la estructura condicional para procesar por defecto como consulta de catálogo de motocicletas (sanitizando el texto) si no contiene tags financieros ('CEDULA', 'RECIBO'). Agregar logs estructurados con la respuesta nativa de la IA en caso de error catastrófico.

## Tasks

<task type="auto">
  <name>Modificar enrutamiento en whatsapp.py</name>
  <files>[app/routers/whatsapp.py]</files>
  <action>Desacoplar la validación de '[MOTO_DETECTADA]' y cambiarla a una verificación condicional basada en la ausencia de tags de documentos financieros ('CEDULA', 'RECIBO'). Añadir sanitización y logging estructurado en caso de excepción.</action>
  <verify>.venv/bin/pytest tests/test_identity_legal_gate.py</verify>
  <done>El código de whatsapp.py está modificado y los tests pasan.</done>
</task>

<task type="auto">
  <name>Modificar y añadir pruebas unitarias</name>
  <files>[tests/test_identity_legal_gate.py]</files>
  <action>Modificar la prueba para simular respuestas de visión con y sin la etiqueta heredada '[MOTO_DETECTADA]'.</action>
  <verify>.venv/bin/pytest tests/test_identity_legal_gate.py</verify>
  <done>Nuevas aserciones creadas y pasando con éxito.</done>
</task>

<task type="auto">
  <name>Verificar suite completa</name>
  <files>[]</files>
  <action>Ejecutar evaluación completa mediante agent-cli eval.</action>
  <verify>npx @tobiasgaitan/agent-cli eval</verify>
  <done>La evaluación finaliza con un score mayor o igual a 0.9.</done>
</task>

---
*Created: 2026-07-11*
