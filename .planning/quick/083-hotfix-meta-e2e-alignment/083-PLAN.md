---
task: 083
name: hotfix-meta-e2e-alignment
description: El bypass de contingencia de PermissionError en ai_brain.py sufre de fugas de contexto en caliente con Meta debido al uso de 'continue' en bucles iterativos de herramientas del SDK GenAI 2026, y el parser de precios del catálogo provoca fallos de conversión de flotantes.
---

# Quick Task 083: hotfix-meta-e2e-alignment

## Objective
Resolver la fuga de contexto asíncrono interrumpiendo el bucle de inferencia de Gemini en PermissionError y consolidar la limpieza de precios robusta en un método privado para evitar ValueErrors.

## Tasks

<task type="auto">
  <name>Modificar ai_brain.py y test_pcc_ficha_tecnica.py</name>
  <files>
    <file>app/services/ai_brain.py</file>
    <file>tests/test_pcc_ficha_tecnica.py</file>
  </files>
  <action>Extraer el método de parseo privado _parse_raw_price, implementarlo en los 3 puntos de parseo de precios, reemplazar el continue por return response_message en el PermissionError, y actualizar el test con precio sucio "$9.969.000.*" y aserciones directas de response string.</action>
  <verify>./.venv/bin/pytest tests/test_pcc_ficha_tecnica.py</verify>
  <done>Las pruebas unitarias y el análisis de agent-cli eval pasan exitosamente con score 1.000.</done>
</task>

---
*Created: 2026-06-30*
