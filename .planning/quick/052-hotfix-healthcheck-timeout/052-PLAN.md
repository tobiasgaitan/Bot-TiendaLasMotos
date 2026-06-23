---
task: 052
name: Hotfix Healthcheck Timeout
description: El despliegue falla por timeout/fallo en el Healthcheck de Dockerfile durante el inicio del contenedor.
---

# Quick Task 052: Hotfix Healthcheck Timeout

## Objective
Optimizar la carga síncrona del bot durante la inicialización en app/main.py y aumentar el start-period a 60s en el Dockerfile para evitar fallos de timeout en el healthcheck.

## Tasks

<task type="auto">
  <name>Optimize Lifespan Startup Parallelization</name>
  <files>app/main.py</files>
  <action>Paralelizar la inicialización y carga de configuración de config_service y config_loader usando un ThreadPoolExecutor en el lifespan del backend en app/main.py.</action>
  <verify>uv run pytest</verify>
  <done>La inicialización paralela pasa las pruebas locales de integración y unitarias.</done>
</task>

<task type="auto">
  <name>Increase Docker Healthcheck Start Period</name>
  <files>Dockerfile</files>
  <action>Modificar el start-period del HEALTHCHECK en el Dockerfile de 40s a 60s.</action>
  <verify>docker build -t test-bot . && TEST_MODE=true docker run --rm -p 8080:8080 -d --name temp-test-bot test-bot && sleep 5 && curl -s -f http://localhost:8080/health && docker stop temp-test-bot</verify>
  <done>La imagen de Docker se construye correctamente y responde con código 200 en http://localhost:8080/health en TEST_MODE.</done>
</task>
