---
task: 069
name: hotfix-test-namespace-patch
description: Fallo del test de integración de recuperación zombi (AttributeError) provocado por intentar hacer patch de un atributo que no reside en el namespace global del router debido al uso de lazy imports.
---

# Quick Task 069: hotfix-test-namespace-patch

## Objective
Corregir la ruta del parche de inyección para `whatsapp_service` en `tests/test_zombie_recovery_flow.py` cambiándolo a `app.services.whatsapp_service.whatsapp_service` para resolver el AttributeError provocado por el lazy import en el router, y validar que la suite de pruebas pase.

## Tasks

<task type="auto">
  <name>Modificar parche de inyección en test_zombie_recovery_flow.py</name>
  <files>tests/test_zombie_recovery_flow.py</files>
  <action>Cambiar patch('app.routers.whatsapp.whatsapp_service') por patch('app.services.whatsapp_service.whatsapp_service') en la línea 51.</action>
  <verify>uv run pytest tests/test_zombie_recovery_flow.py</verify>
  <done>El test de integración pasa exitosamente con "1 passed".</done>
</task>
