# Sonda híbrida MATRIZ — matriz-fix-20260825-1054

- **Ejecutado:** 2026-08-25T16:22:08.781128+00:00
- **dry_run:** False
- **preclean:** True
- **Veredicto global:** VERDE
- **Flags pre/post:** hybrid=true qwen=false (OK)

## Resumen por sesión

| Sesión | Escenario | Profiling | Frontera | Cierre | CoreFail | AuxFail | NoneType | Errores | Veredicto |
|---|---|---|---|---|---|---|---|---|---|
| 1 | matriz_empleado_alto | 6 | 1 | 2 | 0 | 5 | 0 | 0 | VERDE |
| 2 | matriz_independiente_reportado | 6 | 1 | 2 | 0 | 6 | 0 | 0 | VERDE |

### Sesión 1 — matriz_empleado_alto
- Teléfono: `57377009901`
- captured_progression: `[0, 2, 3, 4, 4, 6]`
- score_resultado: `685`
- HYBRID BACKSTOP: 0 | QWEN ROUTE: 0 | DUAL FAILOVER: 0 | route_fallback: 0
- core_failovers: 0 | aux_failovers: 5
- Errores NoneType.strip: 0
- **Advertencias:**
  - failover a Gemini en llamadas auxiliares: 5
- **Histograma (38 eventos):**
  | provider | reason | captured | siguiente | fase | timestamp |
  |---|---|---|---|---|---|
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T15:56:11.454359Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T15:56:31.533327Z |
  | gemini | default_conservador | 0 | None | PHASE_1_PROFILING | 2026-08-25T15:56:48.932393Z |
  | gemini | default_conservador | 0 | None | None | 2026-08-25T15:56:53.913432Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T15:56:58.535866Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T15:57:19.095961Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T15:57:30.439347Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T15:58:07.757469Z |
  | gemini | simulacion_ciega_paso2 | 0 | None | PHASE_2_HABEAS_DATA | 2026-08-25T15:58:15.772317Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T15:58:39.857666Z |
  | gemini | simulacion_ciega_paso2 | 0 | None | PHASE_2_HABEAS_DATA | 2026-08-25T15:58:50.519674Z |
  | gemini | default_conservador | 0 | None | None | 2026-08-25T15:58:52.087368Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T15:59:24.025562Z |
  | deepseek | turno_1_profiling | 0 | Ocupación | PHASE_3_CREDIT_PROFILING | 2026-08-25T15:59:41.268694Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:00:18.276389Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:00:38.674290Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:01:01.436601Z |
  | deepseek | turno_3_profiling | 2 | Ingresos | PHASE_3_CREDIT_PROFILING | 2026-08-25T16:01:17.711153Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:01:45.920563Z |
  | deepseek | turno_4_profiling | 3 | Reportes Datacrédito | PHASE_3_CREDIT_PROFILING | 2026-08-25T16:01:52.128408Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:02:20.149841Z |
  | deepseek | turno_5_profiling | 4 | Gastos mensuales | PHASE_3_CREDIT_PROFILING | 2026-08-25T16:02:32.224089Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:03:02.352346Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:03:22.950880Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:03:45.441869Z |
  | deepseek | turno_5_profiling | 4 | Gastos mensuales | PHASE_3_CREDIT_PROFILING | 2026-08-25T16:04:04.528952Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:04:37.883287Z |
  | deepseek | turno_7_profiling | 6 | Vivienda | PHASE_3_CREDIT_PROFILING | 2026-08-25T16:04:56.573855Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:05:25.479427Z |
  | gemini | frontera_turno_7_matriz | 7 | Plan celular | PHASE_3_CREDIT_PROFILING | 2026-08-25T16:05:41.842995Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:06:07.699350Z |
  | gemini | cierre_fase_completo | 8 | COMPLETO | PHASE_3_CREDIT_PROFILING | 2026-08-25T16:06:22.770299Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:06:26.275350Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:06:54.032082Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:07:14.336090Z |
  | gemini | cierre_fase_completo | 8 | COMPLETO | PHASE_3_CREDIT_PROFILING | 2026-08-25T16:07:23.983983Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:07:27.163579Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:07:47.668885Z |

### Sesión 2 — matriz_independiente_reportado
- Teléfono: `57377009902`
- captured_progression: `[0, 2, 3, 4, 5, 6]`
- score_resultado: `255`
- HYBRID BACKSTOP: 0 | QWEN ROUTE: 0 | DUAL FAILOVER: 0 | route_fallback: 0
- core_failovers: 0 | aux_failovers: 6
- Errores NoneType.strip: 0
- **Advertencias:**
  - failover a Gemini en llamadas auxiliares: 6
- **Histograma (38 eventos):**
  | provider | reason | captured | siguiente | fase | timestamp |
  |---|---|---|---|---|---|
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:08:47.282151Z |
  | gemini | default_conservador | 0 | None | PHASE_1_PROFILING | 2026-08-25T16:08:53.559884Z |
  | gemini | default_conservador | 0 | None | None | 2026-08-25T16:08:56.585925Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:09:03.973485Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:09:24.724193Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:09:38.221314Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:09:51.916293Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:10:53.928873Z |
  | gemini | simulacion_ciega_paso2 | 0 | None | PHASE_2_HABEAS_DATA | 2026-08-25T16:11:03.970523Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:11:30.793550Z |
  | gemini | simulacion_ciega_paso2 | 0 | None | PHASE_2_HABEAS_DATA | 2026-08-25T16:11:42.867952Z |
  | gemini | default_conservador | 0 | None | None | 2026-08-25T16:11:43.928460Z |
  | gemini | default_conservador | 0 | None | None | 2026-08-25T16:12:04.219314Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:12:36.837187Z |
  | deepseek | turno_1_profiling | 0 | Ocupación | PHASE_3_CREDIT_PROFILING | 2026-08-25T16:12:43.628266Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:13:17.450499Z |
  | deepseek | turno_3_profiling | 2 | Ingresos | PHASE_3_CREDIT_PROFILING | 2026-08-25T16:13:27.065799Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:13:55.402084Z |
  | deepseek | turno_4_profiling | 3 | Reportes Datacrédito | PHASE_3_CREDIT_PROFILING | 2026-08-25T16:14:09.729391Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:14:38.327852Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:14:58.568097Z |
  | deepseek | turno_5_profiling | 4 | Gastos mensuales | PHASE_3_CREDIT_PROFILING | 2026-08-25T16:15:15.820759Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:15:45.463646Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:16:06.167307Z |
  | deepseek | turno_6_profiling | 5 | Gas natural (Brilla) | PHASE_3_CREDIT_PROFILING | 2026-08-25T16:16:18.477011Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:16:47.752519Z |
  | deepseek | turno_7_profiling | 6 | Vivienda | PHASE_3_CREDIT_PROFILING | 2026-08-25T16:16:58.052041Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:17:26.420910Z |
  | gemini | frontera_turno_7_matriz | 7 | Plan celular | PHASE_3_CREDIT_PROFILING | 2026-08-25T16:17:38.470175Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:18:04.182756Z |
  | gemini | cierre_fase_completo | 8 | COMPLETO | PHASE_3_CREDIT_PROFILING | 2026-08-25T16:18:15.240749Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:18:19.716461Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:18:46.576196Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:19:06.707182Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:19:29.298448Z |
  | gemini | cierre_fase_completo | 8 | COMPLETO | PHASE_3_CREDIT_PROFILING | 2026-08-25T16:19:47.872437Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:19:51.258217Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T16:20:11.813215Z |

## Advertencias globales
- quiesce check: 8 eventos HYBRID ROUTE en los últimos 10 minutos