# F4.5 Synthetic Traffic Harness

Harness para ejecutar el protocolo de tráfico sintético + baseline A/B de la ventana F4.5 en el bot beta de Tienda Las Motos.

## Alcance y restricciones

- **Footprint:** únicamente `scripts/f4_5_traffic/` y `.planning/F4.5_MONITORING.md`.
- **C4:** cero edits a `app/core/prompts.py`, `personality.json`, `admin.py`, `config_loader.py`, workflows, `ai_brain.py`, `memory_service.py`.
- **Canal:** inyección por `/webhook/task-processor` del servicio beta; nunca toca el número ni webhook de producción.
- **PII:** corpus 100% ficticio; teléfonos reservados bajo el prefijo `5737700xxxxx`.
- **CRM:** `memory_service.py` hardcodea la colección `prospectos`, por lo que beta escribe en la misma colección que prod. Mitigación: prefijo reservado + etiquetado + purga obligatoria al cierre (`cleanup_synthetic.py`).

## Requisitos

- Python 3.13+ con el entorno del proyecto (`.venv/bin/python`).
- `gcloud` autenticado con ADC y acceso al proyecto `tiendalasmotos`.
- Variables de entorno (o secretos de gcloud):
  - `WEBHOOK_VERIFY_TOKEN` — token del endpoint `/webhook/task-processor`.
  - `WHATSAPP_TOKEN` — token de Meta para subir media (OPCIÓN-A). Si no está en env, el runner intenta cargar el secreto `WHATSAPP_TOKEN`.
  - `BETA_PHONE_NUMBER_ID` — default `1021779847693778` (valor de `corpus.yaml`).
  - `GOOGLE_CLOUD_PROJECT` — default `tiendalasmotos`.
  - `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST` — opcionales para latencias en `analyze_wave.py`.

## Archivos

| Archivo | Propósito |
|---|---|
| `corpus.yaml` | 40 escenarios sintéticos reutilizando fixtures de `scripts/gates_f4/`. |
| `media.py` | Genera PNG 64×64 y WAV ≤2s y los sube a Meta para obtener `media_id` real. |
| `run_wave.py` | Ejecuta una oleada A/B: flip de flag, sonda de ruta, inyección del corpus, manifest. |
| `analyze_wave.py` | Correlaciona logs, Langfuse y docs de prospectos; emite reporte A/B con veredicto. |
| `cleanup_synthetic.py` | Dry-run por defecto; purga recursiva de docs con prefijo `+5737700`. |

## Uso

### 1. Pilot wave (subset de validación)

```bash
export WEBHOOK_VERIFY_TOKEN="tiendalasmotos_secret_123"
export GOOGLE_CLOUD_PROJECT="tiendalasmotos"

.venv/bin/python scripts/f4_5_traffic/run_wave.py \
  --wave 1 \
  --run-id "pilot-$(date +%Y%m%d-%H%M)" \
  --pilot \
  --concurrency 2
```

### 2. Oleada completa (40 escenarios × 2 brazos)

```bash
.venv/bin/python scripts/f4_5_traffic/run_wave.py \
  --wave 1 \
  --run-id "2026-08-20-10-00" \
  --concurrency 6
```

El runner alterna el orden por oleada:
- Oleadas impares: A (Gemini, `qwen_enabled=false`) → B (Qwen, `qwen_enabled=true`).
- Oleadas pares: B → A.

### 3. Analizar una oleada

```bash
.venv/bin/python scripts/f4_5_traffic/analyze_wave.py "2026-08-20-10-00"
```

Genera:
- `results/<run-id>/analysis_report.json`
- `results/<run-id>/analysis_report.md`

### 4. Programar las 4 oleadas en 24h

Cada ~6h ejecutar oleadas 1-4 con `--run-id` único. Al finalizar:

```bash
# Dry-run primero
.venv/bin/python scripts/f4_5_traffic/cleanup_synthetic.py --list

# Ejecutar purga tras verificación del Auditor/owner
.venv/bin/python scripts/f4_5_traffic/cleanup_synthetic.py --execute
```

## Criterio de salida F4.5

- **VERDE:** las 4 oleadas cumplen todos los umbrales 086 (sin relajar) y el drill de rollback <30s está documentado.
- **ROJO:** cualquier umbral ROJO persistente >1h → rollback a `qwen_enabled=false` + STOP + escalación al Auditor.

Umbrales comparados baseline A/B:
- key-set+args verbatim de `calculate_credit_score` por provider.
- `score_resultado` media/p50/p90; alerta si `|Δmedia| > 20` pts.
- Mix cierre ruta R1-R4; alerta si shift >5pp.
- `tool_call_rate` B dentro de ±10% de A.
- p95 latencia B ≤ 1.15× p95 A (Langfuse).
- `DUAL FAILOVER` / escenarios B < 5%.
- MATRIZ divergencia 0 (contenido/orden canónico de las 8 preguntas).
- Operativos: 5xx ≤1%, `CATALOG_VALIDATION_FAIL`/h ≤5, `TOOL-SUPPRESS retry_failed`/h ≤5, exporter errors = 0.

## Notas C5

- **C5-F45-01:** `memory_service.py:82` hardcodea `collection_name="prospectos"`; beta y prod comparten CRM. El aislamiento se hace por prefijo telefónico + purga.
- **C5-F45-02:** durante la ventana, excluir el prefijo `5737700xxxxx` de dashboards de deliverability porque los envíos a números sintéticos generarán acuses `failed` de Meta.
- **C5-F45-03:** media inbound requiere subida real a Meta (OPCIÓN-A). Si el canal beta no tiene cuota, usar `--skip-media` y cubrir con el gate `G0-AUDIO-VISION` ya certificado.
- **C5-F45-04:** cada escenario multi-turno espera el 200 síncrono del `task-processor` y deja 6s de gap entre turnos para evitar agrupación en el `MessageBuffer`.
