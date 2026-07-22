#!/usr/bin/env bash
# [BOT-BUILD-SECURITY-202] Hook pre-push — Barrera anti-filtración de secretos (Fase 5)
#
# INSTALACIÓN (una sola vez por clon):
#   cp scripts/gitleaks-pre-push.sh .git/hooks/pre-push && chmod +x .git/hooks/pre-push
#
# COMPORTAMIENTO:
#   Ejecuta gitleaks sobre los commits a punto de publicarse (rango del push).
#   Si detecta una credencial con formato real (Meta EAA..., npm PAT, GitHub PAT,
#   reglas default de gitleaks), ABORTA el push con log forense explícito.
#
# REQUISITO: binario `gitleaks` en PATH (brew install gitleaks / https://github.com/gitleaks/gitleaks).
# BYPASS DE EMERGENCIA (queda registrado en el log del hook): `git push --no-verify`.

set -euo pipefail

if ! command -v gitleaks >/dev/null 2>&1; then
  echo "❌ FORENSIC [pre-push]: gitleaks no está en PATH. Instálalo (brew install gitleaks) o usa --no-verify bajo tu responsabilidad." >&2
  exit 1
fi

remote_name="$1"
z40="0000000000000000000000000000000000000000"
any_range=0

# Lee refs desde stdin (formato del protocolo pre-push):
# <local ref> <local sha> <remote ref> <remote sha>
while read -r local_ref local_sha remote_ref remote_sha; do
  # Ramas/tags borradas: nada que escanear.
  if [ "$local_sha" = "$z40" ]; then
    continue
  fi
  if [ "$remote_sha" = "$z40" ]; then
    range="$local_sha"          # ref nuevo: escanear todo lo alcanzable
  else
    range="${remote_sha}..${local_sha}"
  fi
  any_range=1
  echo "🔍 FORENSIC [pre-push]: gitleaks escaneando ${range} (remoto: ${remote_name})" >&2
  if ! gitleaks git --log-opts="$range" --config .gitleaks.toml --redact --verbose .; then
    echo "❌ FORENSIC [pre-push]: gitleaks detectó material con formato de secreto en ${local_ref}." >&2
    echo "   Push ABORTADO. Incidente H-A: prohibido publicar credenciales con formato real." >&2
    echo "   Si es un falso positivo documentado, añade allowlist en .gitleaks.toml con ticket." >&2
    exit 1
  fi
done

if [ "$any_range" -eq 0 ]; then
  echo "ℹ️  FORENSIC [pre-push]: sin commits nuevos que escanear." >&2
fi

echo "✅ FORENSIC [pre-push]: gitleaks limpio — push autorizado." >&2
exit 0
