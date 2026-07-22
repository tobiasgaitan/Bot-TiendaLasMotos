# Bot Tienda Las Motos

## Ejecución de Tests (Pin de Entorno Obligatorio)

La suite exige el entorno virtual del proyecto (`.venv`, Python **3.13** — ver `.python-version` y `requires-python = "==3.13.*"` en `pyproject.toml`):

```bash
.venv/bin/python -m pytest tests/ -q
```

⚠️ **No ejecutar con el intérprete del sistema** (`python3 -m pytest`). El Python del sistema (ej. 3.14 Homebrew) carece de dependencias del venv (`ffmpeg`, entre otras) y produce **falsos negativos** (`ModuleNotFoundError: No module named 'ffmpeg'`) en `test_audio_regression.py`, `test_webhook_sync_block.py` y paridades financieras, sin que exista regresión real del core [BOT-BUILD-MULTIMODAL-CIERRE-196].