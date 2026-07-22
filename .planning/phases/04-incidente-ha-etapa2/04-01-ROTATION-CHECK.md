# 04-01 · T0 — Checklist de Rotación de Credenciales (BLOQUEANTE)

**Incidente:** H-A — Token real de Meta publicado en repo público + webhookSecret de whap.json en historial Git.
**Estado:** ⏳ PENDING — NINGÚN force-push se ejecuta hasta que TODAS las casillas estén confirmadas por el usuario.

> Reescribir el historial sin rotar las credenciales es COSMÉTICO: cualquier actor que haya clonado/visitado el repo público posee los secretos. La rotación es la única remediación real; la reescritura es higiene forense.

## Credenciales comprometidas (evidencia forense 2026-07-22)

| # | Credencial | Ubicación histórica | Prefijo (6) | Longitud |
|---|-----------|--------------------|-------------|----------|
| 1 | Meta Graph API / WhatsApp Business token | `.github/workflows/qa-pipeline.yml` (1d681aa), `tests/test_startup_lock.py` (era v10.45.3x) | `EAATOs` | 195–200 |
| 2 | `webhookSecret` de whap | `whap.json` (2b200b1, 8b75d54) | (ver manifiesto redactado) | 38 |

## Pasos de rotación

- [ ] **R1.** Meta for Business / WhatsApp Business Manager: **revocar** el token comprometido (EAATOs…) y emitir uno nuevo (System User → WhatsApp → Generate token, permisos `whatsapp_business_messaging` + `whatsapp_business_management`).
- [ ] **R2.** Actualizar el nuevo token en GCP Secret Manager (secreto `WHATSAPP_TOKEN`) y verificar que el deploy de Cloud Run lo consume (`deploy.yml` usa `--set-secrets`).
- [ ] **R3.** Actualizar `WHATSAPP_TOKEN` en GitHub → Settings → Secrets and variables → Actions (si existe como secret de repo para los workflows).
- [ ] **R4.** Rotar `webhookSecret` de whap: generar nuevo valor (≥32 chars aleatorios), actualizar en el entorno donde whap.json se materializa (NO commitear el archivo — está gitignored vía `*.json`).
- [ ] **R5.** Smoke test post-rotación: webhook Meta → bot responde en ambiente beta (firma HMAC válida, HTTP 200).
- [ ] **R6.** Confirmar aquí la rotación: responder "ROTACIÓN CONFIRMADA" para desbloquear el force-push.

## Acciones posteriores recomendadas (fuera del repo)

- [ ] **R7.** Ticket a GitHub Support → "Sensitive Data Removal": purgar cachés de commits antiguos (los SHAs pre-rewrite siguen accesibles por URL directa hasta GC del servidor).
- [ ] **R8.** Auditar logs de Meta/WhatsApp por uso anómalo del token comprometido entre 2026-06-21 (1d681aa) y la fecha de revocación.
- [ ] **R9.** Revisar forks/clones públicos del repo (GitHub → Insights → Forks / Traffic).

---
*Creado: 2026-07-22 · BOT-BUILD-INCIDENT-HA-201 · La ejecución automatizada continúa hasta pre-push y ESPERA la confirmación R6.*
