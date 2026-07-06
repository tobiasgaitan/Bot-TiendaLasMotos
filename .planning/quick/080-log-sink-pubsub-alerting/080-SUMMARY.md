# Quick Task 080: Log Sink y Pub Sub Alerting — Summary

**Executed:** 2026-06-28
**Status:** Complete

## What Was Done
1. **Enriquecimiento de Logs en ai_brain.py**:
   - Modificado [ai_brain.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/services/ai_brain.py) para registrar la firma `CATALOG_VALIDATION_FAIL` en los niveles `warning` y `error`.
   - Inyectada la extracción dinámica de `user_id` y el texto de la consulta del usuario (`query`) para proveer contexto forense rico de negocio (JSON-like structured logging) desacoplado.
2. **Actualización de Exclusión de Despliegue (.gcloudignore)**:
   - Configurado [.gcloudignore](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/.gcloudignore) con la versión canónica de GCP, aislando por completo las exclusiones de desarrollo de dependencias locales, caches y tests sin heredar ni colisionar con `.gitignore`.
3. **Automatización de Infraestructura de GCP**:
   - Creado y validado sintácticamente [setup_gcp_alerting.sh](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/bin/setup_gcp_alerting.sh) en el directorio `bin/` con la configuración hardened aprobada por el ingeniero:
     - Tópicos de Pub/Sub principal (`log-alerts-topic`) y Dead Letter Topic (`log-alerts-dlt`).
     - Log Sink nativo calibrado para evitar falsos positivos de escrituras en Firestore (`_firestore_io` solo capturado cuando `severity>=ERROR`).
     - Suscripción Push blindada con Exponential Backoff (`--min-retry-delay=10s`, `--max-retry-delay=600s`) y vinculada al DLT.

## Files Modified
| File | Action | Description |
|------|--------|-------------|
| [app/services/ai_brain.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/services/ai_brain.py) | Modified | Inyección de la firma CATALOG_VALIDATION_FAIL enriquecida. |
| [.gcloudignore](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/.gcloudignore) | Modified | Reemplazo con .gcloudignore canónico de GCP. |
| [bin/setup_gcp_alerting.sh](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/bin/setup_gcp_alerting.sh) | Created | Script de aprovisionamiento de infraestructura de alertas en GCP. |
| [.planning/quick/080-log-sink-pubsub-alerting/080-PLAN.md](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/.planning/quick/080-log-sink-pubsub-alerting/080-PLAN.md) | Created | Plan de tareas atómicas. |

## Verification
- Ejecutado `grep -n 'CATALOG_VALIDATION_FAIL' app/services/ai_brain.py` para constatar la existencia física de la firma estructurada.
- Ejecutada la suite completa de pruebas locales mediante `npx agent-cli eval`.
- Coherence Score obtenido: **1.000 (167/167 Tests PASSED)**.

---
*Completed: 2026-06-28*
