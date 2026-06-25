---
task: 065
name: fix-pipeline-secrets
description: Parametrizar WHATSAPP_APP_SECRET en el pipeline de GitHub Actions para evitar regresiones de firma (HTTP 401) en cada push.
---

# Quick Task 065: fix-pipeline-secrets

## Objective
Evitar que el pipeline de GitHub Actions pise la variable WHATSAPP_APP_SECRET al desplegar el bot en Cloud Run, previniendo regresiones de firma HTTP 401.

## Tasks

<task type="auto">
  <name>Parametrizar secreto en deploy.yml</name>
  <files>[".github/workflows/deploy.yml"]</files>
  <action>Modificar el archivo de workflow de GitHub Actions deploy.yml para añadir la variable WHATSAPP_APP_SECRET en el paso de despliegue con uvx google-agents-cli deploy.</action>
  <verify>cat .github/workflows/deploy.yml</verify>
  <done>El archivo deploy.yml contiene WHATSAPP_APP_SECRET asignado al secreto correspondiente de GitHub.</done>
</task>

<task type="auto">
  <name>Parametrizar secreto en deploy-beta.yml</name>
  <files>[".github/workflows/deploy-beta.yml"]</files>
  <action>Modificar el archivo de workflow de GitHub Actions deploy-beta.yml para añadir la variable WHATSAPP_APP_SECRET en el paso de despliegue de gcloud run deploy.</action>
  <verify>cat .github/workflows/deploy-beta.yml</verify>
  <done>El archivo deploy-beta.yml contiene WHATSAPP_APP_SECRET asignado al secreto correspondiente de GitHub.</done>
</task>

---
*Created: 2026-06-24*
