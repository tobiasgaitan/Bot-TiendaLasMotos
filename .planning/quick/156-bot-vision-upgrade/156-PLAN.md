---
task: 156
name: bot-vision-upgrade
description: Desalineación de infraestructura multimodal en app/services/vision_service.py que fuerza el uso de gemini-2.0-flash en lugar de gemini-2.5-flash
---

# Quick Task 156: bot-vision-upgrade

## Objective
Desacoplar la inicialización rígida de `self._model_id` en `VisionService` para apuntar a `gemini-2.5-flash` de forma nativa. Implementar un caso de prueba unitario robusto y real en `tests/test_vision_service.py` que compruebe la inicialización mediante mock, y que garantice que ante respuestas vacías o nulas de la API de Gemini, se lance un `ValueError` explícito y se registren logs estructurados con la traza/traceback del origen (Zero-Silent-Failures).

## Tasks

<task type="auto">
  <name>Actualizar model_id en VisionService</name>
  <files>[app/services/vision_service.py]</files>
  <action>Modificar self._model_id a "gemini-2.5-flash" en el constructor de VisionService. Añadir validaciones para lanzar ValueError cuando la API de Gemini devuelva payloads vacíos o textos nulos en todos sus métodos internos. Cambiar capturas genéricas para usar logger.exception y re-propagar el error.</action>
  <verify>.venv/bin/pytest tests/test_vision_service.py</verify>
  <done>El código de VisionService actualizado a gemini-2.5-flash y manejo de excepciones robusto completado.</done>
</task>

<task type="auto">
  <name>Crear pruebas unitarias para VisionService</name>
  <files>[tests/test_vision_service.py]</files>
  <action>Implementar test_vision_service_initialization para validar que se asigne gemini-2.5-flash al instanciar el servicio con un mock de firestore.Client. Implementar test_vision_service_null_payload_error para verificar que se arroje un ValueError y se llame a logger.exception ante respuestas nulas.</action>
  <verify>.venv/bin/pytest tests/test_vision_service.py</verify>
  <done>Pruebas creadas y pasando exitosamente.</done>
</task>

<task type="auto">
  <name>Verificar suite completa</name>
  <files>[]</files>
  <action>Ejecutar evaluación completa mediante agent-cli eval.</action>
  <verify>npx @tobiasgaitan/agent-cli eval</verify>
  <done>La evaluación finaliza con un Coherence Score de 1.000.</done>
</task>

---
*Created: 2026-07-11*
