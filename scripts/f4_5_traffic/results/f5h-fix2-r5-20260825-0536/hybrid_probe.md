# Sonda híbrida MATRIZ — f5h-fix2-r5-20260825-0536

- **Ejecutado:** 2026-08-25T11:03:32.023949+00:00
- **dry_run:** False
- **preclean:** True
- **Veredicto global:** VERDE
- **Flags pre/post:** hybrid=true qwen=false (OK)

## Resumen por sesión

| Sesión | Escenario | Profiling | Frontera | Cierre | CoreFail | AuxFail | NoneType | Errores | Veredicto |
|---|---|---|---|---|---|---|---|---|---|
| 1 | matriz_empleado_alto | 6 | 1 | 2 | 0 | 2 | 0 | 0 | VERDE |
| 2 | matriz_independiente_reportado | 6 | 1 | 3 | 0 | 3 | 0 | 0 | VERDE |

### Sesión 1 — matriz_empleado_alto
- Teléfono: `57377009901`
- captured_progression: `[0, 2, 3, 4, 5, 6]`
- score_resultado: `685`
- HYBRID BACKSTOP: 0 | QWEN ROUTE: 0 | DUAL FAILOVER: 0 | route_fallback: 0
- core_failovers: 0 | aux_failovers: 2
- Errores NoneType.strip: 0
- **Advertencias:**
  - failover a Gemini en llamadas auxiliares: 2
- **Histograma (35 eventos):**
  | provider | reason | captured | siguiente | fase | timestamp |
  |---|---|---|---|---|---|
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:37:11.017236Z |
  | gemini | default_conservador | 0 | None | PHASE_1_PROFILING | 2026-08-25T10:37:19.790152Z |
  | gemini | default_conservador | 0 | None | None | 2026-08-25T10:37:26.250526Z |
  | gemini | default_conservador | 0 | None | PHASE_1_PROFILING | 2026-08-25T10:37:31.067083Z |
  | gemini | default_conservador | 0 | None | None | 2026-08-25T10:37:35.345488Z |
  | gemini | default_conservador | 0 | None | None | 2026-08-25T10:37:37.944589Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:37:40.521181Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:39:55.438606Z |
  | gemini | simulacion_ciega_paso2 | 0 | None | PHASE_2_HABEAS_DATA | 2026-08-25T10:40:11.903779Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:40:38.951197Z |
  | gemini | simulacion_ciega_paso2 | 0 | None | PHASE_2_HABEAS_DATA | 2026-08-25T10:40:53.822938Z |
  | gemini | default_conservador | 0 | None | None | 2026-08-25T10:40:55.633016Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:41:21.563144Z |
  | deepseek | turno_1_profiling | 0 | Ocupación | PHASE_3_CREDIT_PROFILING | 2026-08-25T10:41:36.744241Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:42:06.754740Z |
  | deepseek | turno_3_profiling | 2 | Ingresos | PHASE_3_CREDIT_PROFILING | 2026-08-25T10:42:14.911423Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:42:41.556928Z |
  | deepseek | turno_4_profiling | 3 | Reportes Datacrédito | PHASE_3_CREDIT_PROFILING | 2026-08-25T10:42:56.683712Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:43:22.843431Z |
  | deepseek | turno_5_profiling | 4 | Gastos mensuales | PHASE_3_CREDIT_PROFILING | 2026-08-25T10:43:31.661846Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:43:58.342645Z |
  | deepseek | turno_6_profiling | 5 | Gas natural (Brilla) | PHASE_3_CREDIT_PROFILING | 2026-08-25T10:44:09.319619Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:44:35.858856Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:44:56.008935Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:45:18.870304Z |
  | deepseek | turno_7_profiling | 6 | Vivienda | PHASE_3_CREDIT_PROFILING | 2026-08-25T10:45:31.650240Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:45:58.954765Z |
  | gemini | frontera_turno_7_matriz | 7 | Plan celular | PHASE_3_CREDIT_PROFILING | 2026-08-25T10:46:11.229722Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:46:35.460440Z |
  | gemini | cierre_fase_completo | 8 | COMPLETO | PHASE_3_CREDIT_PROFILING | 2026-08-25T10:46:52.261062Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:46:57.934256Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:47:23.838162Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:47:44.593212Z |
  | gemini | cierre_fase_completo | 8 | COMPLETO | PHASE_3_CREDIT_PROFILING | 2026-08-25T10:47:59.224884Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:48:02.606702Z |

### Sesión 2 — matriz_independiente_reportado
- Teléfono: `57377009902`
- captured_progression: `[0, 2, 3, 3, 5, 6]`
- score_resultado: `255`
- HYBRID BACKSTOP: 0 | QWEN ROUTE: 0 | DUAL FAILOVER: 0 | route_fallback: 0
- core_failovers: 0 | aux_failovers: 3
- Errores NoneType.strip: 0
- **Advertencias:**
  - failover a Gemini en llamadas auxiliares: 3
- **Histograma (37 eventos):**
  | provider | reason | captured | siguiente | fase | timestamp |
  |---|---|---|---|---|---|
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:49:06.979563Z |
  | gemini | default_conservador | 0 | None | PHASE_1_PROFILING | 2026-08-25T10:49:23.903054Z |
  | gemini | default_conservador | 0 | None | None | 2026-08-25T10:49:28.594867Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:49:33.205342Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:51:37.339789Z |
  | gemini | simulacion_ciega_paso2 | 0 | None | PHASE_2_HABEAS_DATA | 2026-08-25T10:51:53.823737Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:52:17.481383Z |
  | gemini | simulacion_ciega_paso2 | 0 | None | PHASE_2_HABEAS_DATA | 2026-08-25T10:52:31.060109Z |
  | gemini | default_conservador | 0 | None | None | 2026-08-25T10:52:32.527336Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:52:41.738087Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:53:13.565653Z |
  | deepseek | turno_1_profiling | 0 | Ocupación | PHASE_3_CREDIT_PROFILING | 2026-08-25T10:53:29.449152Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:53:57.265836Z |
  | deepseek | turno_3_profiling | 2 | Ingresos | PHASE_3_CREDIT_PROFILING | 2026-08-25T10:54:11.110218Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:54:39.090141Z |
  | deepseek | turno_4_profiling | 3 | Reportes Datacrédito | PHASE_3_CREDIT_PROFILING | 2026-08-25T10:54:48.183923Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:55:14.710425Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:55:35.200063Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:55:57.925646Z |
  | deepseek | turno_4_profiling | 3 | Reportes Datacrédito | PHASE_3_CREDIT_PROFILING | 2026-08-25T10:56:16.358345Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:56:44.118432Z |
  | deepseek | turno_6_profiling | 5 | Gas natural (Brilla) | PHASE_3_CREDIT_PROFILING | 2026-08-25T10:56:57.984963Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:57:24.850709Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:57:45.006323Z |
  | deepseek | turno_7_profiling | 6 | Vivienda | PHASE_3_CREDIT_PROFILING | 2026-08-25T10:58:00.535502Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:58:29.912039Z |
  | gemini | frontera_turno_7_matriz | 7 | Plan celular | PHASE_3_CREDIT_PROFILING | 2026-08-25T10:58:45.798359Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:59:10.766730Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:59:31.450427Z |
  | gemini | cierre_fase_completo | 8 | COMPLETO | PHASE_3_CREDIT_PROFILING | 2026-08-25T10:59:49.690215Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:59:52.307486Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T11:00:19.357442Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T11:00:40.165855Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T11:01:02.297903Z |
  | gemini | cierre_fase_completo | 8 | COMPLETO | PHASE_3_CREDIT_PROFILING | 2026-08-25T11:01:20.931248Z |
  | gemini | cierre_fase_completo | 8 | COMPLETO | PHASE_3_CREDIT_PROFILING | 2026-08-25T11:01:41.517799Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T11:01:44.740698Z |

## Advertencias globales
- quiesce check: 10 eventos HYBRID ROUTE en los últimos 10 minutos