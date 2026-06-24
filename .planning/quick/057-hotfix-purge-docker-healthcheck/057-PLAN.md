---
task: 057
name: hotfix-purge-docker-healthcheck
description: La instrucción HEALTHCHECK explícita en el Dockerfile provoca fallos internos en el motor de Cloud Build durante la compilación aislando el contenedor.
---

# Quick Task 057: hotfix-purge-docker-healthcheck

## Objective
Eliminar de forma completa la directiva HEALTHCHECK del Dockerfile para evitar fallos internos en Cloud Build durante la compilación.

## Tasks

<task type="auto">
  <name>Eliminar HEALTHCHECK de Dockerfile</name>
  <files>Dockerfile</files>
  <action>Eliminar las líneas que contienen la directiva HEALTHCHECK (líneas 54-56)</action>
  <verify>! grep -i "HEALTHCHECK" Dockerfile</verify>
  <done>El archivo Dockerfile no debe contener la directiva HEALTHCHECK</done>
</task>
