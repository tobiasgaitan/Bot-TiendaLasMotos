---
task: 072
name: Install k6 Binary in GHA
description: Fallo en el job qa-gate por ausencia del binario k6 (Error: spawn k6 ENOENT) al ejecutar las pruebas de rendimiento en el pipeline de GitHub Actions.
---

# Quick Task 072: Install k6 Binary in GHA

## Objective
Añadir un paso previo a 'Execute Performance Test' en el pipeline de GitHub Actions (.github/workflows/qa-pipeline.yml) para instalar formalmente Grafana k6 en el runner de Ubuntu usando los comandos oficiales de Linux.

## Tasks

<task type="auto">
  <name>Install k6 Binary in GHA</name>
  <files>.github/workflows/qa-pipeline.yml</files>
  <action>Modificar .github/workflows/qa-pipeline.yml para añadir el paso de instalación de k6 antes del paso de ejecución de pruebas de rendimiento.</action>
  <verify>Validar la sintaxis y los cambios locales del workflow de GitHub Actions.</verify>
  <done>El archivo .github/workflows/qa-pipeline.yml tiene el paso de instalación de k6 antes de 'Execute Performance Test'.</done>
</task>

---
*Created: 2026-06-27*
