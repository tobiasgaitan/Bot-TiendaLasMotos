# Quick Task 197: INFRA Recovery — Config Pool Consolidation — Summary

**Executed:** 2026-07-17
**Status:** Complete ✅
**Commit:** b444282

## Autopsia del Falso Positivo (Mandatoria — BOT-INFRA-RECOVERY-PARAM-197)

**Causa raíz del falso positivo en la suite:**
El `tests/conftest.py` fixture `mock_env_vars` (autouse=True) solo inyectaba
`GOOGLE_APPLICATION_CREDENTIALS`, `TEST_MODE` y `MIN_CATALOG_ITEMS`. Las 4 credenciales
críticas validadas por `Settings()._validate_config()` (WHATSAPP_TOKEN, PHONE_NUMBER_ID,
ADMIN_API_KEY, WEBHOOK_VERIFY_TOKEN) nunca fueron mockeadas.

Los tests pasaban en CI/CD porque importaban `settings` como singleton ya inicializado
desde el `.env` local. Ningún test instanciaba `Settings()` directamente con vars ausentes.
En Cloud Run (sin .env), el `RuntimeError` era inevitable tras cualquier `--set-env-vars`
manual que purgara variables no declaradas. La suite nunca detectó este escenario.

## What Was Done

1. **deploy.yml**: Añadidas `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`
   al pool de `--update-env-vars`. El workflow ya contenía las 4 credenciales críticas.
2. **deploy-beta.yml**: Sincronizado el mismo pool completo de 9 variables.
3. **tests/conftest.py**: Inyectadas las 4 credenciales críticas + WHATSAPP_APP_SECRET
   en el fixture `mock_env_vars` autouse con tokens de prueba seguros.
4. **tests/test_config_startup.py**: Creado con 5 tests anti-falso-positivo que cubren:
   - RuntimeError con WHATSAPP_TOKEN ausente
   - RuntimeError con PHONE_NUMBER_ID ausente
   - Arranque correcto con pool completo
   - Strip de whitespace no causa falsa ausencia
   - Valores inseguros por defecto son rechazados

## Files Modified

| File | Action | Description |
|------|--------|-------------|
| `.github/workflows/deploy.yml` | Modified | Pool completo: LANGFUSE_* añadidas |
| `.github/workflows/deploy-beta.yml` | Modified | Pool completo sincronizado |
| `tests/conftest.py` | Modified | 4 creds críticas + WHATSAPP_APP_SECRET en mock_env_vars |
| `tests/test_config_startup.py` | Created | 5 tests de arranque anti-falso-positivo |
| `.planning/quick/197-infra-recovery-param-197/197-PLAN.md` | Created | Plan GSD |
| `.planning/STATE.md` | Modified | v10.45.16, hito 197 |

## Verification

```
uv run pytest tests/test_config_startup.py -v
5 passed in 0.02s  ✅
```

Todos los archivos verificados físicamente con grep antes del commit.

---
*Completed: 2026-07-17*
