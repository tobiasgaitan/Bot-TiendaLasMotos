# Sonda híbrida MATRIZ — f5h-20260824-2122

- **Ejecutado:** 2026-08-25T02:49:09.221603+00:00
- **dry_run:** False
- **preclean:** True
- **Veredicto global:** ROJO
- **Flags pre/post:** hybrid=true qwen=false (OK)

## Resumen por sesión

| Sesión | Escenario | Provider logs | Core | NoneType | Errores | Veredicto |
|---|---|---|---|---|---|---|
| 1 | matriz_empleado_alto | 38 | 4 profiling | 0 | 5 | ROJO |
| 2 | matriz_independiente_reportado | 34 | 3 profiling | 0 | 5 | ROJO |

### Sesión 1 — matriz_empleado_alto
- Teléfono: `57377009901`
- Secuencia núcleo: `['cierre_fase_completo', 'cierre_fase_completo', 'turno_7_profiling', 'turno_7_profiling', 'turno_3_profiling', 'turno_1_profiling']`
- captured_counts: `[6, 6, 2, 0]`
- HYBRID BACKSTOP: 0 | failover: 2 | QWEN ROUTE: 0 | DUAL FAILOVER: 0
- Errores NoneType.strip: 0
- **Errores:**
  - esperaba 6 turnos de profiling deepseek, hay 4
  - captured_count no monótono en profiling: [6, 6, 2, 0]
  - falta frontera_turno_7_matriz (gemini)
  - razones no esperadas: ['cierre_fase_completo', 'turno_1_profiling', 'turno_3_profiling', 'turno_7_profiling']
  - failover a Gemini detectado: 2
- **Histograma (38 eventos):**
  | provider | reason | captured | fase | timestamp |
  |---|---|---|---|---|
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:35:57.386824Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:35:36.822788Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:35:24.148644Z |
  | gemini | cierre_fase_completo | 8 | PHASE_3_CREDIT_PROFILING | 2026-08-25T02:35:20.980754Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:35:08.714990Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:34:42.162085Z |
  | gemini | cierre_fase_completo | 8 | PHASE_3_CREDIT_PROFILING | 2026-08-25T02:34:39.724935Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:34:26.604209Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:34:04.565012Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:33:43.853055Z |
  | deepseek | turno_7_profiling | 6 | PHASE_3_CREDIT_PROFILING | 2026-08-25T02:33:19.532560Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:33:01.151038Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:32:38.718416Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:32:18.388687Z |
  | deepseek | turno_7_profiling | 6 | PHASE_3_CREDIT_PROFILING | 2026-08-25T02:31:54.091327Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:31:37.418575Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:30:52.667136Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:30:31.975690Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:29:48.006912Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:29:27.358441Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:28:51.790587Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:28:31.078737Z |
  | deepseek | turno_3_profiling | 2 | PHASE_3_CREDIT_PROFILING | 2026-08-25T02:28:05.343198Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:27:55.378081Z |
  | deepseek | turno_1_profiling | 0 | PHASE_3_CREDIT_PROFILING | 2026-08-25T02:27:18.069640Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:27:04.637902Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:26:41.888243Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:26:21.690929Z |
  | gemini | simulacion_ciega_paso2 | 0 | PHASE_2_HABEAS_DATA | 2026-08-25T02:25:54.998643Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:25:49.227510Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:25:26.478774Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:25:05.584064Z |
  | gemini | simulacion_ciega_paso2 | 0 | PHASE_2_HABEAS_DATA | 2026-08-25T02:24:41.692323Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:24:27.055606Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:24:01.330936Z |
  | gemini | default_conservador | 0 | None | 2026-08-25T02:23:59.151409Z |
  | gemini | default_conservador | 0 | PHASE_1_PROFILING | 2026-08-25T02:23:56.082570Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:23:47.977192Z |

### Sesión 2 — matriz_independiente_reportado
- Teléfono: `57377009902`
- Secuencia núcleo: `['cierre_fase_completo', 'turno_7_profiling', 'turno_3_profiling', 'turno_1_profiling', 'cierre_fase_completo']`
- captured_counts: `[6, 2, 0]`
- HYBRID BACKSTOP: 0 | failover: 2 | QWEN ROUTE: 0 | DUAL FAILOVER: 0
- Errores NoneType.strip: 0
- **Errores:**
  - esperaba 6 turnos de profiling deepseek, hay 3
  - captured_count no monótono en profiling: [6, 2, 0]
  - falta frontera_turno_7_matriz (gemini)
  - razones no esperadas: ['cierre_fase_completo', 'turno_1_profiling', 'turno_3_profiling', 'turno_7_profiling']
  - failover a Gemini detectado: 2
- **Histograma (34 eventos):**
  | provider | reason | captured | fase | timestamp |
  |---|---|---|---|---|
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:47:27.461998Z |
  | gemini | cierre_fase_completo | 8 | PHASE_3_CREDIT_PROFILING | 2026-08-25T02:47:22.083633Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:47:08.027173Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:46:47.819165Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:46:02.810096Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:45:40.612538Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:45:19.677760Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:44:42.808130Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:44:21.983874Z |
  | deepseek | turno_7_profiling | 6 | PHASE_3_CREDIT_PROFILING | 2026-08-25T02:43:51.496087Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:43:37.649265Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:42:55.890356Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:42:33.271272Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:42:12.786823Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:41:28.414123Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:41:05.844740Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:40:45.544121Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:40:07.480995Z |
  | deepseek | turno_3_profiling | 2 | PHASE_3_CREDIT_PROFILING | 2026-08-25T02:39:38.431517Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:39:27.345017Z |
  | deepseek | turno_1_profiling | 0 | PHASE_3_CREDIT_PROFILING | 2026-08-25T02:38:49.088331Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:38:36.443207Z |
  | gemini | simulacion_ciega_paso2 | 0 | PHASE_2_HABEAS_DATA | 2026-08-25T02:38:05.316852Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:37:51.173676Z |
  | gemini | simulacion_ciega_paso2 | 0 | PHASE_2_HABEAS_DATA | 2026-08-25T02:37:27.177265Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:37:15.494847Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:36:19.397251Z |
  | gemini | default_conservador | 0 | None | 2026-08-25T02:36:13.038010Z |
  | gemini | default_conservador | 0 | PHASE_1_PROFILING | 2026-08-25T02:36:10.812359Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:35:57.386824Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:35:36.822788Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:35:24.148644Z |
  | gemini | cierre_fase_completo | 8 | PHASE_3_CREDIT_PROFILING | 2026-08-25T02:35:20.980754Z |
  | deepseek | tarea_faq_contexto | 0 | None | 2026-08-25T02:35:08.714990Z |
