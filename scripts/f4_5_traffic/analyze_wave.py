#!/usr/bin/env python3
"""
BOT-BUILD-F45-TRAFFIC-087 — Análisis de oleada A/B contra baseline.

Correlaciona por teléfono sintético:
  - Cloud Logging (ruta, failover, supresiones, fallos PCC).
  - Langfuse (latencia por trace).
  - Firestore prospectos (score_resultado, args extraídos).

Emite analysis_report.json + analysis_report.md con veredicto por umbral 086.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import quote

import httpx


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_ts(iso: str) -> datetime:
    # Soporta '+00:00' y 'Z'
    iso = iso.replace("Z", "+00:00")
    return datetime.fromisoformat(iso)


def fmt_gcloud_ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def load_secret(name: str, project: str = "tiendalasmotos") -> str:
    return (
        subprocess.check_output(
            [
                "gcloud",
                "secrets",
                "versions",
                "access",
                "latest",
                "--secret",
                name,
                "--project",
                project,
            ],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        .strip()
    )


def load_langfuse_creds() -> Tuple[Optional[str], Optional[str], str]:
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com").rstrip("/")
    pk = os.getenv("LANGFUSE_PUBLIC_KEY")
    sk = os.getenv("LANGFUSE_SECRET_KEY")
    if not pk or not sk:
        try:
            pk = load_secret("LANGFUSE_PUBLIC_KEY")
            sk = load_secret("LANGFUSE_SECRET_KEY")
        except Exception:
            return None, None, host
    return pk, sk, host


def query_cloud_logging(
    service_name: str,
    project: str,
    start: datetime,
    end: datetime,
    limit: int = 50000,
) -> List[Dict[str, Any]]:
    # Filtramos por prefijo sintético o marcadores globales para no saturar el límite.
    filter_query = (
        f'resource.type="cloud_run_revision" '
        f'AND resource.labels.service_name="{service_name}" '
        f'AND timestamp>="{fmt_gcloud_ts(start)}" '
        f'AND timestamp<="{fmt_gcloud_ts(end)}" '
        f'AND (textPayload:"+5737700" '
        f'OR textPayload:"QWEN ROUTE DECISION" '
        f'OR textPayload:"DUAL FAILOVER" '
        f'OR textPayload:"TOOL-SUPPRESS" '
        f'OR textPayload:"CATALOG_VALIDATION_FAIL")'
    )
    cmd = [
        "gcloud",
        "logging",
        "read",
        filter_query,
        f"--limit={limit}",
        "--format=json",
        f"--project={project}",
    ]
    try:
        output = subprocess.check_output(cmd, text=True, stderr=subprocess.PIPE)
        if not output.strip():
            return []
        return json.loads(output)
    except subprocess.CalledProcessError as exc:
        print(f"⚠️  Cloud Logging query failed: {exc.stderr[:500]}")
        return []


def _fmt_langfuse_ts(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def query_langfuse_traces(
    host: str,
    public_key: str,
    secret_key: str,
    start: datetime,
    end: datetime,
    name: str = "whatsapp_webhook_background",
    page_size: int = 100,
) -> List[Dict[str, Any]]:
    # Construimos la URL manualmente para evitar que httpx codifique los ':' de ISO-8601,
    # lo que provoca 400 en la API v1 de Langfuse. La API v1 tiene límite de 100 ítems/página.
    base_url = (
        f"{host}/api/public/traces?"
        f"name={quote(name, safe='')}&"
        f"fromTimestamp={_fmt_langfuse_ts(start)}&"
        f"toTimestamp={_fmt_langfuse_ts(end)}&"
        f"limit={page_size}"
    )
    all_traces: List[Dict[str, Any]] = []
    page = 1
    try:
        with httpx.Client(timeout=60.0) as client:
            while True:
                resp = client.get(f"{base_url}&page={page}", auth=(public_key, secret_key))
                resp.raise_for_status()
                body = resp.json()
                all_traces.extend(body.get("data", []))
                meta = body.get("meta", {})
                total_pages = meta.get("totalPages", 1)
                if page >= total_pages:
                    break
                page += 1
        return all_traces
    except Exception as exc:
        print(f"⚠️  Langfuse query failed: {exc}")
        return []


def fetch_prospect_docs(
    phones: List[str],
    project: str = "tiendalasmotos",
) -> Dict[str, Dict[str, Any]]:
    try:
        from google.cloud import firestore
    except Exception as exc:
        print(f"⚠️  No se pudo importar firestore: {exc}")
        return {}

    db = firestore.Client(project=project)
    collection = db.collection("prospectos")
    docs: Dict[str, Dict[str, Any]] = {}
    for phone in phones:
        try:
            snap = collection.document(f"+{phone}").get()
            if snap.exists:
                docs[phone] = dict(snap.to_dict())
        except Exception as exc:
            print(f"⚠️  Fallo leyendo prospecto +{phone}: {exc}")
    return docs


def is_affirmative(value: Any) -> bool:
    if value is True or value == 1:
        return True
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"sí", "si", "yes", "true"}:
            return True
        if "sí tengo" in text or "si tengo" in text or "tengo" in text and "no " not in text:
            return True
    return False


def is_gas_affirmative(value: Any) -> bool:
    return is_affirmative(value)


def resolve_cierre_route(score: Optional[int], gas: Any) -> Optional[int]:
    if score is None:
        return None
    if score >= 750:
        return 1
    if score >= 500:
        return 2
    if is_gas_affirmative(gas):
        return 3
    return 4


ROUTE_LABELS = {1: "R1_Banco", 2: "R2_Revision", 3: "R3_Brilla", 4: "R4_Rechazo"}


def normalize_money(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).lower()
    text = text.replace(".", "").replace(",", "")
    text = text.replace("$", "").replace("cop", "").strip()
    # Mapeos comunes
    multipliers = {
        "millones": 1_000_000,
        "millon": 1_000_000,
        "m": 1_000_000,
        "millones mensuales": 1_000_000,
        "palos": 1_000_000,
        "k": 1_000,
        "mil": 1_000,
    }
    for suffix, mult in multipliers.items():
        if suffix in text:
            try:
                number_part = text.replace(suffix, "").strip()
                if not number_part:
                    return None
                return int(float(number_part) * mult)
            except Exception:
                continue
    try:
        return int(float(text))
    except Exception:
        return None


def get_doc_field(doc: Dict[str, Any], keys: List[str]) -> Any:
    for k in keys:
        if k in doc and doc[k] not in (None, ""):
            return doc[k]
    return None


MATRIZ_FIELDS = [
    ("ocupacion", ["ocupacion", "ocupacion_y_contrato"]),
    ("ingresos_mensuales", ["ingresos_mensuales", "ingresos_demostrables", "income"]),
    ("datacredito", ["datacredito", "historial_datacredito", "credit_history"]),
    ("gastos_mensuales", ["gastos_mensuales", "gastos"]),
    ("tiene_gas_natural", ["tiene_gas_natural", "servicios_publicos"]),
    ("vivienda", ["vivienda"]),
    ("plan_celular", ["plan_celular", "phone_plan"]),
]


def extract_matriz_snapshot(doc: Dict[str, Any]) -> Dict[str, Any]:
    snap: Dict[str, Any] = {}
    for label, keys in MATRIZ_FIELDS:
        raw = get_doc_field(doc, keys)
        if label in ("ingresos_mensuales", "gastos_mensuales"):
            snap[label] = normalize_money(raw)
        elif label == "tiene_gas_natural":
            snap[label] = is_gas_affirmative(raw)
        elif label == "plan_celular":
            snap[label] = is_affirmative(raw)
        elif raw is None:
            snap[label] = None
        else:
            snap[label] = str(raw).strip().lower()
    return snap


def matriz_snapshots_equal(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    for label in a:
        if a.get(label) != b.get(label):
            return False
    return True


def percentile(sorted_values: List[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * p
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return sorted_values[f]
    return sorted_values[f] * (c - k) + sorted_values[c] * (k - f)


def classify_tool_invocations(
    logs: List[Dict[str, Any]],
    phone: str,
    tool_names: List[str],
) -> Set[str]:
    invoked: Set[str] = set()
    phone_norm = f"+{phone}"
    for entry in logs:
        payload = entry.get("textPayload", "") or ""
        if phone_norm not in payload and phone not in payload:
            continue
        for tool in tool_names:
            if tool in payload:
                invoked.add(tool)
    return invoked


def analyze_arm(
    arm_result: Dict[str, Any],
    logs: List[Dict[str, Any]],
    traces: List[Dict[str, Any]],
    docs: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    arm_label = arm_result["arm"]
    qwen = arm_result["qwen_enabled"]
    scenarios = arm_result["results"]
    phones = [s["phone"] for s in scenarios if s.get("phone")]
    phone_set = set(phones)

    # Errores HTTP registrados por el runner
    errors = sum(1 for s in scenarios if s.get("error"))
    total = len(scenarios)
    error_rate = errors / total if total else 0.0

    # Latencias Langfuse filtradas por userId de teléfonos sintéticos.
    # Fuente: campo 'latency' de la API v1 de Langfuse, expresado en segundos.
    arm_traces = [
        t for t in traces
        if t.get("userId") and t["userId"].lstrip("+") in phone_set
    ]
    latencies_s = []
    for t in arm_traces:
        lat = t.get("latency")
        if isinstance(lat, (int, float)) and lat > 0:
            latencies_s.append(float(lat))
    latencies_sorted = sorted(latencies_s)
    p50 = percentile(latencies_sorted, 0.50)
    p95 = percentile(latencies_sorted, 0.95)

    # Métricas operativas de logs
    catalog_fail = sum(
        1 for e in logs if "CATALOG_VALIDATION_FAIL" in (e.get("textPayload") or "")
    )
    dual_failover = sum(
        1 for e in logs if "DUAL FAILOVER" in (e.get("textPayload") or "")
    )
    tool_suppress = sum(
        1 for e in logs if "[TOOL-SUPPRESS] retry_failed fail_open" in (e.get("textPayload") or "")
    )

    # Tool-call rate y scores
    expected_tool_hits = 0
    actual_tool_hits = 0
    scores: List[int] = []
    routes: List[int] = []
    matriz_divergences = 0
    matriz_pairs: List[Tuple[str, Dict[str, Any], Dict[str, Any]]] = []

    for sc in scenarios:
        phone = sc.get("phone")
        if not phone:
            continue
        doc = docs.get(phone, {})
        expected = sc.get("expected_tool")
        if expected:
            expected_tool_hits += 1
            invoked = False
            # Para calculate_credit_score, la persistencia de score_resultado es evidencia definitiva.
            if expected == "calculate_credit_score":
                invoked = doc.get("score_resultado") is not None
            if not invoked:
                invoked = expected in classify_tool_invocations(logs, phone, [expected, "function_call"])
            if invoked:
                actual_tool_hits += 1

        score = doc.get("score_resultado")
        if isinstance(score, (int, float)):
            scores.append(int(score))
            route = resolve_cierre_route(int(score), doc.get("tiene_gas_natural") or doc.get("servicios_publicos"))
            if route:
                routes.append(route)

    tool_call_rate = actual_tool_hits / expected_tool_hits if expected_tool_hits else None

    return {
        "arm": arm_label,
        "qwen_enabled": qwen,
        "total_scenarios": total,
        "errors": errors,
        "error_rate": round(error_rate, 4),
        "expected_tool_hits": expected_tool_hits,
        "actual_tool_hits": actual_tool_hits,
        "tool_call_rate": round(tool_call_rate, 4) if tool_call_rate is not None else None,
        "scores": scores,
        "score_count": len(scores),
        "score_mean": round(sum(scores) / len(scores), 2) if scores else None,
        "score_p50": round(percentile(sorted(scores), 0.50), 2) if scores else None,
        "score_p90": round(percentile(sorted(scores), 0.90), 2) if scores else None,
        "routes": routes,
        "route_distribution": {label: routes.count(r) / len(routes) if routes else 0.0 for r, label in ROUTE_LABELS.items()},
        "latencies_s": latencies_s,
        "latency_p50_s": round(p50, 2),
        "latency_p95_s": round(p95, 2),
        "trace_count": len(arm_traces),
        "latency_source": "Langfuse trace latency (seconds)",
        "catalog_validation_fail": catalog_fail,
        "dual_failover": dual_failover,
        "tool_suppress_retry_failed": tool_suppress,
    }


def compare_arms(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    # Asume A = baseline, B = tratamiento
    diffs: Dict[str, Any] = {}

    # Tool call rate ±10%
    if a.get("tool_call_rate") is not None and b.get("tool_call_rate") is not None:
        diff_pct = b["tool_call_rate"] - a["tool_call_rate"]
        diffs["tool_call_rate_delta_pct"] = round(diff_pct * 100, 2)
        diffs["tool_call_rate_ok"] = abs(diff_pct) <= 0.10
    else:
        diffs["tool_call_rate_ok"] = None

    # Score |Δmean| <= 20
    if a.get("score_mean") is not None and b.get("score_mean") is not None:
        diffs["score_mean_delta"] = round(b["score_mean"] - a["score_mean"], 2)
        diffs["score_mean_ok"] = abs(diffs["score_mean_delta"]) <= 20
    else:
        diffs["score_mean_ok"] = None

    # p95 latencia B <= 1.15 * A
    if a.get("latency_p95_s") and b.get("latency_p95_s"):
        ratio = b["latency_p95_s"] / a["latency_p95_s"] if a["latency_p95_s"] else None
        diffs["latency_p95_ratio"] = round(ratio, 3) if ratio else None
        diffs["latency_p95_ok"] = ratio is not None and ratio <= 1.15
    else:
        diffs["latency_p95_ok"] = None

    # Failover B < 5%
    total_b = b.get("total_scenarios", 0)
    failover_b = b.get("dual_failover", 0)
    failover_rate_b = failover_b / total_b if total_b else 0.0
    diffs["failover_rate_b"] = round(failover_rate_b, 4)
    diffs["failover_ok"] = failover_rate_b < 0.05

    # Ruta mix shift <=5pp por categoría
    route_ok = True
    route_shifts: Dict[str, float] = {}
    for r, label in ROUTE_LABELS.items():
        pa = a.get("route_distribution", {}).get(label, 0.0)
        pb = b.get("route_distribution", {}).get(label, 0.0)
        shift = abs(pb - pa)
        route_shifts[label] = round(shift, 4)
        if shift > 0.05:
            route_ok = False
    diffs["route_shifts_pp"] = route_shifts
    diffs["route_mix_ok"] = route_ok

    return diffs


def evaluate_matriz_divergence(
    manifest: Dict[str, Any],
    docs: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    # Empareja escenarios MATRIZ entre brazos A y B por scenario_id
    pairs: Dict[str, Tuple[Optional[str], Optional[str]]] = {}
    for arm in manifest.get("arms", []):
        for sc in arm.get("results", []):
            if sc.get("type") == "matriz_full":
                sid = sc["scenario_id"]
                if sid not in pairs:
                    pairs[sid] = (None, None)
                if arm["arm"] == "A":
                    pairs[sid] = (sc.get("phone"), pairs[sid][1])
                elif arm["arm"] == "B":
                    pairs[sid] = (pairs[sid][0], sc.get("phone"))

    divergences = 0
    details = []
    for sid, (phone_a, phone_b) in pairs.items():
        if not phone_a or not phone_b:
            continue
        doc_a = docs.get(phone_a, {})
        doc_b = docs.get(phone_b, {})
        snap_a = extract_matriz_snapshot(doc_a)
        snap_b = extract_matriz_snapshot(doc_b)
        equal = matriz_snapshots_equal(snap_a, snap_b)
        if not equal:
            divergences += 1
        details.append({
            "scenario_id": sid,
            "phone_a": phone_a,
            "phone_b": phone_b,
            "snap_a": snap_a,
            "snap_b": snap_b,
            "equal": equal,
        })

    return {
        "matriz_pairs": len(pairs),
        "matriz_divergences": divergences,
        "matriz_ok": divergences == 0,
        "details": details,
    }


def build_catalog_fail_map(
    manifest: Dict[str, Any],
    logs: List[Dict[str, Any]],
) -> Dict[str, Dict[str, int]]:
    """Mapea escenario_id -> {A: count, B: count} para CATALOG_VALIDATION_FAIL."""
    phone_to_scenario: Dict[str, Tuple[str, str]] = {}
    for arm in manifest.get("arms", []):
        arm_label = arm["arm"]
        for sc in arm.get("results", []):
            phone = sc.get("phone")
            if phone:
                phone_to_scenario[phone] = (sc["scenario_id"], arm_label)

    fails: Dict[str, Dict[str, int]] = {}
    for entry in logs:
        text = entry.get("textPayload", "") or ""
        if "CATALOG_VALIDATION_FAIL" not in text:
            continue
        for phone, (sid, arm_label) in phone_to_scenario.items():
            if f"+{phone}" in text or phone in text:
                fails.setdefault(sid, {"A": 0, "B": 0})
                fails[sid][arm_label] += 1
    return fails


def overall_verdict(comparison: Dict[str, Any], matriz_ok: bool, a: Dict[str, Any], b: Dict[str, Any]) -> str:
    checks = [
        comparison.get("tool_call_rate_ok") is not False,
        comparison.get("score_mean_ok") is not False,
        comparison.get("latency_p95_ok") is not False,
        comparison.get("failover_ok") is not False,
        comparison.get("route_mix_ok") is not False,
        matriz_ok,
        (a.get("error_rate", 0.0) <= 0.01),
    ]
    return "VERDE" if all(checks) else "ROJO"


def main() -> int:
    parser = argparse.ArgumentParser(description="Análisis de oleada A/B F4.5")
    parser.add_argument("run-id", type=str, help="ID de la corrida a analizar")
    parser.add_argument("--results-dir", type=str, default="scripts/f4_5_traffic/results", help="Directorio de resultados")
    parser.add_argument("--project", type=str, default="tiendalasmotos", help="GCP project")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    run_dir = results_dir / getattr(args, "run-id")
    if not run_dir.exists():
        raise SystemExit(f"No existe directorio de resultados: {run_dir}")

    manifest_path = run_dir / "run_manifest.json"
    arm_files = sorted(run_dir.glob("arm_*.json"))
    loaded_arms = [load_json(f) for f in arm_files]

    if manifest_path.exists():
        manifest = load_json(manifest_path)
        existing = {a["arm"]: a for a in manifest.get("arms", [])}
        for a in loaded_arms:
            existing[a["arm"]] = a
        manifest["arms"] = [existing[l] for l in ["A", "B"] if l in existing]
    else:
        if len(loaded_arms) < 2:
            raise SystemExit(f"No se encontró manifest ni ambos arm_*.json en {run_dir}")
        manifest = {
            "run_id": getattr(args, "run-id"),
            "wave": 0,
            "pilot": False,
            "arms": loaded_arms,
        }
    service_name = manifest.get("beta_service_name", "bot-tiendalasmotos-beta")

    start = parse_ts(manifest["started_at"])
    end = parse_ts(manifest["finished_at"])
    # Márgenes de 2 min para logs y Langfuse
    start_margin = start
    if start_margin.tzinfo is None:
        start_margin = start.replace(tzinfo=timezone.utc)
    end_margin = end
    if end_margin.tzinfo is None:
        end_margin = end.replace(tzinfo=timezone.utc)

    print("📡 Consultando Cloud Logging...")
    logs = query_cloud_logging(service_name, args.project, start_margin, end_margin)
    print(f"   {len(logs)} entradas recuperadas")

    print("📡 Consultando Langfuse...")
    pk, sk, host = load_langfuse_creds()
    traces: List[Dict[str, Any]] = []
    if pk and sk:
        traces = query_langfuse_traces(host, pk, sk, start_margin, end_margin)
        print(f"   {len(traces)} trazas recuperadas")
    else:
        print("   Credenciales de Langfuse no disponibles; se omite latencia")

    # Recolectar todos los teléfonos sintéticos
    all_phones: List[str] = []
    for arm in manifest.get("arms", []):
        for sc in arm.get("results", []):
            if sc.get("phone"):
                all_phones.append(sc["phone"])

    print(f"🔎 Leyendo {len(all_phones)} docs de prospectos...")
    docs = fetch_prospect_docs(all_phones, project=args.project)
    print(f"   {len(docs)} docs encontrados")

    arm_analyses = []
    for arm in manifest.get("arms", []):
        analysis = analyze_arm(arm, logs, traces, docs)
        arm_analyses.append(analysis)

    # Baseline A vs tratamiento B
    a_analysis = next((x for x in arm_analyses if x["arm"] == "A"), None)
    b_analysis = next((x for x in arm_analyses if x["arm"] == "B"), None)
    comparison = compare_arms(a_analysis, b_analysis) if a_analysis and b_analysis else {}

    matriz_eval = evaluate_matriz_divergence(manifest, docs)
    catalog_fail_map = build_catalog_fail_map(manifest, logs)

    verdict = overall_verdict(comparison, matriz_eval["matriz_ok"], a_analysis or {}, b_analysis or {})

    report = {
        "run_id": manifest["run_id"],
        "wave": manifest["wave"],
        "pilot": manifest.get("pilot", False),
        "verdict": verdict,
        "generated_at": now_iso(),
        "arm_analyses": arm_analyses,
        "comparison": comparison,
        "matriz": matriz_eval,
        "catalog_validation_fail_by_scenario": catalog_fail_map,
    }

    json_path = run_dir / "analysis_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    md_path = run_dir / "analysis_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(render_markdown(report, a_analysis, b_analysis, comparison, matriz_eval, catalog_fail_map))

    print(f"\n✅ Análisis completo: {json_path}")
    print(f"📄 Resumen markdown: {md_path}")
    print(f"🚦 Veredicto: {verdict}")
    return 0 if verdict == "VERDE" else 1


def render_markdown(
    report: Dict[str, Any],
    a: Optional[Dict[str, Any]],
    b: Optional[Dict[str, Any]],
    comparison: Dict[str, Any],
    matriz_eval: Dict[str, Any],
    catalog_fail_map: Dict[str, Dict[str, int]],
) -> str:
    lines = [
        f"# Análisis F4.5 — {report['run_id']} (oleada {report['wave']})",
        "",
        f"- **Modo piloto:** {report.get('pilot', False)}",
        f"- **Veredicto:** {report['verdict']}",
        f"- **Generado:** {report['generated_at']}",
        "",
        "## Denominadores",
        "",
        f"- Escenarios por brazo: {report['arm_analyses'][0]['total_scenarios'] if report['arm_analyses'] else '—'}",
        f"- Expected tool hits (calculate_credit_score) por brazo: {report['arm_analyses'][0].get('expected_tool_hits') if report['arm_analyses'] else '—'}",
        f"- Trazas Langfuse recuperadas: A={report['arm_analyses'][0].get('trace_count') if report['arm_analyses'] else '—'}, "
        f"B={report['arm_analyses'][1].get('trace_count') if len(report['arm_analyses']) > 1 else '—'}",
        f"- Fuente de latencia: {report['arm_analyses'][0].get('latency_source', 'Langfuse')} (segundos)",
        "",
        "## Métricas por brazo",
        "",
        "| Métrica | Brazo A (baseline) | Brazo B (Qwen) |",
        "|---|---|---|",
    ]

    def fmt(x: Any) -> str:
        if x is None:
            return "—"
        if isinstance(x, float):
            return f"{x:.4f}"
        return str(x)

    if a and b:
        rows = [
            ("Escenarios", a["total_scenarios"], b["total_scenarios"]),
            ("Errores HTTP", a["errors"], b["errors"]),
            ("Tasa errores", a["error_rate"], b["error_rate"]),
            ("Tool-call rate", a.get("tool_call_rate"), b.get("tool_call_rate")),
            ("Score mean", a.get("score_mean"), b.get("score_mean")),
            ("Score p50", a.get("score_p50"), b.get("score_p50")),
            ("Score p90", a.get("score_p90"), b.get("score_p90")),
            ("Latencia p50 s", a["latency_p50_s"], b["latency_p50_s"]),
            ("Latencia p95 s", a["latency_p95_s"], b["latency_p95_s"]),
            ("CATALOG_VALIDATION_FAIL", a["catalog_validation_fail"], b["catalog_validation_fail"]),
            ("DUAL FAILOVER", a["dual_failover"], b["dual_failover"]),
            ("TOOL-SUPPRESS retry_failed", a["tool_suppress_retry_failed"], b["tool_suppress_retry_failed"]),
        ]
        for label, av, bv in rows:
            lines.append(f"| {label} | {fmt(av)} | {fmt(bv)} |")

        lines.append("")
        lines.append("## Comparación A/B")
        lines.append("")
        lines.append(f"- Δ tool-call rate: {comparison.get('tool_call_rate_delta_pct', '—')}pp (ok={comparison.get('tool_call_rate_ok')})")
        lines.append(f"- Δ score mean: {comparison.get('score_mean_delta', '—')} (ok={comparison.get('score_mean_ok')})")
        lines.append(f"- Ratio p95 latencia B/A: {comparison.get('latency_p95_ratio', '—')} (ok={comparison.get('latency_p95_ok')})")
        lines.append(f"- Failover rate B: {comparison.get('failover_rate_b', '—')} (ok={comparison.get('failover_ok')})")
        lines.append(f"- Shift mix ruta: {comparison.get('route_shifts_pp', {})} (ok={comparison.get('route_mix_ok')})")
        lines.append(f"- MATRIZ divergencias: {matriz_eval['matriz_divergences']}/{matriz_eval['matriz_pairs']} (ok={matriz_eval['matriz_ok']})")
        lines.append("")
        lines.append("## Distribución de rutas de cierre")
        lines.append("")
        lines.append("| Ruta | A | B |")
        lines.append("|---|---|---|")
        for r, label in ROUTE_LABELS.items():
            pa = a.get("route_distribution", {}).get(label, 0.0)
            pb = b.get("route_distribution", {}).get(label, 0.0)
            lines.append(f"| {label} | {pa:.2%} | {pb:.2%} |")
    else:
        lines.append("No se encontraron ambos brazos para comparar.")

    lines.append("")
    lines.append("## CATALOG_VALIDATION_FAIL por escenario (correlación A vs B)")
    lines.append("")
    if catalog_fail_map:
        lines.append("| Escenario | A | B |")
        lines.append("|---|---|---|")
        for sid in sorted(catalog_fail_map.keys()):
            counts = catalog_fail_map[sid]
            lines.append(f"| {sid} | {counts.get('A', 0)} | {counts.get('B', 0)} |")
    else:
        lines.append("Sin eventos CATALOG_VALIDATION_FAIL en esta oleada.")

    lines.append("")
    lines.append("## Notas")
    lines.append("- El prefijo 5737700xxxxx debe excluirse de dashboards de deliverability (C5-F45-02).")
    lines.append("- La colección subyacente es `prospectos` compartida con prod; la purga se ejecuta con cleanup_synthetic.py.")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
