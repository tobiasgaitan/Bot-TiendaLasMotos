# Quick Task 075: Hotfix CI k6 GPG Key Installation — Summary

**Executed:** 2026-06-27
**Status:** Complete

## What Was Done
Reemplazado el paso `Install Grafana k6` en `qa-pipeline.yml` que utilizaba `gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys` con lógica de fallback bash `||`. Esta lógica causaba:
- `curl: 23` (error de permisos de escritura al dearmor)
- Colapsos intermitentes del keyserver HKP en runners efímeros de GitHub Actions

Se reemplazó con un pipeline atómico de 3 líneas:
1. `curl -sL https://dl.k6.io/key.gpg | sudo gpg --no-default-keyring --keyring ... --import`
2. `echo "deb [signed-by=...] ..." | sudo tee /etc/apt/sources.list.d/k6.list`
3. `sudo apt-get update && sudo apt-get install -y k6`

Se eliminaron: `dirmngr`, `mkdir /root/.gnupg`, `rm -f`, todo el bloque `||` de fallback.

## Files Modified
| File | Action | Description |
|------|--------|-------------|
| .github/workflows/qa-pipeline.yml | Modified | Reemplazo de 11 líneas GPG keyserver por 3 líneas de pipeline atómico seguro |

## Verification
- `cat -n` confirmó que el archivo contiene exclusivamente el pipeline atómico sin keyserver ni fallback.
- Scaffold integrity: PASS ✅
- Coherence Score: **1.000** (167 passed, 0 failed, 2 skipped)
- Push exitoso a `fix/pipeline-qa-gate-073` → commit `8de00f4`

---
*Completed: 2026-06-27*
