# Manifiesto REDACTADO de secretos extraídos (secrets.txt)

**Fecha:** 2026-07-22 · **Método:** `git grep -h -o -E` sobre `rev-list --all` + extracción regex de `whap.json` (2b200b1, 8b75d54) · **Total literales:** 3

> ⚠️ Los valores reales NUNCA se commitean. El archivo `secrets.txt` vive únicamente en el workspace temporal del operador (chmod 600) y se destruye tras el push.

| # | Tipo | Prefijo (4-6) | Longitud | Origen histórico | Estado post-rewrite |
|---|------|--------------|----------|------------------|---------------------|
| 1 | Meta Graph API token | `EAAT…` | 195 | `tests/test_startup_lock.py` (era v10.45.3x) | `***REMOVED***` ✓ |
| 2 | Meta Graph API token | `EAAT…` | 200 | `.github/workflows/qa-pipeline.yml` (1d681aa) | `***REMOVED***` ✓ |
| 3 | webhookSecret whap | `secr…` | 38 | `whap.json` (2b200b1, 8b75d54) | `***REMOVED***` ✓ |

**Exclusiones verificadas (no-credenciales):** `EAA_DUMMY_TOKEN_TEST` (fixture sintético allowlisted en `.gitleaks.toml`, sufijo 17 chars — preservado), `.npmrc` `_authToken` (referencia `${ENV_VAR}`, no literal), `key.json`/`.env` (nunca commiteados).
