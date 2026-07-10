---
task: 150
name: Audio SDK Credentials and Regression Fix
description: Modify client initialization in app/services/audio_service.py to inject explicit ADC credentials, and update tests/test_audio_regression.py to catch ClientError and raise on unexpected exceptions.
---

# Quick Task 150: Audio SDK Credentials and Regression Fix

## Objective
Fix the google-genai Client initialization in production/Cloud Run by passing explicit ADC credentials and project parameters, without forcing Vertex AI unless required. Then, update the live integration test to propagate ClientError/ValueError so it correctly fails locally instead of passing in green, adding strict propagation to the unexpected exception handler.

## Tasks

<task type="auto">
  <name>Inyectar credenciales ADC en AudioService</name>
  <files>app/services/audio_service.py</files>
  <action>Modificar la inicialización de genai.Client para inyectar credenciales de Google Cloud default (ADC) explícitas y no forzar Vertex AI si hay una GEMINI_API_KEY local.</action>
  <verify>python3 -c "from app.services.audio_service import AudioService; print(AudioService)"</verify>
  <done>AudioService se puede importar sin errores de sintaxis y la lógica de inicialización está actualizada.</done>
</task>

<task type="auto">
  <name>Alinear test_audio_service_live_integration</name>
  <files>tests/test_audio_regression.py</files>
  <action>Actualizar el test en tests/test_audio_regression.py para capturar ClientError del SDK de Google GenAI y ValueError, y forzar fallos/abortos locales propagándolas o lanzándolas, además de lanzar excepciones no controladas en el bloque genérico Exception.</action>
  <verify>.venv/bin/pytest tests/test_audio_regression.py</verify>
  <done>La prueba de regresión test_audio_service_live_integration falla de forma controlada cuando no se tiene acceso autenticado o no hay API key, lanzando ClientError o ValueError.</done>
</task>

---
*Created: 2026-07-10*
