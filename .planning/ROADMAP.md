# Roadmap - Bot-TiendaLasMotos

## Tasks Completadas (v10.12.4)
- [x] Identificación forense del error 404 NotFound de Firestore en Cloud Run ante ráfagas de Webhooks.
- [x] Refactorización de `update_prospect_summary` y `update_whatsapp_status` usando .set(merge=True) para tolerar documentos purgados.
- [x] Adaptación de contratos y firmas en la suite de pruebas unitarias.
- [x] Certificación local del framework agéntico con Score de Coherencia 1.000.
- [x] Transición de la ruta crítica del webhook a llamadas síncronas bloqueantes (await) y testeo unitario de persistencia.

## Próximos Pasos
- [ ] Monitoreo en producción (GCP Live Logs) del comportamiento del comando `/reset`.
