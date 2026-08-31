# Sonda híbrida MATRIZ — paso2-retry-20260825-1050

- **Ejecutado:** 2026-08-25T15:54:59.038006+00:00
- **dry_run:** False
- **preclean:** True
- **Veredicto global:** ROJO
- **Flags pre/post:** hybrid=true qwen=false (OK)

## Resumen por sesión

| Sesión | Escenario | Profiling | Frontera | Cierre | CoreFail | AuxFail | NoneType | Errores | Veredicto |
|---|---|---|---|---|---|---|---|---|---|
| 1 | paso2_cuota | 0 | 0 | 0 | 0 | 0 | 0 | 1 | ROJO |

### Sesión 1 — paso2_cuota
- Teléfono: `57377009901`
- captured_progression: `[]`
- score_resultado: `None`
- HYBRID BACKSTOP: 0 | QWEN ROUTE: 0 | DUAL FAILOVER: 0 | route_fallback: 0
- core_failovers: 0 | aux_failovers: 0
- Errores NoneType.strip: 0
- **Errores:**
  - egreso no contiene cuota/simulación de crédito (modelo no invocó calculate_credit_score o devolvió solo ficha)
- **Advertencias:**
  - score_resultado no está presente (esperado en simulación ciega de PASO 2)
- **Histograma (7 eventos):**
  | provider | reason | captured | siguiente | fase | timestamp |
  |---|---|---|---|---|---|
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T15:51:45.852913Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T15:52:06.473429Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T15:52:28.968839Z |
  | gemini | default_conservador | 0 | None | PHASE_1_PROFILING | 2026-08-25T15:52:44.862123Z |
  | gemini | default_conservador | 0 | None | None | 2026-08-25T15:52:54.953485Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T15:52:58.563841Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T15:53:12.528120Z |

## Advertencias globales
- quiesce check: 8 eventos HYBRID ROUTE en los últimos 10 minutos