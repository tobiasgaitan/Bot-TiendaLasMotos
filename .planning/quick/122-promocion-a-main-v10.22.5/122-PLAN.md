---
task: 122
name: Promoción a main v10.22.5
description: Fusión y promoción de la rama beta a main, garantizando el despliegue automático del backend sin regresión nomenclatural ni degradación de infraestructura en GCP Cloud Run.
---

# Quick Task 122: Promoción a main v10.22.5

## Objective
Merge and promote the beta branch to main, run local tests offline and synchronously, execute `npx agent-cli eval` to achieve a 1.000 coherence score, and verify the GitHub Actions workflow completion.

## Tasks

<task type="auto">
  <name>Auditar topología y verificar suite de testing completa de forma offline y síncrona en beta</name>
  <files>
    <file>app/services/ai_brain.py</file>
    <file>app/routers/whatsapp.py</file>
  </files>
  <action>Correr suite de pytest local y verificar que pasa con cero errores de forma síncrona/offline.</action>
  <verify>pytest</verify>
  <done>Todos los tests pasan exitosamente.</done>
</task>

<task type="auto">
  <name>Ejecutar npx agent-cli eval en beta</name>
  <files></files>
  <action>Correr la suite de evaluación para asegurar un Coherence Score de 1.000 antes del merge.</action>
  <verify>npx agent-cli eval</verify>
  <done>Coherence Score de 1.000 obtenido y verificado en la terminal.</done>
</task>

<task type="auto">
  <name>Realizar merge de beta a main y hacer push a origin</name>
  <files></files>
  <action>Cambiar a rama main, realizar merge de beta asegurando que no haya conflictos, y realizar git push origin main.</action>
  <verify>git checkout main && git merge beta --no-ff -m "merge branch 'beta' into main for release v10.22.5" && git push origin main</verify>
  <done>Merge realizado correctamente y subido al repositorio remoto.</done>
</task>

---
*Created: 2026-07-05*
