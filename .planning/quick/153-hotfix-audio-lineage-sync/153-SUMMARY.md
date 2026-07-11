# Quick Task 153: Hotfix Audio Lineage Sync — Summary

**Ejecutado:** 2026-07-10
**Status:** Complete
**Ticket:** BOT-ROUTER-AUDIO-LINEAGE-123

## What Was Done

### Diagnóstico Forense

La autopsia física de `app/routers/whatsapp.py` (L1243–1292) reveló que el bloque `elif msg_type == "audio"` verificaba el flag `human_help_requested` **ANTES** de ejecutar `generate_and_update_summary` (el LINEAR BLOCKING).

**Causa raíz confirmada:** Un payload de audio llegado inmediatamente después de un `/reset` podía encontrar un documento de Firestore recién recreado con un flag `human_help_requested=True` residual de la sesión anterior. Al verificar este flag en el pre-fetch (pre-sync), el bot se silenciaba con datos obsoletos, **sin ejecutar el LINEAR BLOCKING ni re-hidratar el contexto limpio de Firestore**.

El bloque `msg_type == "text"` (L1023-L1061) no sufría este problema porque el check de `human_help_requested` estaba en la sección §2 (L1000-1002), **después** del refresh post-session-creation (L996).

### Cambio Quirúrgico (TASK-1)

En `app/routers/whatsapp.py`, bloque `elif msg_type == "audio"`:

- **Eliminado:** Check `human_help_requested` en línea pre-transcripción (pre-sync).
- **Añadido:** Check `human_help_requested` DESPUÉS del `generate_and_update_summary` + re-fetch autoritativo (post-sync), espejando el patrón del bloque `text`.
- **Añadidos:** Comentarios de arquitectura JSDoc-style explicando el WHY (mandato de negocio/seguridad).

### Test de Caracterización (TASK-2)

Añadido `test_audio_lineage_post_reset_no_desertion` en `tests/test_audio_regression.py`:
- Simula `human_help_requested=True` en el pre-fetch (dato residual post-reset).
- Simula `human_help_requested=False` en el re-fetch post-sync (dato fresco Firestore).
- Afirma rígidamente que `pensar_respuesta` ES invocado (no hubo silenciamiento falso).
- Afirma que `generate_and_update_summary` fue ejecutado exactamente una vez.
- Prohíbe que `set_human_help_status(True)` sea invocado (no hay falsa deserción).

## Files Modified

| File | Action | Description |
|------|--------|-------------|
| `app/routers/whatsapp.py` | Modified | Reubicar `human_help_requested` check post-LINEAR-BLOCKING en bloque audio |
| `tests/test_audio_regression.py` | Modified | Añadir test de caracterización `test_audio_lineage_post_reset_no_desertion` |

## Verification

```
npx agent-cli eval

━━━ EVAL REPORT ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Tests passed : 233
  Tests failed : 0
  Total        : 233
  Score        : 1.000 (threshold: 0.9)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ SCORE 1.000 ≥ 0.9 — DEPLOY AUTHORIZED ✅
```

Commit: `5d4ca75`

---
*Completed: 2026-07-10*
