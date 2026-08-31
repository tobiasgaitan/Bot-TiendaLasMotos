# Sonda híbrida MATRIZ — probe-robust-single-20260825-2146

- **Ejecutado:** 2026-08-26T03:03:57.347824+00:00
- **dry_run:** False
- **preclean:** True
- **Veredicto global:** ROJO
- **Flags pre/post:** hybrid=true qwen=false (OK)

## Resumen por sesión

| Sesión | Escenario | Profiling | Frontera | Cierre | CoreFail | AuxFail | NoneType | Errores | Veredicto |
|---|---|---|---|---|---|---|---|---|---|
| 1 | matriz_empleado_alto | 6 | 3 | 0 | 0 | 1 | 0 | 2 | ROJO |

### Sesión 1 — matriz_empleado_alto
- Teléfono: `57377009901`
- captured_progression: `[0, 2, 3, 4, 5, 5]`
- score_resultado: `None`
- HYBRID BACKSTOP: 0 | QWEN ROUTE: 0 | DUAL FAILOVER: 0 | route_fallback: 0
- core_failovers: 0 | aux_failovers: 1
- Errores NoneType.strip: 0
- **Errores:**
  - falta cierre_fase_completo (gemini)
  - score_resultado no esta presente en el doc prospecto (calculate_credit_score no ejecuto)
- **Advertencias:**
  - failover a Gemini en llamadas auxiliares: 1
- **Histograma (43 eventos):**
  | provider | reason | captured | siguiente | fase | timestamp |
  |---|---|---|---|---|---|
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-26T02:48:05.942721Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-26T02:48:26.317740Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-26T02:48:48.517544Z |
  | gemini | default_conservador | 0 | None | PHASE_1_PROFILING | 2026-08-26T02:49:07.296821Z |
  | gemini | default_conservador | 0 | None | None | 2026-08-26T02:49:10.347948Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-26T02:49:17.906576Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-26T02:49:28.000561Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-26T02:50:03.695875Z |
  | gemini | simulacion_ciega_paso2 | 0 | None | PHASE_2_HABEAS_DATA | 2026-08-26T02:50:19.100144Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-26T02:50:44.129840Z |
  | gemini | simulacion_ciega_paso2 | 0 | None | PHASE_2_HABEAS_DATA | 2026-08-26T02:50:54.701261Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-26T02:51:21.503705Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-26T02:51:41.845591Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-26T02:52:04.314084Z |
  | gemini | simulacion_ciega_paso2 | 0 | None | PHASE_2_HABEAS_DATA | 2026-08-26T02:52:15.600134Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-26T02:52:41.888502Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-26T02:53:02.858067Z |
  | deepseek | turno_1_profiling | 0 | Ocupación | PHASE_3_CREDIT_PROFILING | 2026-08-26T02:53:17.035552Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-26T02:53:56.329758Z |
  | deepseek | turno_3_profiling | 2 | Ingresos | PHASE_3_CREDIT_PROFILING | 2026-08-26T02:54:05.238738Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-26T02:54:29.517629Z |
  | deepseek | turno_4_profiling | 3 | Reportes Datacrédito | PHASE_3_CREDIT_PROFILING | 2026-08-26T02:54:44.751593Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-26T02:55:09.154400Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-26T02:55:29.698556Z |
  | deepseek | turno_5_profiling | 4 | Gastos mensuales | PHASE_3_CREDIT_PROFILING | 2026-08-26T02:55:43.859349Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-26T02:56:08.915535Z |
  | deepseek | turno_6_profiling | 5 | Gas natural (Brilla) | PHASE_3_CREDIT_PROFILING | 2026-08-26T02:56:24.807133Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-26T02:56:49.191239Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-26T02:57:10.112319Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-26T02:57:32.975235Z |
  | deepseek | turno_6_profiling | 5 | Gas natural (Brilla) | PHASE_3_CREDIT_PROFILING | 2026-08-26T02:57:51.841602Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-26T02:58:16.358432Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-26T02:58:36.996301Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-26T02:58:59.967971Z |
  | gemini | frontera_turno_7_matriz | 7 | Plan celular | PHASE_3_CREDIT_PROFILING | 2026-08-26T02:59:15.370089Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-26T02:59:39.784363Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-26T03:00:00.746588Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-26T03:00:23.296162Z |
  | gemini | frontera_turno_7_matriz | 7 | Plan celular | PHASE_3_CREDIT_PROFILING | 2026-08-26T03:00:41.892309Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-26T03:01:10.045785Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-26T03:01:30.785141Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-26T03:01:53.271373Z |
  | gemini | frontera_turno_7_matriz | 7 | Plan celular | PHASE_3_CREDIT_PROFILING | 2026-08-26T03:02:11.878846Z |

## Advertencias globales
- quiesce check: 2 eventos HYBRID ROUTE en los últimos 10 minutos