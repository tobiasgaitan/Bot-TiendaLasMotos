---
task: 058
name: hotfix-gcp-robots-probe
description: El balanceador de Cloud Run aborta el despliegue al recibir respuestas HTTP 404 en rutas automatizadas del sistema como /robots.txt.
---

# Quick Task 058: hotfix-gcp-robots-probe

## Objective
Modificar quirúrgicamente app/main.py para inyectar un endpoint explícito que responda a peticiones de /robots.txt con código HTTP 200 de forma inmediata (texto plano vacío) y certificarlo mediante pytest local.

## Tasks

<task type="auto">
  <name>Inyectar endpoint /robots.txt en app/main.py</name>
  <files>app/main.py</files>
  <action>Añadir la ruta `@app.get("/robots.txt")` que retorne una respuesta de texto plano vacía con estado 200 OK.</action>
  <verify>uv run pytest tests/test_robots.py</verify>
  <done>El endpoint /robots.txt responde con estado 200 OK y cuerpo vacío.</done>
</task>

<task type="auto">
  <name>Crear test para /robots.txt en tests/test_robots.py</name>
  <files>tests/test_robots.py</files>
  <action>Crear tests/test_robots.py para verificar que la petición GET a /robots.txt retorna un 200 OK con texto plano vacío.</action>
  <verify>uv run pytest tests/test_robots.py</verify>
  <done>El test pasa exitosamente y confirma el retorno correcto del endpoint.</done>
</task>

---
*Created: 2026-06-24*
