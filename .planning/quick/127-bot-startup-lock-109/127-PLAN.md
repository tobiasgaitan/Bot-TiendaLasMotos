---
task: 127
name: bot-startup-lock-109
description: Enforce strict startup locking and timeout fail-fast to protect against Cold-Starts on Google Cloud Run. Reject webhooks with HTTP 503 if the catalog is not 100% loaded (at least 60 items).
---

# Quick Task 127: bot-startup-lock-109

## Objective
Garantizar determinismo absoluto e inmunidad ante Cold-Starts:
1. Bloqueo Mandatorio de Arranque: El lifespan de `app/main.py` ejecutará de forma síncrona la inicialización de los servicios de base de datos dentro de un timeout estricto de 5 segundos (`asyncio.wait_for` sobre un `asyncio.to_thread`).
2. Caída Rápida (Fail-Fast): Si la sincronización excede los 5 segundos o la inicialización falla, se lanzará una excepción `RuntimeError` para forzar la caída del contenedor y abortar el despliegue.
3. Arranque Inflexible: Si el catálogo cargado en memoria tiene menos de 60 ítems (configurable vía `MIN_CATALOG_ITEMS`), el arranque en producción lanzará una excepción abortando el inicio.
4. Protección de Webhooks: Los endpoints `/` (webhook_handler) y `/task-processor` en `app/routers/whatsapp.py` verificarán de forma inflexible la presencia del catálogo cargado, respondiendo de inmediato con HTTP 503 si el catálogo no cumple el umbral mínimo (60 ítems).
5. No Regresión en Tests: El entorno de pruebas usará variables de entorno (`TEST_MODE="true"`, `MIN_CATALOG_ITEMS="0"`) para no interferir con las aserciones de pytest.

## Tasks

<task type="auto">
  <name>Configure Settings with min_catalog_items</name>
  <files>
    <file>app/core/config.py</file>
  </files>
  <action>
    - Agregar `self.min_catalog_items: int = int(os.getenv("MIN_CATALOG_ITEMS", "60"))` en la clase Settings.
  </action>
  <verify>.venv/bin/pytest tests/test_health_check.py</verify>
  <done>Settings se actualiza correctamente y los tests existentes no se ven afectados.</done>
</task>

<task type="auto">
  <name>Enforce synchronous startup lock in main.py</name>
  <files>
    <file>app/main.py</file>
  </files>
  <action>
    - Modificar la función `lifespan` para encapsular la secuencia de inicialización síncrona en un helper `run_initialization_sync()`.
    - Ejecutar el helper dentro de `asyncio.wait_for` con `asyncio.to_thread` usando `settings.db_timeout` (5s).
    - Verificar la cantidad de ítems cargados en el catálogo y lanzar `RuntimeError` si es menor a `settings.min_catalog_items` (a menos que esté en `TEST_MODE`).
    - Propagar excepciones y fallar rápidamente.
  </action>
  <verify>.venv/bin/pytest tests/test_health_check.py</verify>
  <done>El arranque bloquea y verifica el tamaño de catálogo, fallando en caso de error o lentitud.</done>
</task>

<task type="auto">
  <name>Implement Webhook Reject guards in whatsapp.py</name>
  <files>
    <file>app/routers/whatsapp.py</file>
  </files>
  <action>
    - Modificar el endpoint `webhook_handler` (POST /) para llamar a `_ensure_services()` al inicio y verificar el tamaño del catálogo contra `settings.min_catalog_items`.
    - Lanzar un HTTP 503 con mensaje explícito si el catálogo no está completamente hidratado.
    - Modificar el endpoint `task_processor` de forma análoga para llamar a `_ensure_services()` y validar el catálogo antes de proceder con el procesamiento.
  </action>
  <verify>.venv/bin/pytest tests/test_webhook_sync_block.py</verify>
  <done>Los webhooks rechazan solicitudes con HTTP 503 cuando el catálogo no está hidratado.</done>
</task>

<task type="auto">
  <name>Configure Test Mode variables in conftest.py</name>
  <files>
    <file>tests/conftest.py</file>
  </files>
  <action>
    - Actualizar la fixture `mock_env_vars` para parchar `TEST_MODE="true"` y `MIN_CATALOG_ITEMS="0"` en `os.environ`.
  </action>
  <verify>.venv/bin/pytest</verify>
  <done>Todos los 202 tests pasan correctamente con el mock de entorno activado.</done>
</task>

<task type="auto">
  <name>Implement test suite for startup locking and guards</name>
  <files>
    <file>tests/test_startup_lock.py</file>
  </files>
  <action>
    - Crear un archivo de pruebas unitarias que certifique la protección de los endpoints ante catálogos incompletos (HTTP 503) y la propagación de excepciones en el lifespan ante timeouts de base de datos.
  </action>
  <verify>.venv/bin/pytest tests/test_startup_lock.py</verify>
  <done>El nuevo test de bloqueo y guarda de arranque pasa al 100%.</done>
</task>

---
*Created: 2026-07-06*
