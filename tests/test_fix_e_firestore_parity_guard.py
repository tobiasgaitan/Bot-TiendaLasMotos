"""
Guard continuo FIX-E — [BOT-PLAN-HARDENING-EGRESS-FUNNEL-001] (Fase 5).

Test de INTEGRACIÓN (credenciales GCP reales) con AISLAMIENTO DE PROCESO:
invoca el canal único certificado `scripts/sync_full_prompt.py --check` en un
intérprete limpio (subprocess), que ejecuta el read-back forense sobre el
documento productivo `configuracion/juan_pablo_personality.system_instruction`
con la triple aserción:
  (i)   paridad byte-exacta remoto == SSOT local,
  (ii)  0 ocurrencias de "Crediorbe"/"CrediOrbe" en el remoto,
  (iii) presencia de "Brilla de Gases" y "nuestro sistema".

WHY subprocess: la suite comparte un intérprete donde otros tests envenenan
`sys.modules`/variables de entorno (fixtures fake de Firestore/keys). Un guard
credentialed debe ejecutarse en un proceso aislado para que su veredicto sobre
producción sea fiel y determinista.

SKIP automático cuando el subprocess no logra leer el remoto (sin credenciales
o sin conectividad): el veredicto solo se exige cuando la lectura forense ocurre.
"""

import os
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SYNC_SCRIPT = ROOT / "scripts" / "sync_full_prompt.py"


@pytest.mark.integration
def test_firestore_personality_matches_ssot_forensic_triple_assertion():
    env = dict(os.environ)
    candidate = ROOT / "key.json"
    if candidate.exists():
        # Convención del repo (scripts/normalize_imagen_url.py): key.json local
        # como credencial de servicio para el canal forense.
        env["GOOGLE_APPLICATION_CREDENTIALS"] = str(candidate)

    proc = subprocess.run(
        [sys.executable, str(SYNC_SCRIPT), "--check"],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(ROOT),
        env=env,
    )
    output = proc.stdout + proc.stderr

    if "PRE-READ remoto" not in output:
        pytest.skip(f"Sin credenciales/conectividad GCP para el guard continuo FIX-E: {output[-300:]}")

    assert "parity_byte_exact" in output, f"Salida inesperada del canal forense:\n{output[-800:]}"
    assert proc.returncode == 0, (
        "DERIVA Firestore o falla de la triple aserción post-sync "
        "(configuracion/juan_pablo_personality). "
        "Re-sincroniza con: python3 scripts/sync_full_prompt.py\n"
        f"Salida del canal:\n{output[-800:]}"
    )
    # Pin explícito de la triple aserción en la salida del canal.
    assert "✅ parity_byte_exact" in output
    assert "✅ crediorbe_eradicated_remote" in output
    assert "✅ brilla_and_nuestro_sistema_present_remote" in output
