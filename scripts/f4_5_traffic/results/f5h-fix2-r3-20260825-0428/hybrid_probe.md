# Sonda híbrida MATRIZ — f5h-fix2-r3-20260825-0428

- **Ejecutado:** 2026-08-25T10:02:04.787744+00:00
- **dry_run:** False
- **preclean:** True
- **Veredicto global:** ROJO
- **Flags pre/post:** hybrid=true qwen=false (OK)

## Resumen por sesión

| Sesión | Escenario | Profiling | Frontera | Cierre | CoreFail | AuxFail | NoneType | Errores | Veredicto |
|---|---|---|---|---|---|---|---|---|---|
| 1 | matriz_empleado_alto | 9 | 0 | 0 | 0 | 4 | 0 | 3 | ROJO |
| 2 | matriz_independiente_reportado | 7 | 0 | 2 | 0 | 3 | 0 | 1 | ROJO |

### Sesión 1 — matriz_empleado_alto
- Teléfono: `57377009901`
- captured_progression: `[0, 0, 3, 3, 5, 5, 5, 5, 5]`
- score_resultado: `None`
- HYBRID BACKSTOP: 0 | QWEN ROUTE: 0 | DUAL FAILOVER: 0 | route_fallback: 0
- core_failovers: 0 | aux_failovers: 4
- Errores NoneType.strip: 0
- **Errores:**
  - falta cierre_fase_completo (gemini)
  - falta frontera_turno_7_matriz y captured final <7; matriz incompleta
  - score_resultado no esta presente en el doc prospecto (calculate_credit_score no ejecuto)
- **Advertencias:**
  - failover a Gemini en llamadas auxiliares: 4
- **Histograma (52 eventos):**
  | provider | reason | captured | siguiente | fase | timestamp |
  |---|---|---|---|---|---|
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:30:02.626118Z |
  | gemini | default_conservador | 0 | None | PHASE_1_PROFILING | 2026-08-25T09:30:16.529765Z |
  | gemini | default_conservador | 0 | None | None | 2026-08-25T09:30:29.354747Z |
  | gemini | simulacion_ciega_paso2 | 0 | None | PHASE_2_HABEAS_DATA | 2026-08-25T09:30:32.220268Z |
  | gemini | default_conservador | 0 | None | None | 2026-08-25T09:30:34.682004Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:30:36.627146Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:30:47.679744Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:31:08.609653Z |
  | gemini | simulacion_ciega_paso2 | 0 | None | PHASE_2_HABEAS_DATA | 2026-08-25T09:31:22.269624Z |
  | gemini | default_conservador | 0 | None | None | 2026-08-25T09:31:24.044695Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:31:29.435518Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:31:31.865140Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:31:57.178347Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:32:17.391368Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:32:39.927380Z |
  | gemini | simulacion_ciega_paso2 | 0 | None | PHASE_2_HABEAS_DATA | 2026-08-25T09:32:59.073896Z |
  | gemini | default_conservador | 0 | None | None | 2026-08-25T09:33:02.130543Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:33:28.841323Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:33:49.275355Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:34:11.515116Z |
  | gemini | simulacion_ciega_paso2 | 0 | None | PHASE_2_HABEAS_DATA | 2026-08-25T09:34:15.892970Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:34:42.539635Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:35:03.354600Z |
  | deepseek | turno_1_profiling | 0 | Ocupación | PHASE_3_CREDIT_PROFILING | 2026-08-25T09:35:20.706027Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:36:01.330233Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:36:21.376026Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:36:43.559Z |
  | deepseek | turno_1_profiling | 0 | Ocupación | PHASE_3_CREDIT_PROFILING | 2026-08-25T09:37:01.984197Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:37:40.061114Z |
  | deepseek | turno_4_profiling | 3 | Reportes Datacrédito | PHASE_3_CREDIT_PROFILING | 2026-08-25T09:37:53.043648Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:38:20.048157Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:38:40.165441Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:39:02.229432Z |
  | deepseek | turno_4_profiling | 3 | Reportes Datacrédito | PHASE_3_CREDIT_PROFILING | 2026-08-25T09:39:20.701012Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:39:46.939844Z |
  | deepseek | turno_6_profiling | 5 | Gas natural (Brilla) | PHASE_3_CREDIT_PROFILING | 2026-08-25T09:39:59.689506Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:40:24.062706Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:40:44.650130Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:41:07.022891Z |
  | deepseek | turno_6_profiling | 5 | Gas natural (Brilla) | PHASE_3_CREDIT_PROFILING | 2026-08-25T09:41:25.815960Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:41:50.863993Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:42:11.711624Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:42:34.188170Z |
  | deepseek | turno_6_profiling | 5 | Gas natural (Brilla) | PHASE_3_CREDIT_PROFILING | 2026-08-25T09:42:52.590380Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:43:19.972489Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:43:40.475639Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:44:03.000685Z |
  | deepseek | turno_6_profiling | 5 | Gas natural (Brilla) | PHASE_3_CREDIT_PROFILING | 2026-08-25T09:44:21.440547Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:44:56.194554Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:45:16.484785Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:45:39.303661Z |
  | deepseek | turno_6_profiling | 5 | Gas natural (Brilla) | PHASE_3_CREDIT_PROFILING | 2026-08-25T09:45:57.699895Z |

### Sesión 2 — matriz_independiente_reportado
- Teléfono: `57377009902`
- captured_progression: `[0, 2, 2, 4, 5, 6, 6]`
- score_resultado: `255`
- HYBRID BACKSTOP: 0 | QWEN ROUTE: 0 | DUAL FAILOVER: 0 | route_fallback: 0
- core_failovers: 0 | aux_failovers: 3
- Errores NoneType.strip: 0
- **Errores:**
  - falta frontera_turno_7_matriz y captured final <7; matriz incompleta
- **Advertencias:**
  - failover a Gemini en llamadas auxiliares: 3
- **Histograma (41 eventos):**
  | provider | reason | captured | siguiente | fase | timestamp |
  |---|---|---|---|---|---|
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:47:04.239755Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:47:25.051489Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:47:47.551462Z |
  | gemini | default_conservador | 0 | None | PHASE_1_PROFILING | 2026-08-25T09:48:07.356563Z |
  | gemini | default_conservador | 0 | None | None | 2026-08-25T09:48:12.552582Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:48:15.348796Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:49:04.871270Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:49:24.932657Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:49:47.064251Z |
  | gemini | simulacion_ciega_paso2 | 0 | None | PHASE_2_HABEAS_DATA | 2026-08-25T09:50:06.218729Z |
  | gemini | default_conservador | 0 | None | None | 2026-08-25T09:50:08.294901Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:50:34.783689Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:50:55.364158Z |
  | gemini | simulacion_ciega_paso2 | 0 | None | PHASE_2_HABEAS_DATA | 2026-08-25T09:51:06.509310Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:51:33.658561Z |
  | deepseek | turno_1_profiling | 0 | Ocupación | PHASE_3_CREDIT_PROFILING | 2026-08-25T09:51:48.107241Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:52:26.483392Z |
  | deepseek | turno_3_profiling | 2 | Ingresos | PHASE_3_CREDIT_PROFILING | 2026-08-25T09:52:38.709045Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:53:04.352005Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:53:24.446726Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:53:47.405513Z |
  | deepseek | turno_3_profiling | 2 | Ingresos | PHASE_3_CREDIT_PROFILING | 2026-08-25T09:54:05.850599Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:54:31.063812Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:54:51.713148Z |
  | deepseek | turno_5_profiling | 4 | Gastos mensuales | PHASE_3_CREDIT_PROFILING | 2026-08-25T09:55:07.209581Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:55:35.525502Z |
  | deepseek | turno_6_profiling | 5 | Gas natural (Brilla) | PHASE_3_CREDIT_PROFILING | 2026-08-25T09:55:54.212505Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:56:19.094573Z |
  | deepseek | turno_7_profiling | 6 | Vivienda | PHASE_3_CREDIT_PROFILING | 2026-08-25T09:56:34.290285Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:56:59.027750Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:57:20.028203Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:57:42.051371Z |
  | deepseek | turno_7_profiling | 6 | Vivienda | PHASE_3_CREDIT_PROFILING | 2026-08-25T09:58:00.613576Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:58:26.367892Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:58:46.526857Z |
  | gemini | cierre_fase_completo | 8 | COMPLETO | PHASE_3_CREDIT_PROFILING | 2026-08-25T09:59:00.969118Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:59:05.988617Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:59:33.556848Z |
  | gemini | cierre_fase_completo | 8 | COMPLETO | PHASE_3_CREDIT_PROFILING | 2026-08-25T09:59:43.068755Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T09:59:53.734226Z |
  | deepseek | tarea_faq_contexto | 0 | None | None | 2026-08-25T10:00:13.973118Z |
