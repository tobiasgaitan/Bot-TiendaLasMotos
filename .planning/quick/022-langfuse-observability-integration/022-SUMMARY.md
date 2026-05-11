# Quick Task 022: Langfuse Observability Integration — Summary

**Executed:** 2026-05-11
**Status:** Complete

## What Was Done

Integración completa de Langfuse para observabilidad del ciclo de vida del prospecto en el bot Juan Pablo.

### Decisiones de arquitectura clave:
1. **Guard `LANGFUSE_AVAILABLE`**: El import de Langfuse está protegido por `try/except`. Si las claves no están configuradas, el app arranca normalmente con un no-op decorator y un no-op context manager — ZERO impacto en producción sin claves.
2. **`@observe()` en `pensar_respuesta`**: El decorator captura wall-clock latency total del turno completo. Es el span raíz.
3. **`propagate_attributes` con `userId = phone (E.164)`**: El número de teléfono en formato canónico E.164 se propaga como `userId` a todos los spans hijo. Permite filtrar trazas forenses por prospecto en la consola de Langfuse.
4. **`session_id = f"wa_{phone}"`**: Estable por thread de WhatsApp. Agrupa todos los turnos del mismo prospecto.
5. **Tags `[funnel_phase, "juan_pablo_agent"]`**: Permite filtrar trazas por fase del embudo en Langfuse.
6. **`search_catalog` latency span**: El `time.perf_counter()` existente se enriquece con `_lf.update_current_observation()` reportando `latency_s` y `results_count`.
7. **Token counts en `update_current_generation`**: `prompt_token_count` y `candidates_token_count` se separan del `total_token_count` y se envían a Langfuse con `cost_usd`.

## Files Modified

| File | Action | Description |
|------|--------|-------------|
| `requirements.txt` | Modified | Agregado `langfuse>=2.0.0` bajo sección `# Observability` |
| `app/core/config.py` | Modified | Agregadas 3 vars: `langfuse_public_key`, `langfuse_secret_key`, `langfuse_host` |
| `app/services/ai_brain.py` | Modified | Import guard + `@observe()` + `propagate_attributes` + `search_catalog` span + token reporting |

## Verification

- ✅ `grep langfuse requirements.txt` → L28: `langfuse>=2.0.0`
- ✅ `python3 -c "import ast; ast.parse(...config.py...)"` → AST OK
- ✅ `python3 -c "import ast; ast.parse(...ai_brain.py...)"` → AST OK
- ✅ 3 commits atómicos: `bc82ec5`, `703b94e`, `befe140`

## Environment Variables Required (Cloud Run)

```bash
gcloud run services update bot-tienda-las-motos \
  --set-env-vars="LANGFUSE_PUBLIC_KEY=pk-lf-xxx,LANGFUSE_SECRET_KEY=sk-lf-xxx,LANGFUSE_HOST=https://cloud.langfuse.com"
```

---
*Completed: 2026-05-11*
