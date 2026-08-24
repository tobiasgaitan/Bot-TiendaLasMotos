"""Reporte consolidado china_eval_report.json para BOT-BUILD-CHINA-EVAL-090."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class VariantResult:
    variant: int
    verdict: str  # PASS, FAIL, CONDICIONAL
    reason: str
    request_summary: dict[str, Any] = field(default_factory=dict)
    response_summary: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProtocolResult:
    protocol: str
    provider: str
    verdict: str
    reason: str
    trace_id: str
    variants: list[VariantResult] = field(default_factory=list)


@dataclass
class EvalReport:
    provider: str
    protocols: list[ProtocolResult] = field(default_factory=list)
    go_no_go: str = "NO-GO"
    summary: str = ""

    def compute_go_no_go(self) -> None:
        core_pass = sum(
            1 for p in self.protocols
            if p.protocol in {"P1", "P2", "P3", "P4"} and p.verdict == "PASS"
        )
        if core_pass >= 3:
            self.go_no_go = "GO"
        elif core_pass == 2:
            self.go_no_go = "CONDICIONAL"
        else:
            self.go_no_go = "NO-GO"
        self.summary = (
            f"{self.provider}: P1-P4 PASS={core_pass}/4; "
            f"P5/P6/P7 resultados={[(p.protocol, p.verdict) for p in self.protocols if p.protocol in ('P5','P6','P7')]}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "go_no_go": self.go_no_go,
            "summary": self.summary,
            "protocols": [
                {
                    "protocol": p.protocol,
                    "verdict": p.verdict,
                    "reason": p.reason,
                    "trace_id": p.trace_id,
                    "variants": [
                        {
                            "variant": v.variant,
                            "verdict": v.verdict,
                            "reason": v.reason,
                            "request_summary": v.request_summary,
                            "response_summary": v.response_summary,
                        }
                        for v in p.variants
                    ],
                }
                for p in self.protocols
            ],
        }


def save_report(reports: list[EvalReport], path: Path | str | None = None) -> Path:
    if path is None:
        path = Path.cwd() / "china_eval_report.json"
    path = Path(path)
    consolidated = {
        "reports": [r.to_dict() for r in reports],
        "global_go_no_go": (
            "GO" if all(r.go_no_go == "GO" for r in reports)
            else "CONDICIONAL" if any(r.go_no_go in ("GO", "CONDICIONAL") for r in reports)
            else "NO-GO"
        ),
    }
    path.write_text(json.dumps(consolidated, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
