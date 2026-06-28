---
task: 080
name: Log Sink y Pub Sub Alerting
description: Implementar Log Sink y Pub Sub Alerting para CATALOG_VALIDATION_FAIL
---

# Quick Task 080: Log Sink y Pub Sub Alerting

## Objective
Configurar un mecanismo de alerta asíncrono nativo de GCP Cloud Logging (Log Sink) filtrando la firma CATALOG_VALIDATION_FAIL (con payload enriquecido) y errores de _firestore_io, despachando mediante Pub/Sub a un webhook receptor blindado con Dead Letter Topic (DLT) y Exponential Backoff.

## Tasks

<task type="auto">
  <name>Enriquecimiento Estructurado en ai_brain.py</name>
  <files>[app/services/ai_brain.py]</files>
  <action>Modificar app/services/ai_brain.py para inyectar la firma CATALOG_VALIDATION_FAIL estructurada con user_id y texto de consulta en los logs warning y error.</action>
  <verify>grep -n 'CATALOG_VALIDATION_FAIL' app/services/ai_brain.py</verify>
  <done>La firma CATALOG_VALIDATION_FAIL está físicamente en app/services/ai_brain.py y se loguea con user_id y la consulta.</done>
</task>

<task type="auto">
  <name>Actualizar .gcloudignore Canónico</name>
  <files>[.gcloudignore]</files>
  <action>Reemplazar .gcloudignore por la versión canónica de GCP que ignore carpetas de desarrollo locales y excluya .gitignore para evitar colisiones.</action>
  <verify>cat .gcloudignore</verify>
  <done>El archivo .gcloudignore contiene la lista de exclusiones de desarrollo de forma limpia.</done>
</task>

<task type="auto">
  <name>Documentar Script de Infraestructura GCP</name>
  <files>[bin/setup_gcp_alerting.sh]</files>
  <action>Crear bin/setup_gcp_alerting.sh con los comandos CLI gcloud validados y la configuración hardened (DLT, Exponential Backoff, Sink filter calibrado).</action>
  <verify>chmod +x bin/setup_gcp_alerting.sh && bash -n bin/setup_gcp_alerting.sh</verify>
  <done>El script de configuración de GCP está creado y sintácticamente validado.</done>
</task>

---
*Created: 2026-06-28*
