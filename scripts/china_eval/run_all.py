"""Orquestador BOT-BUILD-CHINA-EVAL-090."""
from __future__ import annotations

from scripts.china_eval import protocol_p1, protocol_p2, protocol_p3, protocol_p4, protocol_p5, protocol_p6, protocol_p7
from scripts.china_eval.common.report import EvalReport, save_report


PROVIDERS = ["deepseek", "glm52"]


def main() -> None:
    reports: list[EvalReport] = []
    for provider in PROVIDERS:
        report = EvalReport(provider=provider)
        report.protocols.append(protocol_p1.run(provider))
        report.protocols.append(protocol_p2.run(provider))
        report.protocols.append(protocol_p3.run(provider))
        report.protocols.append(protocol_p4.run(provider))
        report.protocols.append(protocol_p5.run(provider))
        report.protocols.append(protocol_p6.run(provider))
        report.protocols.extend(protocol_p7.run(provider))
        report.compute_go_no_go()
        reports.append(report)
        print(f"[{provider}] GO/NO-GO: {report.go_no_go} — {report.summary}")

    path = save_report(reports)
    print(f"\nReporte consolidado: {path}")


if __name__ == "__main__":
    main()
