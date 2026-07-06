---
task: 129
name: Restore External Infra Environment Variables and Disable CPU Throttling
description: El cliente de google-cloud-firestore en entorno serverless pierde la conectividad física de gRPC disparando excepciones CANCELLED y timeouts de sockets controlados por el interceptor de I/O en save_message y load_all.
---

# Quick Task 129: Restore External Infra Environment Variables and Disable CPU Throttling

## Objective
Restore the full set of environment variables wiped out by a previous deployment, and disable CPU throttling on Cloud Run to allow background database synchronization to run at full CPU capacity without timing out during startup.

## Tasks

<task type="auto">
  <name>Restore Cloud Run Env Vars and Disable CPU Throttling</name>
  <files>[]</files>
  <action>Run gcloud run services update to restore all required environment variables and add the --no-cpu-throttling flag on bot-tiendalasmotos-beta.</action>
  <verify>gcloud run services describe bot-tiendalasmotos-beta --region=us-central1 --project=tiendalasmotos --format=json</verify>
  <done>Cloud Run service bot-tiendalasmotos-beta is updated successfully, CPU throttling is disabled, and the container starts up and passes startup probe.</done>
</task>

---
*Created: 2026-07-06*
