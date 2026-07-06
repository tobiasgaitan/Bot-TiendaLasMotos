# Quick Task 129: Restore External Infra Environment Variables and Disable CPU Throttling — Summary

**Executed:** 2026-07-06
**Status:** Complete

## What Was Done
1. **IAM and Perms Verification**: Confirmed active service account `467812260261-compute@developer.gserviceaccount.com` correctly holds the required `roles/datastore.user` role.
2. **Local Topology Scan**: Audited python Firestore Client/AsyncClient interactions using AST (Graphify). Analyzed the uvicorn startup blocking database synchronization behavior.
3. **CPU Throttling Mitigation**: Identified that Cloud Run default CPU throttling deallocates CPU when no active user requests are processed. When combined with lifespan startup yielding immediately, it throttled uvicorn's background startup sync task causing Firestore gRPC streams to timeout.
4. **Environment Restoration & Configuration**: Restored missing environment variables (`WHATSAPP_TOKEN`, `PHONE_NUMBER_ID`, `WEBHOOK_VERIFY_TOKEN`, `ADMIN_API_KEY`, `WHATSAPP_APP_SECRET`, `FIRESTORE_COLLECTION`) and set `MIN_CATALOG_ITEMS=40` and `DB_TIMEOUT=15`.
5. **Disabled CPU Throttling**: Configured the Cloud Run service to disable CPU throttling (`--no-cpu-throttling`).
6. **Startup Log Enforcement**: Surgically modified `app/main.py` to output the exact verification string `[STARTUP-SUCCESS] Catálogo hidratado sin timeouts.` when the catalog hydrates successfully without timeouts.

## Files Modified
| File | Action | Description |
|------|--------|-------------|
| [app/main.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/main.py) | Modified | Updated startup success log output to print the expected verification trace. |

## Verification
- Successfully deployed revision `bot-tiendalasmotos-beta-00250-djp` serving 100% of traffic.
- Verified logs and found the exact success trace:
  `2026-07-06 23:10:38,034 - app.main - INFO - ✅ [STARTUP-SUCCESS] Catálogo hidratado sin timeouts.`

---
*Completed: 2026-07-06*
