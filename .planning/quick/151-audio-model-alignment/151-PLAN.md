---
task: 151
name: audio-model-alignment
description: Corrección del model_id en AudioService para usar gemini-2.5-flash y actualización de test de regresión
---

# Quick Task 151: audio-model-alignment

## Objective
Corregir app/services/audio_service.py para que self._model_id se inicialice dinámicamente como 'gemini-2.5-flash' tanto en la rama con API Key como en la de Vertex AI, y actualizar tests/test_audio_regression.py con aserciones rígidas que verifiquen el model_id unificado.

## Tasks

<task type="auto">
  <name>Modificar AudioService para inicializar _model_id como gemini-2.5-flash</name>
  <files>app/services/audio_service.py</files>
  <action>Reemplazar 'gemini-2.0-flash' con 'gemini-2.5-flash' en todas las ramas de inicialización en AudioService.__init__</action>
  <verify>.venv/bin/pytest tests/test_audio_regression.py</verify>
  <done>AudioService utiliza gemini-2.5-flash</done>
</task>

<task type="auto">
  <name>Modificar test_audio_regression.py para validar model_id</name>
  <files>tests/test_audio_regression.py</files>
  <action>Actualizar el método test_audio_service_live_integration para simular el cliente genai y validar que _model_id coincide con 'gemini-2.5-flash' en ambos canales de autenticación</action>
  <verify>.venv/bin/pytest tests/test_audio_regression.py</verify>
  <done>Las aserciones verifican que model_id es gemini-2.5-flash y el test de integración pasa en modo test</done>
</task>
