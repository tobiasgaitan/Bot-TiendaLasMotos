# Roadmap - Bot-TiendaLasMotos

## Tasks Completadas (v10.22.5)
- [x] Alineación stateless del contexto del catálogo para el Juez en `whatsapp.py` (BOT-BUGFIX-121-CONSOLIDATED).
- [x] Corrección de literalidad en Drift Interceptor al cruzar contra el catálogo por alias compuestos (BOT-BUGFIX-118).
- [x] Refactorización dinámica del interceptor de palabras clave de motocicletas e integración del test de alias (BOT-BUGFIX-117).
- [x] Restauración de la bifurcación lógica de Cold Start en el Drift Interceptor y aserciones de test (BOT-BUGFIX-115).
- [x] Restauración del blindaje asíncrono en la inicialización del webhook y suite de pruebas unitarias (BOT-PERF-114).
- [x] Resolución de colisión de Casing ('Semiautomatica' vs 'semiautomatica') en la hidratación de alias de Firestore y mitigación del falso positivo de fallback en el catálogo (BOT-BUGFIX-113).
- [x] Desacoplamiento de alias de catálogo y resolución de importación circular deadlock en caliente en producción (BOT-RESILIENCE-104).
- [x] Flexibilización del Drift Interceptor a 0.30, Null Masking opcional para summary/descripcion y fallback de imagen_url/image_url (BOT-RESILIENCE-102).
- [x] Implementación del Tool Rejection Pattern para calculate_credit_score en PHASE_1_PROFILING y reversión de exclusión.
- [x] Cierre de Hotfix BOT-BRAIN-HABEAS-085: Validación de moto_interest previa a Fase 2 (Habeas Data).

- [x] Excepción `HabeasDataBypassInterrupt` para cortocircuito limpio del while loop en `pensar_respuesta` (BOT-BRAIN-CRITICAL-E2E-084).
- [x] Resolución de la fuga de contexto en contingencias de PermissionError y robustecimiento del parser de precios (BOT-BRAIN-E2E-META-083).
- [x] Resolución de la contingencia de retorno de `PermissionError` en `ai_brain.py` e inyección de `response_parts` (BOT-BRAIN-RETURN-082).
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
