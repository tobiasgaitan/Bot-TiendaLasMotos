---
task: 036
name: Purga de Deuda Técnica Documental
description: Purga de archivos legados de la iteración V6 y redundancias de despliegue.
---

# Quick Task 036: Purga de Deuda Técnica Documental

## Objective
Purgar de forma segura múltiples archivos legados de la iteración V6 y redundancias de despliegue en la raíz del repositorio, garantizando que no queden variables de entorno huérfanas sin migrar al esquema actual y verificando con tests la integridad de 'Ficha Tecnica:'.

## Tasks

<task type="auto">
  <name>Auditoría y Purga de Archivos</name>
  <files>CLOUD_SHELL_DEPLOYMENT.md, DEPLOYMENT.md, DEPLOYMENT_ALTERNATIVE.md, V6_CONFIG_FIX.md, V6_DEPLOYMENT_GUIDE.md, V6_EXECUTIVE_SUMMARY.md, V6_ROUTER_ACTIVATION.md, V6_SIMPLIFIED_CONFIG.md</files>
  <action>Realizar git rm sobre los archivos indicados para remover la documentación legada V6.</action>
  <verify>git status</verify>
  <done>Los 8 archivos legados se eliminaron correctamente del control de versiones.</done>
</task>

<task type="auto">
  <name>Verificación del Directorio Raíz</name>
  <files></files>
  <action>Ejecutar scaffold --check o ls para garantizar un directorio raíz limpio.</action>
  <verify>ls -la | grep -iE "deployment|v6_"</verify>
  <done>El directorio raíz no contiene los archivos purgados, excepto DEPLOYMENT_GUIDE.md.</done>
</task>

<task type="auto">
  <name>Verificación de Coherencia y Test Unitario</name>
  <files>tests/test_pcc_ficha_tecnica.py</files>
  <action>Ejecutar pytest para verificar que el test de aserción de contenido 'Ficha Tecnica:' (que evita mutaciones vacías o None silenciosos) pasa correctamente.</action>
  <verify>.venv/bin/pytest tests/test_pcc_ficha_tecnica.py</verify>
  <done>El test unitario de no-regresión pasa exitosamente.</done>
</task>
