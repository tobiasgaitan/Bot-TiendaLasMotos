# Análisis F4.5 — mini-qwen-fix-090 (oleada 1)

- **Modo piloto:** True
- **Veredicto:** ROJO
- **Generado:** 2026-08-21T06:14:39.794852+00:00

## Denominadores

- Escenarios por brazo: 12
- Expected tool hits (calculate_credit_score) por brazo: 12
- Trazas Langfuse recuperadas: A=0, B=0
- Fuente de latencia: Langfuse trace latency (seconds) (segundos)

## Métricas por brazo

| Métrica | Brazo A (baseline) | Brazo B (Qwen) |
|---|---|---|
| Escenarios | 12 | 12 |
| Errores HTTP | 0 | 0 |
| Tasa errores | 0.0000 | 0.0000 |
| Tool-call rate | 0.5833 | 0.0833 |
| Score mean | 580.0000 | 235.0000 |
| Score p50 | 635.0000 | 235 |
| Score p90 | 735.0000 | 235 |
| Latencia p50 s | 0.0000 | 0.0000 |
| Latencia p95 s | 0.0000 | 0.0000 |
| CATALOG_VALIDATION_FAIL | 0 | 0 |
| DUAL FAILOVER | 0 | 0 |
| TOOL-SUPPRESS retry_failed | 0 | 0 |

## Comparación A/B

- Δ tool-call rate: -50.0pp (ok=False)
- Δ score mean: -345.0 (ok=False)
- Ratio p95 latencia B/A: — (ok=None)
- Failover rate B: 0.0 (ok=True)
- Shift mix ruta: {'R1_Banco': 0.1429, 'R2_Revision': 0.5714, 'R3_Brilla': 0.0, 'R4_Rechazo': 0.7143} (ok=False)
- MATRIZ divergencias: 8/8 (ok=False)

## Distribución de rutas de cierre

| Ruta | A | B |
|---|---|---|
| R1_Banco | 14.29% | 0.00% |
| R2_Revision | 57.14% | 0.00% |
| R3_Brilla | 0.00% | 0.00% |
| R4_Rechazo | 28.57% | 100.00% |

## CATALOG_VALIDATION_FAIL por escenario (correlación A vs B)

Sin eventos CATALOG_VALIDATION_FAIL en esta oleada.

## Notas
- El prefijo 5737700xxxxx debe excluirse de dashboards de deliverability (C5-F45-02).
- La colección subyacente es `prospectos` compartida con prod; la purga se ejecuta con cleanup_synthetic.py.
