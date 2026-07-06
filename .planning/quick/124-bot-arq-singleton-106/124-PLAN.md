---
task: 124
name: bot-arq-singleton-106
description: El enrutador app/routers/whatsapp.py inicializa una instancia local duplicada (catalog_service_local) en lugar de consumir el Singleton global importado desde app.services.catalog_service, causando que hilos concurrentes operen con catálogos vacíos o desincronizados tras comandos de control.
---

# Quick Task 124: bot-arq-singleton-106

## Objective
Purge the duplicate local `catalog_service_local` in `app/routers/whatsapp.py` and replace all references character-by-character to use the canonical `catalog_service` singleton. Remove duplicate initialization lines (129-132) and verify via pytest.

## Tasks

<task type="auto">
  <name>Sustituir catalog_service_local por el singleton catalog_service</name>
  <files>
    <file>app/routers/whatsapp.py</file>
  </files>
  <action>
    - Importar el singleton catalog_service desde app.services.catalog_service
    - Eliminar la variable global catalog_service_local = None
    - Remover la referencia a catalog_service_local en el global statement
    - Remover las líneas de inicialización duplicada (129-132) del router
    - Reemplazar todas las referencias a catalog_service_local por catalog_service en app/routers/whatsapp.py
  </action>
  <verify>npx agent-cli eval</verify>
  <done>La suite de pruebas pasa con un Score de Coherencia de 1.000.</done>
</task>
