# Análisis F4.5 — mini-qwen-fix-001 (oleada 1)

- **Modo piloto:** True
- **Veredicto:** ROJO
- **Generado:** 2026-08-21T04:50:17.367942+00:00

## Denominadores

- Escenarios por brazo: 6
- Expected tool hits (calculate_credit_score) por brazo: 2
- Trazas Langfuse recuperadas: A=0, B=0
- Fuente de latencia: Langfuse trace latency (seconds) (segundos)

## Métricas por brazo

| Métrica | Brazo A (baseline) | Brazo B (Qwen) |
|---|---|---|
| Escenarios | 6 | 6 |
| Errores HTTP | 2 | 2 |
| Tasa errores | 0.3333 | 0.3333 |
| Tool-call rate | 0.5000 | 0.5000 |
| Score mean | 685.0000 | 685.0000 |
| Score p50 | 685 | 685 |
| Score p90 | 685 | 685 |
| Latencia p50 s | 0.0000 | 0.0000 |
| Latencia p95 s | 0.0000 | 0.0000 |
| CATALOG_VALIDATION_FAIL | 0 | 0 |
| DUAL FAILOVER | 0 | 0 |
| TOOL-SUPPRESS retry_failed | 0 | 0 |

## Comparación A/B

- Δ tool-call rate: 0.0pp (ok=True)
- Δ score mean: 0.0 (ok=True)
- Ratio p95 latencia B/A: — (ok=None)
- Failover rate B: 0.0 (ok=True)
- Shift mix ruta: {'R1_Banco': 0.0, 'R2_Revision': 0.0, 'R3_Brilla': 0.0, 'R4_Rechazo': 0.0} (ok=True)
- MATRIZ divergencias: 0/1 (ok=True)

## Distribución de rutas de cierre

| Ruta | A | B |
|---|---|---|
| R1_Banco | 0.00% | 0.00% |
| R2_Revision | 100.00% | 100.00% |
| R3_Brilla | 0.00% | 0.00% |
| R4_Rechazo | 0.00% | 0.00% |

## CATALOG_VALIDATION_FAIL por escenario (correlación A vs B)

Sin eventos CATALOG_VALIDATION_FAIL en esta oleada.

## Notas
- El prefijo 5737700xxxxx debe excluirse de dashboards de deliverability (C5-F45-02).
- La colección subyacente es `prospectos` compartida con prod; la purga se ejecuta con cleanup_synthetic.py.
