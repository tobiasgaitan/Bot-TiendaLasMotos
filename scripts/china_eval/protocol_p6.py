"""Protocolo P6: image analysis (pipeline externo, GO/NO-GO independiente)."""
from __future__ import annotations

import json
from dataclasses import asdict

from scripts.china_eval.common.logging import log_event, new_trace_id
from scripts.china_eval.common.report import ProtocolResult, VariantResult


VARIANTS = [
    {"image_id": "moto_01", "description": "Foto frontal moto deportiva roja"},
    {"image_id": "doc_01", "description": "Captura cédula de ciudadanía"},
]


def run(provider: str) -> ProtocolResult:
    trace_id = new_trace_id()
    variants: list[VariantResult] = []
    for idx, variant in enumerate(VARIANTS, start=1):
        reason = (
            "P6 requiere pipeline externo (MiniMax M3 / GLM-5V-Turbo). "
            "No se ejecuta en este run por ausencia de imágenes reales y modelos locales."
        )
        v = VariantResult(
            variant=idx,
            verdict="CONDICIONAL",
            reason=reason,
            request_summary={"image_id": variant["image_id"], "description": variant["description"]},
            response_summary={"note": "pipeline externo pendiente"},
        )
        variants.append(v)
        log_event(trace_id, "P6", idx, provider, "CONDICIONAL", reason, v.request_summary, v.response_summary)

    return ProtocolResult(
        protocol="P6",
        provider=provider,
        verdict="CONDICIONAL",
        reason="Pipeline externo de imagen no ejecutado; GO/NO-GO independiente",
        trace_id=trace_id,
        variants=variants,
    )


if __name__ == "__main__":
    import sys

    prov = sys.argv[1] if len(sys.argv) > 1 else "deepseek"
    print(json.dumps(asdict(run(prov)), ensure_ascii=False, indent=2))
