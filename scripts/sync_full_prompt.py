"""
CANAL ÚNICO DE SINCRONIZACIÓN DEL PROMPT — [BOT-PLAN-HARDENING-EGRESS-FUNNEL-001 / FIX-E]
========================================================================================
Prelación SSOT (certificada): app/core/prompts.py ≡ app/core/personality.json
→ Firestore `configuracion/juan_pablo_personality.system_instruction`.

Este script es el ÚNICO canal autorizado para sincronizar el prompt completo.
`scripts/patch_prompt.py` y `scripts/sync_production_v2.py` quedan declarados
LEGACY (parches puntuales históricos, no prompt completo).

Protocolo de actualización dual con re-sync forense:
  PRE-WRITE  (repo):    paridad prompts.py == personality.json; 0 "Crediorbe";
                        presencia "Brilla de Gases" / "nuestro sistema".
  WRITE     (Firestore): update del campo system_instruction desde el SSOT.
  READ-BACK (forense):  triple aserción sobre el documento remoto:
                        (i) paridad byte-exacta remoto == local,
                        (ii) 0 ocurrencias "Crediorbe"/"CrediOrbe" en remoto,
                        (iii) presencia "Brilla de Gases" y "nuestro sistema".
  EVIDENCIA:            JSON archivado en scripts/evidence/ con timestamp y hash.

Uso:
  python3 scripts/sync_full_prompt.py            # sync + verificación + evidencia
  python3 scripts/sync_full_prompt.py --check    # SOLO lectura: reporta deriva (no escribe)
"""

import hashlib
import json
import os
import sys
from datetime import datetime, timezone

sys.path.append(os.getcwd())

from google.cloud import firestore
from app.core.prompts import JUAN_PABLO_SYSTEM_INSTRUCTION

PROJECT_ID = "tiendalasmotos"
COLLECTION = "configuracion"
DOCUMENT = "juan_pablo_personality"
FIELD = "system_instruction"
EVIDENCE_DIR = os.path.join("scripts", "evidence")

FORBIDDEN = ("Crediorbe", "CrediOrbe", "crediorbe")
REQUIRED = ("Brilla de Gases", "nuestro sistema")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def assert_repo_ssot() -> None:
    """PRE-WRITE gate: el SSOT local debe estar erradicado y en paridad dual."""
    personality_path = os.path.join("app", "core", "personality.json")
    with open(personality_path, encoding="utf-8") as fh:
        personality_si = json.load(fh)[FIELD]

    assert personality_si == JUAN_PABLO_SYSTEM_INSTRUCTION, (
        "PRE-WRITE FALLA: prompts.py y personality.json divergen. "
        "La paridad dual del SSOT es precondición del sync."
    )
    for bad in FORBIDDEN:
        assert bad not in JUAN_PABLO_SYSTEM_INSTRUCTION, f"PRE-WRITE FALLA: '{bad}' presente en el SSOT local."
    for req in REQUIRED:
        assert req in JUAN_PABLO_SYSTEM_INSTRUCTION, f"PRE-WRITE FALLA: '{req}' ausente del SSOT local."
    print("✅ PRE-WRITE: paridad prompts.py ≡ personality.json; 0 'Crediorbe'; 'Brilla de Gases'/'nuestro sistema' presentes.")


def forensic_readback(remote_si: str, local_si: str) -> dict:
    """Triple aserción post-sync sobre el documento remoto."""
    return {
        "parity_byte_exact": remote_si == local_si,
        "crediorbe_eradicated_remote": all(bad not in remote_si for bad in FORBIDDEN),
        "brilla_and_nuestro_sistema_present_remote": all(req in remote_si for req in REQUIRED),
    }


def archive_evidence(report: dict) -> str:
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(EVIDENCE_DIR, f"fix_e_prompt_sync_{stamp}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    return path


def main() -> int:
    check_only = "--check" in sys.argv
    print("=" * 72)
    print(f"🚀 FULL PROMPT SYNC (CANAL ÚNICO, FIX-E): Firestore ↔️ app/core/prompts.py {'[CHECK-ONLY]' if check_only else ''}")
    print("=" * 72)

    assert_repo_ssot()

    db = firestore.Client(project=PROJECT_ID)
    doc_ref = db.collection(COLLECTION).document(DOCUMENT)
    local_si = JUAN_PABLO_SYSTEM_INSTRUCTION

    pre_doc = doc_ref.get()
    pre_si = (pre_doc.to_dict() or {}).get(FIELD, "") if pre_doc.exists else ""
    drift = pre_si != local_si
    print(f"📡 PRE-READ remoto: {len(pre_si)} chars | local: {len(local_si)} chars | deriva: {'SÍ' if drift else 'NO'}")
    if pre_si:
        print(f"   remoto contiene 'Crediorbe': {any(b in pre_si for b in FORBIDDEN)}")

    wrote = False
    if check_only:
        print("🔎 CHECK-ONLY: no se escribe. Ejecuta sin --check para sincronizar.")
    elif not drift:
        print("✅ SIN DERIVA: el documento remoto ya es byte-exacto al SSOT. No se requiere escritura.")
    else:
        doc_ref.update({FIELD: local_si})
        wrote = True
        print(f"✅ WRITE: Firestore actualizado desde el SSOT ({len(local_si)} chars).")

    # READ-BACK forense (siempre, haya o no escritura: la aserción es sobre el estado remoto final)
    post_doc = doc_ref.get()
    post_si = (post_doc.to_dict() or {}).get(FIELD, "") if post_doc.exists else ""
    assertions = forensic_readback(post_si, local_si)

    report = {
        "ticket": "BOT-PLAN-HARDENING-EGRESS-FUNNEL-001 / FIX-E",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "target": f"{COLLECTION}/{DOCUMENT}.{FIELD}",
        "check_only": check_only,
        "drift_detected_pre": drift,
        "write_executed": wrote,
        "local_sha256": _sha256(local_si),
        "remote_sha256_post": _sha256(post_si) if post_si else None,
        "assertions": assertions,
        "all_assertions_passed": all(assertions.values()),
    }
    evidence_path = archive_evidence(report)

    print("\n📋 TRIPLE ASERCIÓN POST-SYNC (read-back forense):")
    for key, ok in assertions.items():
        print(f"   {'✅' if ok else '❌'} {key}")
    print(f"🗂️  Evidencia archivada: {evidence_path}")

    if not all(assertions.values()):
        print("❌ FALLA FORENSE: una o más aserciones no se cumplen en el remoto.")
        return 1
    print("✅ FIX-E VERIFICADO: Firestore y repo son espejos idénticos, erradicados y alineados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
