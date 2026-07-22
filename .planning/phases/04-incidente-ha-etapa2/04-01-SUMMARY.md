# Plan 04-01: Rotación T0 + Reescritura Forense Git — Summary

**Executed:** 2026-07-22
**Status:** ⏸️ Partial — PAUSADO en compuerta T0 (rotación de credenciales pendiente por el usuario)
**Commits:** 2 (`0926140` docs plans fase, `34c738f` checklist + evidencia)

## What Was Built
- Checklist de rotación T0 (`04-01-ROTATION-CHECK.md`) — estado PENDING, bloqueante para el push.
- Inventario forense completo: 3 literales únicos (2 tokens Meta EAATOs… 195/200 chars; 1 webhookSecret `secr…` 38 chars). Verificados NO-credenciales: `EAA_DUMMY_TOKEN_TEST` (allowlist), `.npmrc` `_authToken` (ref `${ENV_VAR}`), `key.json`/`.env` (nunca commiteados).
- Clon espejo de origin (6 ramas, 1098 commits, refs/pull/1-2 de GitHub PRs) + reescritura con `git filter-repo --replace-text` (0.31s, repack OK).
- Verificación post-rewrite en espejo: **0 hits de credenciales** en `rev-list --all`; whap.json muestra `***REMOVED***` (3 ocurrencias); 0 `BEGIN PRIVATE KEY` / `npm_` / `_authToken` literal; fsck limpio; conteo de commits intacto.

## Files Created/Modified
| File | Action | Description |
|------|--------|-------------|
| 04-01-ROTATION-CHECK.md | Created | Checklist T0 (R1-R9), estado PENDING |
| evidence/secrets-manifest-REDACTED.md | Created | Manifiesto de 3 literales (prefijos/longitudes, sin valores) |
| evidence/filter-repo.log | Created | Log de ejecución filter-repo |
| evidence/post-rewrite-scan.log | Created | Escaneo forense post-rewrite (0 hits) |

## Verification Results
- [x] `git grep -E "EAA[A-Za-z0-9_-]{20,}" $(rev-list --all)` en espejo → **0** (excl. dummy allowlisted)
- [x] `git log -p --all -- whap.json` → `"webhookSecret": "***REMOVED***"` ×3
- [x] Integridad: 1098 commits preservados, fsck sin errores
- [ ] Force-push a origin — **BLOQUEADO** hasta confirmación de rotación (R6)

## Estado de artefactos sensibles
- `secrets.txt` (valores reales): workspace temporal `$TMPDIR/opencode/incident-ha-201/`, chmod 600. Se destruye tras el push exitoso. NUNCA commiteado.

## Decisiones del usuario (2026-07-22)
1. Rotación: **AÚN NO** → pausa en compuerta T0.
2. Salvaguarda trabajo Etapa-1 sin commitear: **commit de rescate en beta** antes del push.
3. Refs locales contaminados (tags v1.0.1/v1.0.2, rama hotfix-infra-k6-124): **eliminar ambos** en la realineación.

## Procedimiento de reanudación (cuando el usuario confirme ROTACIÓN)
1. Commit de rescate en beta con el trabajo Etapa-1 en curso.
2. Refrescar espejo (fetch + re-ejecutar filter-repo si hubo commits nuevos) — 0.3s.
3. `git -C <espejo> push --force --all https://github.com/tobiasgaitan/Bot-TiendaLasMotos.git`.
4. Realineación local: fetch + rebase/reset a `origin/beta`; eliminar tags v1.0.1/v1.0.2 y rama hotfix-infra-k6-124; `git gc --prune=now`.
5. Destruir `secrets.txt`; verificación remota final (`git ls-remote`); actualizar este SUMMARY a Complete.
6. Recordatorio documentado: ticket a GitHub Support para purga de cachés (R7) — los SHAs antiguos y refs/pull/* siguen sirviendo contenido antiguo hasta GC del servidor.

## Issues Encountered
- zsh interpreta `$c:whap.json` como modificador `:w` en loops → resuelto con `${c}:whap.json`.
- BSD grep de macOS no soporta `\s` → extracción migrada a Python `re`.

---
*Executed: 2026-07-22 | Pausado en compuerta T0 — awaiting user rotation confirmation*
