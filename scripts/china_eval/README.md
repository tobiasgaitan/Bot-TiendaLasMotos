# BOT-BUILD-CHINA-EVAL-090

Suite de evaluación empírica P1-P7 para DeepSeek V4 Flash 0731 y GLM-5.2 como
posibles reemplazos del loop agéntico de `juan_pablo_personality`.

## Estructura

```
scripts/china_eval/
├── common/          # clients, retry, logging, report
├── fixtures/        # declaraciones de tools
├── logs/            # logs ZSF forenses
├── protocol_p1.py   # search_catalog single-turn
├── protocol_p2.py   # calculate_credit_score single-turn
├── protocol_p3.py   # multi-turn MATRIZ 8 turnos
├── protocol_p4.py   # PASO 1 output format
├── protocol_p5.py   # audio transcription (pipeline externo)
├── protocol_p6.py   # image analysis (pipeline externo)
├── protocol_p7.py   # GLM-5.2 replay P1-P4
├── run_all.py       # orquestador
└── README.md
```

## Variables de entorno

### Activas (BOT-BUILD-CHINA-EVAL-090-D1)

| Variable | Requerida | Default | Descripción |
|---|---|---|---|
| `OPENROUTER_API_KEY` | Sí | — | Bearer token para OpenRouter |
| `CHINA_EVAL_BASE_URL` | No | `https://openrouter.ai/api/v1` | Base URL del gateway OpenRouter-compatible |
| `DEEPSEEK_MODEL` | No | `deepseek/deepseek-v4-flash-0731` | Slug DeepSeek V4 Flash 0731 (build re-entrenado) |
| `GLM52_MODEL` | No | `z-ai/glm-5.2` | Slug GLM-5.2 vía OpenRouter |

```bash
export OPENROUTER_API_KEY="sk-or-v1-..."
export CHINA_EVAL_BASE_URL="https://openrouter.ai/api/v1"  # opcional
export DEEPSEEK_MODEL="deepseek/deepseek-v4-flash-0731"     # opcional
export GLM52_MODEL="z-ai/glm-5.2"                           # opcional
```

### Diagnóstico de NBSP / zero-width en la API key

Si ves `UnicodeEncodeError: 'ascii' codec can't encode character '\xa0'`, la key puede contener un NBSP invisible por copiar/pegar desde la web:

```bash
printf '%s' "$OPENROUTER_API_KEY" | od -c | grep -n '302 240' ; echo "len=${#OPENROUTER_API_KEY}"
```

`302 240` octal = bytes UTF-8 del NBSP. Si hay match, usa el re-export limpio:

```bash
export OPENROUTER_API_KEY=$(printf '%s' "$OPENROUTER_API_KEY" | LC_ALL=C tr -d '\302\240\342\200\213' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
```

### Deprecadas/eliminadas

- `DEEPSEEK_API_KEY` — reemplazada por `OPENROUTER_API_KEY`
- `GLM52_API_KEY` — reemplazada por `OPENROUTER_API_KEY`
- `GLM52_BASE_URL` — reemplazada por `CHINA_EVAL_BASE_URL`

**Guard:** `DEEPSEEK_MODEL=deepseek/deepseek-v4-flash` (build 0423 pre-reentrenamiento) genera `ValueError`.

## Ejecución

```bash
python scripts/china_eval/run_all.py && cat china_eval_report.json
```

También se puede ejecutar un protocolo individual por proveedor:

```bash
python scripts/china_eval/protocol_p1.py deepseek
python scripts/china_eval/protocol_p2.py glm52
```

## Criterios GO/NO-GO

| Prueba | PASS |
|---|---|
| P1 | ≥ 4/5 variantes invocan `search_catalog` correctamente |
| P2 | ≥ 4/5 variantes invocan `calculate_credit_score` correctamente |
| P3 | tool-call rate ≥ 0.4 en 8 turnos MATRIZ |
| P4 | ≥ 2/3 variantes cumplen formato PASO 1 |
| P5 | Pipeline externo; GO/NO-GO independiente |
| P6 | Pipeline externo; GO/NO-GO independiente |
| P7 | Mismos criterios P1-P4 aplicados a GLM-5.2 |

## Restricciones

- Cero toques a `app/core/ai_brain.py`, `app/core/prompts.py`, `app/core/personality.json`.
- P5/P6 son pipelines externos; su resultado no bloquea P1-P4+P7.
- Logs ZSF en `scripts/china_eval/logs/china_eval.log`.
