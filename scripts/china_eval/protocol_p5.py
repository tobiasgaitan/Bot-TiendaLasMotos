"""Protocolo P5: audio transcription (pipeline externo, GO/NO-GO independiente)."""
from __future__ import annotations

import json
from dataclasses import asdict

from scripts.china_eval.common.logging import log_event, new_trace_id
from scripts.china_eval.common.report import ProtocolResult, VariantResult


VARIANTS = [
    {"audio_id": "audio_01", "duration_s": 2, "format": "ogg/opus", "ground_truth": "Quiero una moto deportiva a crédito"},
    {"audio_id": "audio_02", "duration_s": 2, "format": "ogg/opus", "ground_truth": "Me llamo Juan Pérez"},
]


def run(provider: str) -> ProtocolResult:
    trace_id = new_trace_id()
    variants: list[VariantResult] = []
    for idx, variant in enumerate(VARIANTS, start=1):
        reason = (
            "P5 requiere pipeline externo (FunASR/Gemini audio). "
            "No se ejecuta en este run por ausencia de corpus de audio real y modelos locales."
        )
        v = VariantResult(
            variant=idx,
            verdict="CONDICIONAL",
            reason=reason,
            request_summary={"audio_id": variant["audio_id"], "ground_truth": variant["ground_truth"]},
            response_summary={"note": "pipeline externo pendiente"},
        )
        variants.append(v)
        log_event(trace_id, "P5", idx, provider, "CONDICIONAL", reason, v.request_summary, v.response_summary)

    return ProtocolResult(
        protocol="P5",
        provider=provider,
        verdict="CONDICIONAL",
        reason="Pipeline externo de audio no ejecutado; GO/NO-GO independiente",
        trace_id=trace_id,
        variants=variants,
    )


if __name__ == "__main__":
    import sys

    prov = sys.argv[1] if len(sys.argv) > 1 else "deepseek"
    print(json.dumps(asdict(run(prov)), ensure_ascii=False, indent=2))
