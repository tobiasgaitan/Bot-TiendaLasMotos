# Sonda híbrida MATRIZ — paso2-fix-20260825-1038

- **Ejecutado:** 2026-08-25T15:43:21.997649+00:00
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
- **Histograma (8 eventos):**
  | provider | reason | captured | siguiente | fase | timestamp |
  |---|---|---|---|---|---|
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T15:40:07.600842Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T15:40:27.745146Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T15:40:50.066036Z |
  | gemini | default_conservador | 0 | None | PHASE_1_PROFILING | 2026-08-25T15:41:07.360338Z |
  | gemini | default_conservador | 0 | None | None | 2026-08-25T15:41:10.041091Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T15:41:14.791274Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T15:41:18.321905Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T15:41:32.890418Z |
