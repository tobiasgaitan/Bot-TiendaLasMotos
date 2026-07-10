---
task: 149
name: Audio Credentials Integration Test
description: Modificar tests/test_audio_regression.py para inyectar un Test de Integración Desacoplado que instancie AudioService nativamente, y modificar AudioService para evitar silenciar fallos de credenciales/gRPC de Google aplicando la Regla de Oro Forense.
---

# Quick Task 149: Audio Credentials Integration Test

## Objective
Implementar un test de integración en tests/test_audio_regression.py que instancie AudioService nativamente para verificar la conexión/credenciales de Google Cloud, y corregir en app/services/audio_service.py la captura genérica de excepciones para que propague DefaultCredentialsError y APIError con la Regla de Oro Forense.

## Tasks

<task type="auto">
  <name>Modificar AudioService para propagar excepciones de credenciales y API</name>
  <files>app/services/audio_service.py</files>
  <action>Importar DefaultCredentialsError y modificar los bloques try-except para registrar mediante logger.exception y propagar los errores de credenciales (DefaultCredentialsError) y fallos gRPC de Google (APIError), registrando e.response.text si está disponible.</action>
  <verify>python3 -c "from app.services.audio_service import AudioService; AudioService.test_integration()"</verify>
  <done>El comando se ejecuta de forma independiente arrojando el error de credenciales explícito o listando los modelos si existen credenciales válidas en la terminal.</done>
</task>

<task type="auto">
  <name>Modificar tests/test_audio_regression.py e inyectar test de integración</name>
  <files>tests/test_audio_regression.py</files>
  <action>Inyectar un Test de Integración Desacoplado (test_audio_service_live_integration) que instancie AudioService nativamente, capture y registre específicamente DefaultCredentialsError y APIError, cumpliendo la Regla de Oro Forense.</action>
  <verify>pytest tests/test_audio_regression.py</verify>
  <done>Todos los tests en tests/test_audio_regression.py pasan correctamente.</done>
</task>

---
*Created: 2026-07-10*
