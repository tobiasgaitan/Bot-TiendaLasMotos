# Roadmap - Bot-TiendaLasMotos

## Tasks Completadas (v10.12.6)
- [x] Identificación forense del error 404 NotFound de Firestore en Cloud Run ante ráfagas de Webhooks.
- [x] Refactorización de `update_prospect_summary` y `update_whatsapp_status` usando .set(merge=True) para tolerar documentos purgados.
- [x] Adaptación de contratos y firmas en la suite de pruebas unitarias.
- [x] Certificación local del framework agéntico con Score de Coherencia 1.000.
- [x] Transición de la ruta crítica del webhook a llamadas síncronas bloqueantes (await) y testeo unitario de persistencia.
- [x] Monitoreo en producción (GCP Live Logs) del comportamiento del comando `/reset`.
- [x] Implementación de `update_last_interaction` en `MemoryService` con aislamiento E.164 y vinculación Langfuse.
- [x] Extensión del blindaje zombi del router para escenario post-reset (`is_fully_deleted`).
- [x] Test de integración post-reset con `exists: False` y aserciones rígidas anti-null (Condición #3).
- [x] Decoración del webhook de WhatsApp (`_handle_message_background`) y propagación de trazas Langfuse con adaptador seguro No-Op (Task 071).
- [x] Instalación del binario k6 en el pipeline de qa-pipeline.yml (Task 072).
- [x] Reemplazo de GPG keyserver por pipeline atómico curl para k6 en qa-pipeline.yml (Task 075).
- [x] Firma HMAC dinámica en test k6 con `crypto.hmac()` eliminando hardcode estático que causaba HTTP 401 (Task 076).

## Próximos Pasos
- [ ] Validación en producción (GCP Live Logs) del flujo completo post-reset con telemetría Langfuse end-to-end.
