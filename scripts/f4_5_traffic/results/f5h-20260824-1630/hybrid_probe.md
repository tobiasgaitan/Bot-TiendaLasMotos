# Sonda híbrida MATRIZ — f5h-20260824-1630

- **Ejecutado:** 2026-08-24T21:42:32.779404+00:00
- **dry_run:** False
- **Veredicto global:** ROJO
- **Flags pre/post:** hybrid=true qwen=false (OK)

## Resumen por sesión

| Sesión | Escenario | Provider logs | Core | Errores | Veredicto |
|---|---|---|---|---|---|
| 1 | matriz_empleado_alto | 22 | 0 profiling | 3 | ROJO |
| 2 | matriz_independiente_reportado | 12 | 0 profiling | 3 | ROJO |

### Sesión 1 — matriz_empleado_alto
- Teléfono: `57377009901`
- Secuencia núcleo: `[]`
- captured_counts: `[]`
- HYBRID BACKSTOP: 0 | failover: 0 | QWEN ROUTE: 0 | DUAL FAILOVER: 0
- **Errores:**
  - esperaba 6 turnos de profiling deepseek, hay 0
  - falta frontera_turno_7_matriz (gemini)
  - falta cierre_fase_completo (gemini)

### Sesión 2 — matriz_independiente_reportado
- Teléfono: `57377009902`
- Secuencia núcleo: `[]`
- captured_counts: `[]`
- HYBRID BACKSTOP: 0 | failover: 0 | QWEN ROUTE: 0 | DUAL FAILOVER: 0
- **Errores:**
  - esperaba 6 turnos de profiling deepseek, hay 0
  - falta frontera_turno_7_matriz (gemini)
  - falta cierre_fase_completo (gemini)
