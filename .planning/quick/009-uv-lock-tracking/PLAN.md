# Quick Task: BOT-INFRA-780-LOCK — Tracking uv.lock

## Objetivo
Incluir el archivo `uv.lock` en el seguimiento de Git para asegurar la paridad de dependencias entre los entornos de desarrollo, beta y producción.

## Verificación Inicial
- [x] Archivo `uv.lock` existe físicamente.
- [x] `uv.lock` aparece como "untracked" en `git status`.
- [x] Scaffold integrity check PASSED.

## Plan de Ejecución Atómica
1. **Fase de Registro**:
   - `git add uv.lock`
2. **Fase de Commit**:
   - `git commit -m 'chore(infra): track uv.lock for environment parity'`
3. **Fase de Certificación**:
   - `node ./bin/agent-cli.js eval` (o `npx @tobiasgaitan/agent-cli eval`) para obtener score 1.0.

## Guardrails
- No se deben modificar otros archivos.
- El score de coherencia debe ser exactamente 1.0.
