---
task: 102
name: bot-resilience-102
description: Fallo en cascada provocado por sobre-ingeniería en interceptores de seguridad. Se requiere flexibilizar el Drift Interceptor y el Null Masking, además de actualizar la suite de pruebas para evitar falsos negativos y garantizar la cobertura de la nueva resiliencia de datos.
---

# Quick Task 102: bot-resilience-102

## Objective
Flexibilizar el Drift Interceptor a 0.30, hacer 'summary'/'descripcion' opcional (por defecto 'Sin descripción'), dar soporte a 'image_url'/'imagen_url' como fallback, y actualizar/crear la suite de pruebas unitarias.

## Tasks

<task type="auto">
  <name>Modificar ai_brain.py (Drift Interceptor, Null Masking, fallback de imagen)</name>
  <files>[/Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/services/ai_brain.py]</files>
  <action>
  1. Modificar Drift Interceptor: cambiar 0.35 <= ratio < 0.95 a 0.30 <= ratio < 0.95 en app/services/ai_brain.py.
  2. En Null Masking: hacer 'summary'/'descripcion' opcional. Si falta, usar 'Sin descripción' como valor por defecto. Las llaves críticas únicas requeridas son 'name' y 'price'.
  3. Soporte para 'image_url' / 'imagen_url' fallback.
  </action>
  <verify>uv run pytest tests/test_robots.py</verify>
  <done>ai_brain.py modificado y validado sintácticamente.</done>
</task>

<task type="auto">
  <name>Actualizar y crear tests unitarios en tests/test_pcc_ficha_tecnica.py u otros archivos de pruebas</name>
  <files>[/Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_pcc_ficha_tecnica.py]</files>
  <action>
  1. Modificar tests existentes que asertaban el rechazo por falta de summary.
  2. Crear test unitario afirmando que un documento sin summary pasa el filtro.
  3. Crear test unitario afirmando que la llave 'imagen_url' es procesada correctamente.
  4. Crear test afirmando que un ratio de 0.35 no dispara el bloqueo del Drift Interceptor.
  </action>
  <verify>npx agent-cli eval</verify>
  <done>Suite de pruebas actualizada y pasando con score de 1.000.</done>
</task>
