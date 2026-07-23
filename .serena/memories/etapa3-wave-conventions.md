# Etapa 3 — Convenciones de Waves (God Node whatsapp.py)

Estado al 2026-07-22: waves 05-01…05-06 certificadas. ETAPA 3 (RF-5) CERRADA. Suite: 431 tests + 2 subtests, Coherence 1.000. RF-5=Done. Siguiente: despliegue beta (F5).

## Wave 05-06 — Latencia forense y cierre (BOT-BUILD-ETAPA3-WAVE06-LATENCY-CLOSE-001)
`tests/test_latency_forensics.py` (LAT-1 Meta≥10s vía httpx.AsyncClient.send compuertado con asyncio.Event — send_text usa client.post que delega en send; LAT-2 timeout Firestore 10s>db_timeout=5 (default real=5) — _firestore_io ELEVA TimeoutError (sancionado por test_bot_bug_044, NO retorna snapshot); LAT-3 cerebro side_effect → JUDGE_CRITICAL_ERROR → fallback). HALLAZGO: rama JUDGE_CRITICAL_ERROR ordena send≺save(model) del fallback (asimetría vigente vs rama rechazo Juez save≺send de ORDER-FALLBACK — pineada, NO normalizar sin Auditor). Auditoría: 2 except:pass remediados con logger (whatsapp.py HANDOFF notification_service, memory_service.py L562 Langfuse).

## Wave 05-05 — Fragmentación text/reaction + egreso consolidado (BOT-BUILD-ETAPA3-WAVE05-FRAGMENT-TEXT-EGRESS-001)
`_pipeline_reaction_debounce` (devuelve cuerpo agregado; None=stop), `_pipeline_text_cognitive` (devuelve `(response_text, prospect_data)`; None=fallback Juez/error), `_pipeline_egress` (consolida HANDOFF+PHASE_GATE y DELEGA a `_process_and_send_egress_message` con firma exacta — CH-5 prohíbe reemplazarlo). impl: **231 code-lines (<300)**, switch lineal puro. Pipelines del God Node: reaction L1714, media L1066, audio L1496, text L1778, egress L2068. Pins: test_pipeline_{reaction,text_cognitive,egress}_integrity.py (5+5+5).

## Wave 05-04 — Fragmentación media+audio (BOT-BUILD-ETAPA3-WAVE04-FRAGMENT-MEDIA-AUDIO-001)
`_pipeline_media_vision` y `_pipeline_audio` extraídos como funciones módulo (sprout, cuerpo VERBATIM vía cirugía programática con aserciones de frontera — no editar a mano 570 líneas). `_pipeline_audio` devuelve `(response_text, prospect_data)`: None=salida temprana (human-help/fallback). Firmas del ticket menos `self` (módulo procedural; una clase rompería el namespace plano de patch targets). Costuras meta_sender/db_client aceptadas como RESERVADAS donde el cuerpo no las consume. impl: 633 span / 433 code-lines (<500 bajo métrica de código efectivo — el <500 físico es imposible: rama TEXT 246 líneas sigue inline hasta 05-05). Pins: test_pipeline_media_vision_integrity.py (MVI-1..5), test_pipeline_audio_integrity.py (AI-1..5).

## Wave 05-03 — Costuras DI (BOT-BUILD-ETAPA3-WAVE03-DI-SEAMS-001)
`_handle_message_background_impl` acepta 4 kwargs keyword-only (default None) con resolución runtime:
`catalog or catalog_service`, `vision_factory or VisionService`, `db_client or db`,
`meta_sender or whatsapp_service` (junto al import diferido READ-FIRST).
`_send_whatsapp_message`/`_send_whatsapp_image` aceptan `meta_sender=None`; `resolve_query_aliases(query, catalog=None)`.
Pin: `tests/test_di_seams_integrity.py` (DI-1..DI-8). Autopsia: `.planning/phases/05-etapa3-concurrencia/PYTEST-AUTOPSY-WAVE03.md`.

## Reglas duras para waves 05-04+ (extracción RF-5)
- NUNCA `default=global` en firmas (def-time rompe los 25 patch targets; ver `grep -rEon "patch\('app.routers.whatsapp..." tests/`).
- NUNCA añadir kwargs en call-sites hacia `_send_whatsapp_message`/`_send_whatsapp_image`: hay 5 pins `assert_called_with(phone, text, phone_number_id=…)` exactos (test_identity_legal_gate ×4, test_zero_silent_failures ×1).
- Tests que alcancen el guard BOT-174: configurar `ms.get_or_create_prospect = AsyncMock(...)` explícito (contaminante: test_pcc_ficha_tecnica.py expulsa unittest.mock de sys.modules).
- `test_zero_fire_and_forget.py` escanea AST: cero `asyncio.create_task` y `add_task` solo en los 3 sitios sancionados.
- Verificación de cierre: `pytest tests/ -q`, `pytest tests/ -q -W error::RuntimeWarning`, `npx agent-cli eval` (umbral 0.95), autopsia en `.planning/phases/05-etapa3-concurrencia/`.
