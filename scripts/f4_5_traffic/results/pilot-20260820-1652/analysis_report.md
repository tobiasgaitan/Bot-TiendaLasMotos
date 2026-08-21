# Análisis F4.5 — pilot-20260820-1652 (oleada 1)

- **Modo piloto:** True
- **Veredicto:** VERDE
- **Generado:** 2026-08-20T22:41:59.399375+00:00

## Métricas por brazo

| Métrica | Brazo A (baseline) | Brazo B (Qwen) |
|---|---|---|
| Escenarios | 6 | 6 |
| Errores HTTP | 0 | 0 |
| Tasa errores | 0.0000 | 0.0000 |
| Tool-call rate | 0.0000 | 0.0000 |
| Score mean | — | — |
| Score p50 | — | — |
| Score p90 | — | — |
| Latencia p50 ms | 0.0000 | 0.0000 |
| Latencia p95 ms | 0.0000 | 0.0000 |
| CATALOG_VALIDATION_FAIL | 5 | 5 |
| DUAL FAILOVER | 0 | 0 |
| TOOL-SUPPRESS retry_failed | 0 | 0 |

## Comparación A/B

- Δ tool-call rate: 0.0pp (ok=True)
- Δ score mean: — (ok=None)
- Ratio p95 latencia B/A: — (ok=None)
- Failover rate B: 0.0 (ok=True)
- Shift mix ruta: {'R1_Banco': 0.0, 'R2_Revision': 0.0, 'R3_Brilla': 0.0, 'R4_Rechazo': 0.0} (ok=True)
- MATRIZ divergencias: 0/0 (ok=True)

## Distribución de rutas de cierre

| Ruta | A | B |
|---|---|---|
| R1_Banco | 0.00% | 0.00% |
| R2_Revision | 0.00% | 0.00% |
| R3_Brilla | 0.00% | 0.00% |
| R4_Rechazo | 0.00% | 0.00% |

## Notas
- El prefijo 5737700xxxxx debe excluirse de dashboards de deliverability (C5-F45-02).
- La colección subyacente es `prospectos` compartida con prod; la purga se ejecuta con cleanup_synthetic.py.
