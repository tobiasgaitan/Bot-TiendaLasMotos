# Sonda híbrida MATRIZ — f5h-fix2-r4-20260825-0508

- **Ejecutado:** 2026-08-25T10:34:35.731582+00:00
- **dry_run:** False
- **preclean:** True
- **Veredicto global:** ROJO
- **Flags pre/post:** hybrid=true qwen=false (OK)

## Resumen por sesión

| Sesión | Escenario | Profiling | Frontera | Cierre | CoreFail | AuxFail | NoneType | Errores | Veredicto |
|---|---|---|---|---|---|---|---|---|---|
| 1 | matriz_empleado_alto | 6 | 1 | 2 | 0 | 3 | 0 | 0 | AMARILLO |
| 2 | matriz_independiente_reportado | 6 | 2 | 1 | 0 | 1 | 0 | 0 | AMARILLO |

### Sesión 1 — matriz_empleado_alto
- Teléfono: `57377009901`
- captured_progression: `[0, 2, 3, 3, 5, 6]`
- score_resultado: `685`
- HYBRID BACKSTOP: 0 | QWEN ROUTE: 0 | DUAL FAILOVER: 0 | route_fallback: 0
- core_failovers: 0 | aux_failovers: 3
- Errores NoneType.strip: 0
- **Advertencias:**
  - failover a Gemini en llamadas auxiliares: 3
- **Histograma (39 eventos):**
  | provider | reason | captured | siguiente | fase | timestamp |
  |---|---|---|---|---|---|
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:09:05.219503Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:09:25.353595Z |
  | gemini | default_conservador | 0 | None | PHASE_1_PROFILING | 2026-08-25T10:09:38.603849Z |
  | gemini | default_conservador | 0 | None | None | 2026-08-25T10:09:44.087122Z |
  | gemini | default_conservador | 0 | None | None | 2026-08-25T10:09:45.831760Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:09:55.684429Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:11:09.143784Z |
  | gemini | simulacion_ciega_paso2 | 0 | None | PHASE_2_HABEAS_DATA | 2026-08-25T10:11:27.763636Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:11:51.755653Z |
  | gemini | simulacion_ciega_paso2 | 0 | None | PHASE_2_HABEAS_DATA | 2026-08-25T10:12:08.754924Z |
  | gemini | default_conservador | 0 | None | None | 2026-08-25T10:12:11.630739Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:12:23.302121Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:12:50.547225Z |
  | deepseek | turno_1_profiling | 0 | Ocupación | PHASE_3_CREDIT_PROFILING | 2026-08-25T10:13:00.083207Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:13:39.894678Z |
  | deepseek | turno_3_profiling | 2 | Ingresos | PHASE_3_CREDIT_PROFILING | 2026-08-25T10:13:47.792780Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:14:18.556536Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:14:39.553741Z |
  | deepseek | turno_4_profiling | 3 | Reportes Datacrédito | PHASE_3_CREDIT_PROFILING | 2026-08-25T10:14:54.862574Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:15:22.709169Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:15:42.765263Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:16:05.634080Z |
  | deepseek | turno_4_profiling | 3 | Reportes Datacrédito | PHASE_3_CREDIT_PROFILING | 2026-08-25T10:16:24.139396Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:16:53.481737Z |
  | deepseek | turno_6_profiling | 5 | Gas natural (Brilla) | PHASE_3_CREDIT_PROFILING | 2026-08-25T10:17:07.611388Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:17:34.093832Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:17:55.021552Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:18:17.759166Z |
  | deepseek | turno_7_profiling | 6 | Vivienda | PHASE_3_CREDIT_PROFILING | 2026-08-25T10:18:31.715668Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:18:58.733496Z |
  | gemini | frontera_turno_7_matriz | 7 | Plan celular | PHASE_3_CREDIT_PROFILING | 2026-08-25T10:19:16.050983Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:19:41.555242Z |
  | gemini | cierre_fase_completo | 8 | COMPLETO | PHASE_3_CREDIT_PROFILING | 2026-08-25T10:19:58.822923Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:20:03.119463Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:20:30.700402Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:20:51.103503Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:21:13.982623Z |
  | gemini | cierre_fase_completo | 8 | COMPLETO | PHASE_3_CREDIT_PROFILING | 2026-08-25T10:21:32.508361Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:21:36.816629Z |

### Sesión 2 — matriz_independiente_reportado
- Teléfono: `57377009902`
- captured_progression: `[0, 2, 3, 4, 5, 6]`
- score_resultado: `255`
- HYBRID BACKSTOP: 0 | QWEN ROUTE: 0 | DUAL FAILOVER: 0 | route_fallback: 0
- core_failovers: 0 | aux_failovers: 1
- Errores NoneType.strip: 0
- **Advertencias:**
  - failover a Gemini en llamadas auxiliares: 1
- **Histograma (36 eventos):**
  | provider | reason | captured | siguiente | fase | timestamp |
  |---|---|---|---|---|---|
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:22:41.463393Z |
  | gemini | default_conservador | 0 | None | PHASE_1_PROFILING | 2026-08-25T10:22:54.474381Z |
  | gemini | default_conservador | 0 | None | None | 2026-08-25T10:22:59.622641Z |
  | gemini | default_conservador | 0 | None | PHASE_1_PROFILING | 2026-08-25T10:23:06.907689Z |
  | gemini | default_conservador | 0 | None | None | 2026-08-25T10:23:20.027433Z |
  | gemini | default_conservador | 0 | None | None | 2026-08-25T10:23:22.205919Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:23:24.862774Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:24:02.424836Z |
  | gemini | simulacion_ciega_paso2 | 0 | None | PHASE_2_HABEAS_DATA | 2026-08-25T10:24:15.139827Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:24:38.820506Z |
  | gemini | simulacion_ciega_paso2 | 0 | None | PHASE_2_HABEAS_DATA | 2026-08-25T10:24:51.014689Z |
  | gemini | default_conservador | 0 | None | None | 2026-08-25T10:24:52.856136Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:25:19.244918Z |
  | deepseek | turno_1_profiling | 0 | Ocupación | PHASE_3_CREDIT_PROFILING | 2026-08-25T10:25:25.720737Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:25:54.464172Z |
  | deepseek | turno_3_profiling | 2 | Ingresos | PHASE_3_CREDIT_PROFILING | 2026-08-25T10:26:03.240287Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:26:29.849533Z |
  | deepseek | turno_4_profiling | 3 | Reportes Datacrédito | PHASE_3_CREDIT_PROFILING | 2026-08-25T10:26:38.026192Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:27:04.622757Z |
  | deepseek | turno_5_profiling | 4 | Gastos mensuales | PHASE_3_CREDIT_PROFILING | 2026-08-25T10:27:15.620807Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:27:44.304110Z |
  | deepseek | turno_6_profiling | 5 | Gas natural (Brilla) | PHASE_3_CREDIT_PROFILING | 2026-08-25T10:28:00.000956Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:28:26.836914Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:28:47.615597Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:29:09.836257Z |
  | deepseek | turno_7_profiling | 6 | Vivienda | PHASE_3_CREDIT_PROFILING | 2026-08-25T10:29:28.225825Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:29:54.203686Z |
  | gemini | frontera_turno_7_matriz | 7 | Plan celular | PHASE_3_CREDIT_PROFILING | 2026-08-25T10:30:06.249487Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:30:32.199187Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:30:53.169982Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:31:15.626195Z |
  | gemini | frontera_turno_7_matriz | 7 | Plan celular | PHASE_3_CREDIT_PROFILING | 2026-08-25T10:31:34.268564Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:32:02.329064Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:32:22.437380Z |
  | gemini | cierre_fase_completo | 8 | COMPLETO | PHASE_3_CREDIT_PROFILING | 2026-08-25T10:32:39.783684Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:32:52.203982Z |

## Errores globales
- quiesce check falló: 8 eventos HYBRID ROUTE en los últimos 10 minutos