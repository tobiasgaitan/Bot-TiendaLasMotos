# Plan 04-01: Rotación T0 + Reescritura Forense Git — Summary

**Executed:** 2026-07-22
**Status:** ✅ Complete
**Commits:** `0926140` → `34c738f` → `7bd97c1` → `cba8657` (rescue) — reescritos como `6b44496` → `53d8adb` → `2f15f6b` → `116e08e`

## What Was Built
- Checklist de rotación T0 (`04-01-ROTATION-CHECK.md`) — **CONFIRMED** por el usuario 2026-07-22 (R1–R6).
- Inventario forense: 3 literales únicos (2 tokens Meta EAATOs… 195/200 chars; 1 webhookSecret 38 chars). Exclusiones verificadas: `EAA_DUMMY_TOKEN_TEST` (allowlist), `.npmrc` `_authToken` (ref `${ENV_VAR}`), `key.json`/`.env` (nunca commiteados).
- Commit de rescate `cba8657`: trabajo Etapa-1 en curso + **purga de whap.json del tip de beta** (contenía webhookSecret vivo).
- Reescritura total con `git filter-repo --replace-text` (2 pasadas: inicial + refresh con 4 commits nuevos) y **force-push de las 6 ramas a origin**.
- Realineación local completa + eliminación de refs contaminados locales (tags v1.0.1/v1.0.2, rama hotfix-infra-k6-124, stash 2026-05-03 archivado y eliminado) + `git gc --prune=now`.
- `secrets.txt` y archivos de extracción destruidos post-push.

## Force-Push Results (verificado vía `git ls-remote origin`)
| Rama | SHA anterior | SHA nuevo |
|------|-------------|-----------|
| beta | 2bd7329 | **116e08e** |
| dev | 5fd6066 | **3929de3** |
| feature-ponytail | 0dbbd47 | **86257fa** |
| fix/pipeline-qa-gate-073 | 6ddec72 | **f21c87c** |
| main | d7b7ebf | **c67ac22** |
| master | 7d50408 | **4598a96** |

Tags: ninguna en remoto (v1.0.1/v1.0.2 eran solo locales → eliminadas, NO publicadas).

## Files Created/Modified
| File | Action | Description |
|------|--------|-------------|
| 04-01-ROTATION-CHECK.md | Created/Updated | Checklist T0 → CONFIRMED |
| evidence/secrets-manifest-REDACTED.md | Created | Manifiesto 3 literales (sin valores) |
| evidence/filter-repo.log | Created | Log filter-repo |
| evidence/post-rewrite-scan.log | Created | Escaneo 0-hits del espejo |
| evidence/stash-archive-2026-05-03.patch | Created | Diff del stash eliminado (3392 líneas, 0 secretos) |

## Verification Results (acceptance criterion #1)
- [x] Espejo: `git grep -E "EAA[A-Za-z0-9_-]{20,}" $(rev-list --all)` → **0 hits** (excl. dummy)
- [x] Local post-gc: mismo escaneo → **0 hits**
- [x] `git log -p --all -- whap.json` → `"webhookSecret": "***REMOVED***"` ×4
- [x] 0 `BEGIN PRIVATE KEY` / `npm_…{36}` / `_authToken=` literal en historial
- [x] Integridad: 1098 commits + 4 nuevos (docs/rescue) preservados; fsck limpio
- [x] Remoto: 6 ramas en SHAs nuevos verificados contra espejo

## Notable Decisions
1. Rotación confirmada por el usuario ANTES del push (compuerta T0 respetada).
2. Tags v1.0.1/v1.0.2 (solo locales) eliminadas, no publicadas — evita contaminar origin con refs a historia vieja.
3. Stash del 2026-05-03 (WIP on main, 11 semanas de antigüedad) archivado como patch y eliminado: era la última ref local que mantenía vivo el grafo contaminado (101 hits residuales → 0).
4. `refs/pull/1-2` de GitHub no son force-pusheables: los SHAs antiguos siguen accesibles vía caché/PRs de GitHub hasta GC del servidor → **acción externa pendiente: ticket a GitHub Support (R7)**.

## Issues Encountered
- zsh `$c:file` → modificador `:w` en loops; resuelto con `${c}:file`.
- BSD grep sin `\s`; extracción migrada a Python `re`.
- Fetch local→espejo rechazado (non-fast-forward post-rewrite); resuelto con `fetch --force`.
- Tags locales arrastradas al espejo por fetch; eliminadas del espejo antes del push.

## Residual Risks (documentados)
- Caché de GitHub (vistas web, PRs #1/#2, SHAs directos) sirve contenido antiguo hasta GC del servidor. Mitigado por: rotación T0 (credenciales muertas) + recomendación R7 (ticket Support).
- Clones/forks previos de terceros conservan la historia vieja (irremediable; mitigado por rotación).

---
*Completed: 2026-07-22 | Wave 04-01 CLOSED — historial Git forense limpio (local + remoto)*
