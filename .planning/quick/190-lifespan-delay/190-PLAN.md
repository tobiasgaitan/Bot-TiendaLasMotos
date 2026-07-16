---
task: 190
name: Lifespan Delay
description: Inyectar un retardo asíncrono no bloqueante estricto de 2 segundos mediante 'await asyncio.sleep(2)' al inicio absoluto de '_run_deferred_initialization' en 'app/main.py'. Actualizar el caso de prueba 'test_deferred_init_port_available_before_hydration' en 'tests/test_startup_lock.py' para enviar un GET a '/health' con TestClient y verificar el status 'starting' inmediato antes de la hidratación de red. Ejecutar npx agent-cli eval para certificar el Score de 1.000.
---

# Quick Task 190: Lifespan Delay

## Objective
Garantizar de manera determinista que el hook de lifespan de FastAPI complete su yield inmediatamente permitiendo a Uvicorn realizar el bind del puerto 8080 en Cloud Run, retardando la inicialización en background por 2 segundos, y verificar mediante TestClient en la suite de pruebas.

## Tasks

<task type="auto">
  <name>Inyectar retardo asíncrono en main.py</name>
  <files>app/main.py</files>
  <action>Introducir un retardo asíncrono no bloqueante estricto de 2 segundos (await asyncio.sleep(2)) al inicio absoluto de la función '_run_deferred_initialization'.</action>
  <verify>uv run pytest tests/test_startup_lock.py</verify>
  <done>El retardo asíncrono está al inicio de la función y las pruebas básicas pasan.</done>
</task>

<task type="auto">
  <name>Actualizar test de regresión en test_startup_lock.py</name>
  <files>tests/test_startup_lock.py</files>
  <action>Modificar 'test_deferred_init_port_available_before_hydration' para inicializar la aplicación con TestClient, realizar un GET a '/health' y verificar que responde con HTTP 200 y status 'starting' antes de esperar a la hidratación.</action>
  <verify>uv run pytest tests/test_startup_lock.py</verify>
  <done>El test de regresión verifica la responsividad inmediata del puerto 8080 en '/health' y la suite de pruebas pasa completamente.</done>
</task>

<task type="auto">
  <name>Certificación final con agent-cli</name>
  <files>app/main.py, tests/test_startup_lock.py</files>
  <action>Ejecutar la validación completa con npx agent-cli eval para asegurar no-regresiones y obtener un score de 1.000.</action>
  <verify>npx agent-cli eval</verify>
  <done>El score de coherencia es 1.000 y el 100% de las pruebas pasan.</done>
</task>

---
*Created: 2026-07-16*
