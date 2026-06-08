Versión: v10.5.0
Posición: Cierre de ticket BOT-ARQ-837 — unificación de persistencia bajo colección prospectos

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 034 | Resolución de autenticación en npm publish y GitHub Packages | 2026-05-18 | fa5d25a | 034-npm-publish-auth-fix |
| 035 | Purga de llaves legacy y alineación de la firma de calculate_credit_score | 2026-05-19 | ce351a9 | 035-purga-llaves-firma-credito |
| 036 | Purga de archivos legados de la iteración V6 y redundancias de despliegue | 2026-05-19 | 487207b | 036-purga-deuda-tecnica-documental |
| 037 | Conmutación a Brilla de Gases, captura de cédula e intercepción de Crediorbe | 2026-05-20 | ef6e6c4 | 037-brilla-entity-switch |
| 038 | Adaptar búsqueda de catálogo a propiedades reales en español de Firestore | 2026-05-20 | 5894d99 | 038-spanish-catalog-keys-fix |
| 039 | Corrección de variable inexistente _lf a langfuse_context en ai_brain.py | 2026-05-20 | 8726fdf | 039-langfuse-context-fix |
| 040 | Resiliencia ante fallo en cascada: skip de ítems corruptos y absorción de gRPC en update_whatsapp_status | 2026-06-04 | 82709ca | 040-cascade-failure-denial-of-service |
| 041 | Unificación de persistencia bajo colección prospectos (BOT-ARQ-837) | 2026-06-07 | a140e02 | 041-unificar-persistencia-prospectos |
| 042 | Cierre BOT-DEBT-042: Sincronía bloqueante y blindaje PCC Pro | 2026-06-07 | 35ba089 | 042-sincronia-pcc-pro |
| 043 | BOT-BUG-044-REV2 Judge Sync and Fallback Log | 2026-06-08 | 797c584 | 043-bot-bug-044-rev2 |

- [2026-06-08] v10.5.1: Hotfix finalizado para BOT-BUG-044-REV2. Sincronización del juez para permitir Simulación Ciega Anticipada y log nativo de fallback.
- [2026-06-07] v10.5.0: BOT-ARQ-837 completado. Colección 'mensajeria' eliminada de todos los módulos de producción. 104/104 tests passed.
- [2026-06-04] v10.3.1: Hotfix finalizado para BOT-BUG-043. Estabilización de persistencia Firestore mediante ContingencySnapshot.
