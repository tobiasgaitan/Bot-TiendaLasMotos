# Sonda híbrida MATRIZ — dryrun-matriz-100

- **Ejecutado:** 2026-08-25T13:56:59.173140+00:00
- **dry_run:** True
- **preclean:** True
- **Veredicto global:** VERDE
- **Flags pre/post:** hybrid=true qwen=false (skipped (dry-run))

## Resumen por sesión

| Sesión | Escenario | Profiling | Frontera | Cierre | CoreFail | AuxFail | NoneType | Errores | Veredicto |
|---|---|---|---|---|---|---|---|---|---|
| 1 | matriz_empleado_alto | 0 | 0 | 0 | 0 | 0 | 0 | 0 | VERDE (dry-run) |
| 2 | matriz_independiente_reportado | 0 | 0 | 0 | 0 | 0 | 0 | 0 | VERDE (dry-run) |

### Sesión 1 — matriz_empleado_alto
- Teléfono: `57377009901`
- captured_progression: `[]`
- score_resultado: `None`
- HYBRID BACKSTOP: 0 | QWEN ROUTE: 0 | DUAL FAILOVER: 0 | route_fallback: 0
- core_failovers: 0 | aux_failovers: 0
- Errores NoneType.strip: 0

### Sesión 2 — matriz_independiente_reportado
- Teléfono: `57377009902`
- captured_progression: `[]`
- score_resultado: `None`
- HYBRID BACKSTOP: 0 | QWEN ROUTE: 0 | DUAL FAILOVER: 0 | route_fallback: 0
- core_failovers: 0 | aux_failovers: 0
- Errores NoneType.strip: 0
