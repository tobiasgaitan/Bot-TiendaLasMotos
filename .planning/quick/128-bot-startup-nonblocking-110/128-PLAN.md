---
task: 128
name: bot-startup-nonblocking-110
description: Habilitar una estrategia de Inicialización Secuencial Desbloqueante en el punto de entrada de la aplicación, permitiendo que FastAPI libere el puerto 8080 de manera inmediata.
---

# Quick Task 128: bot-startup-nonblocking-110

## Objective
Desacoplar la inicialización pesada de Firestore y el catálogo en `app/main.py` delegándola a una tarea asíncrona en segundo plano, liberando el puerto HTTP inmediatamente para cumplir con el contrato de Google Cloud Run, pero manteniendo el bloqueo del procesamiento agéntico de mensajes en el router retornando HTTP 503 hasta que la hidratación finalice.

## Tasks

<task type="auto">
  <name>Configure non-blocking lifespan in main.py</name>
  <files>
    <file>app/main.py</file>
  </files>
  <action>Modificar la función lifespan para inicializar app.state.catalog_ready = False, instanciar los clientes y delegar run_initialization_sync a una tarea asíncrona en segundo plano con asyncio.create_task.</action>
  <verify>.venv/bin/pytest tests/test_startup_lock.py</verify>
  <done>El lifespan del app inicia inmediatamente y no bloquea el arranque en producción.</done>
</task>

<task type="auto">
  <name>Implement catalog_ready checks in webhook guards</name>
  <files>
    <file>app/routers/whatsapp.py</file>
  </files>
  <action>Actualizar los guards de webhook_handler y task_processor en whatsapp.py para verificar app.state.catalog_ready con un fallback a la cuenta dinámica de ítems.</action>
  <verify>.venv/bin/pytest tests/test_startup_lock.py</verify>
  <done>Los webhooks rechazan el tráfico con HTTP 503 hasta que catalog_ready sea True.</done>
</task>

<task type="auto">
  <name>Verify and update test suite</name>
  <files>
    <file>tests/test_startup_lock.py</file>
  </files>
  <action>Actualizar las pruebas de test_startup_lock.py para validar el comportamiento en segundo plano del lifespan y verificar el rechazo HTTP 503.</action>
  <verify>npx @tobiasgaitan/agent-cli eval</verify>
  <done>Todas las pruebas pasan con un Coherence Score de 1.000.</done>
</task>

---
*Created: 2026-07-06*
