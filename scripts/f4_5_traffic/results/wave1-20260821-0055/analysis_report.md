# Análisis F4.5 — wave1-20260821-0055 (oleada 1)

- **Modo piloto:** False
- **Veredicto:** ROJO
- **Generado:** 2026-08-21T01:15:25.899750+00:00

## Denominadores

- Escenarios por brazo: 40
- Expected tool hits (calculate_credit_score) por brazo: 16
- Trazas Langfuse recuperadas: A=111, B=111
- Fuente de latencia: Langfuse trace latency (seconds) (segundos)

## Métricas por brazo

| Métrica | Brazo A (baseline) | Brazo B (Qwen) |
|---|---|---|
| Escenarios | 40 | 40 |
| Errores HTTP | 0 | 0 |
| Tasa errores | 0.0000 | 0.0000 |
| Tool-call rate | 0.4375 | 0.0625 |
| Score mean | 587.1400 | 685.0000 |
| Score p50 | 635.0000 | 685 |
| Score p90 | 685.0000 | 685 |
| Latencia p50 s | 12.2500 | 9.2400 |
| Latencia p95 s | 63.5000 | 21.5700 |
| CATALOG_VALIDATION_FAIL | 29 | 29 |
| DUAL FAILOVER | 0 | 0 |
| TOOL-SUPPRESS retry_failed | 1 | 1 |

## Comparación A/B

- Δ tool-call rate: -37.5pp (ok=False)
- Δ score mean: 97.86 (ok=False)
- Ratio p95 latencia B/A: 0.34 (ok=True)
- Failover rate B: 0.0 (ok=True)
- Shift mix ruta: {'R1_Banco': 0.0, 'R2_Revision': 0.1429, 'R3_Brilla': 0.0, 'R4_Rechazo': 0.1429} (ok=False)
- MATRIZ divergencias: 7/8 (ok=False)

## Distribución de rutas de cierre

| Ruta | A | B |
|---|---|---|
| R1_Banco | 0.00% | 0.00% |
| R2_Revision | 85.71% | 100.00% |
| R3_Brilla | 0.00% | 0.00% |
| R4_Rechazo | 14.29% | 0.00% |

## CATALOG_VALIDATION_FAIL por escenario (correlación A vs B)

| Escenario | A | B |
|---|---|---|
| catalog_125_delivery | 4 | 0 |
| catalog_150_ciudad | 4 | 1 |
| catalog_automatica | 0 | 1 |
| catalog_boxer_competitor | 1 | 0 |
| catalog_deportivas | 1 | 0 |
| catalog_trabajo | 0 | 1 |
| credit_delivery_cuota | 1 | 1 |
| credit_sport_cuota | 1 | 0 |
| extraction_datacredito | 0 | 2 |
| extraction_forma_pago | 0 | 1 |
| extraction_gas | 0 | 1 |
| extraction_habeas | 1 | 1 |
| extraction_plan_celular | 0 | 1 |
| extraction_vivienda | 0 | 1 |
| matriz_empleado_alto | 0 | 1 |
| matriz_independiente_reportado | 0 | 1 |
| matriz_paz_salvo | 1 | 1 |
| matriz_pensionado | 0 | 1 |

## Notas
- El prefijo 5737700xxxxx debe excluirse de dashboards de deliverability (C5-F45-02).
- La colección subyacente es `prospectos` compartida con prod; la purga se ejecuta con cleanup_synthetic.py.
