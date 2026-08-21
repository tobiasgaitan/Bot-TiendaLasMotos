#!/usr/bin/env python3
"""
BOT-BUILD-F45-TRAFFIC-087 — Runner de oleada A/B para tráfico sintético F4.5.

Inyecta mensajes sintéticos por /webhook/task-processor en beta, alternando brazo
A (qwen_enabled=false) y brazo B (qwen_enabled=true), con sonda de ruta en logs
antes de cada brazo y teléfono sintético único por (oleada, brazo, escenario).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
import yaml

# google.cloud.firestore se carga bajo demanda para permitir dry-runs sin credenciales.
try:
    from google.cloud import firestore
except Exception as _firestore_err:  # pragma: no cover
    firestore = None  # type: ignore

SCRIPT_DIR = Path(__file__).resolve().parent
RESULTS_DIR = SCRIPT_DIR / "results"
TASK_PROCESSOR_PATH = "/webhook/task-processor"
TURN_GAP_S = 20.0  # > debounce + procesamiento del MessageBuffer
PROBE_TIMEOUT_S = 90.0
DEFAULT_TIMEOUT_S = 180.0
RETRY_BACKOFFS = [1.5, 3.0, 4.5]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_corpus(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_env_or_die(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"Variable de entorno requerida no definida: {name}")
    return value


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
        )
        .strip()
    )


def load_whatsapp_token() -> Optional[str]:
    token = os.getenv("WHATSAPP_TOKEN")
    if not token:
        try:
            token = load_secret("WHATSAPP_TOKEN")
        except Exception:
            return None
    return token


def set_qwen_flag(value: bool, project: str = "tiendalasmotos") -> None:
    if firestore is None:
        raise RuntimeError("google.cloud.firestore no está disponible")
    db = firestore.Client(project=project)
    doc_ref = db.collection("llm_runtime").document("global")
    doc_ref.set(
        {
            "qwen_enabled": value,
            "updated_at": now_iso(),
        },
        merge=True,
    )


def build_payload(
    phone_number_id: str,
    from_phone: str,
    msg_id: str,
    turn: Dict[str, Any],
    media_ids: Dict[str, str],
) -> Dict[str, Any]:
    timestamp = str(int(time.time()))
    msg_type = turn["type"]
    message: Dict[str, Any] = {"from": from_phone, "id": msg_id, "timestamp": timestamp}

    if msg_type == "text":
        message["type"] = "text"
        message["text"] = {"body": turn["text"]}
    elif msg_type == "image":
        image_id = media_ids.get("image")
        if not image_id:
            raise RuntimeError("media_id de imagen no disponible")
        message["type"] = "image"
        message["image"] = {"id": image_id, "mime_type": "image/png", "caption": turn.get("caption", "")}
    elif msg_type == "audio":
        audio_id = media_ids.get("audio")
        if not audio_id:
            raise RuntimeError("media_id de audio no disponible")
        message["type"] = "audio"
        message["audio"] = {"id": audio_id, "mime_type": "audio/wav"}
    else:
        raise ValueError(f"tipo de turno no soportado: {msg_type}")

    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": phone_number_id,
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15551234567",
                                "phone_number_id": phone_number_id,
                            },
                            "contacts": [
                                {
                                    "profile": {"name": "SyntheticUser"},
                                    "wa_id": from_phone,
                                }
                            ],
                            "messages": [message],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


def query_route_logs(target_bool: bool, service_name: str, project: str) -> List[Dict[str, Any]]:
    target = "true" if target_bool else "false"
    filter_query = (
        f'resource.type=\"cloud_run_revision\" '
        f'AND resource.labels.service_name=\"{service_name}\" '
        f'AND textPayload:\"QWEN ROUTE DECISION\" '
        f'AND textPayload:\"qwen_enabled={target}\"'
    )
    cmd = [
        "gcloud",
        "logging",
        "read",
        filter_query,
        "--freshness=3m",
        "--limit=50",
        "--format=json",
        f"--project={project}",
    ]
    try:
        output = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
        if not output.strip():
            return []
        return json.loads(output)
    except Exception:
        return []


def verify_route(
    target_bool: bool,
    service_name: str,
    project: str,
    timeout: float = PROBE_TIMEOUT_S,
) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        entries = query_route_logs(target_bool, service_name, project)
        if entries:
            return True
        time.sleep(10.0)
    return False


async def send_turn(
    client: httpx.AsyncClient,
    url: str,
    token: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    last_error: Optional[str] = None
    status_code: Optional[int] = None
    response_body: Any = None
    latency_ms: float = 0.0

    for attempt, backoff in enumerate([0.0] + RETRY_BACKOFFS):
        if backoff:
            await asyncio.sleep(backoff)
        start = time.monotonic()
        try:
            resp = await client.post(
                url,
                headers={
                    "Content-Type": "application/json",
                    "X-Task-Token": token,
                },
                json=payload,
                timeout=DEFAULT_TIMEOUT_S,
            )
            latency_ms = (time.monotonic() - start) * 1000
            status_code = resp.status_code
            try:
                response_body = resp.json()
            except Exception:
                response_body = resp.text

            if status_code >= 500:
                last_error = f"HTTP {status_code}"
                continue

            resp.raise_for_status()
            return {
                "status_code": status_code,
                "response_body": response_body,
                "latency_ms": round(latency_ms, 2),
                "error": None,
                "attempts": attempt + 1,
            }
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.TimeoutException) as exc:
            latency_ms = (time.monotonic() - start) * 1000
            last_error = f"{type(exc).__name__}: {exc}"
            continue
        except httpx.HTTPStatusError as exc:
            latency_ms = (time.monotonic() - start) * 1000
            status_code = exc.response.status_code
            last_error = f"HTTP {status_code}"
            if status_code >= 500:
                continue
            return {
                "status_code": status_code,
                "response_body": response_body,
                "latency_ms": round(latency_ms, 2),
                "error": last_error,
                "attempts": attempt + 1,
            }

    return {
        "status_code": status_code,
        "response_body": response_body,
        "latency_ms": round(latency_ms, 2),
        "error": last_error or "unknown",
        "attempts": len([0.0] + RETRY_BACKOFFS),
    }


async def run_scenario(
    scenario: Dict[str, Any],
    arm_label: str,
    arm_index: int,
    wave: int,
    run_id: str,
    phone_number_id: str,
    base_url: str,
    token: str,
    media_ids: Dict[str, str],
    semaphore: asyncio.Semaphore,
) -> Dict[str, Any]:
    scenario_idx = scenario["_index"]
    phone = f"5737700{wave}{arm_index}{scenario_idx:03d}"
    scenario_id = scenario["id"]
    result: Dict[str, Any] = {
        "scenario_id": scenario_id,
        "arm": arm_label,
        "arm_index": arm_index,
        "phone": phone,
        "type": scenario.get("type"),
        "expected_tool": scenario.get("expected_tool"),
        "turns": [],
        "error": None,
    }

    async with semaphore:
        url = base_url.rstrip("/") + TASK_PROCESSOR_PATH
        async with httpx.AsyncClient() as client:
            for turn_idx, turn in enumerate(scenario["turns"]):
                msg_id = f"f45_{run_id}_{arm_label}_{scenario_id}_{turn_idx}"
                try:
                    payload = build_payload(phone_number_id, phone, msg_id, turn, media_ids)
                except Exception as exc:
                    result["error"] = f"build_payload: {exc}"
                    break

                turn_result = await send_turn(client, url, token, payload)
                turn_result["msg_id"] = msg_id
                turn_result["turn_idx"] = turn_idx
                result["turns"].append(turn_result)

                if turn_result["error"]:
                    result["error"] = f"turn {turn_idx}: {turn_result['error']}"
                    break

                # Espera entre turnos para evitar agrupación en el MessageBuffer.
                if turn_idx < len(scenario["turns"]) - 1:
                    await asyncio.sleep(TURN_GAP_S)

    return result


def tag_synthetic_docs(
    phones: List[str],
    run_id: str,
    arm_label: str,
    project: str = "tiendalasmotos",
) -> None:
    if firestore is None:
        return
    db = firestore.Client(project=project)
    collection = db.collection("prospectos")
    batch = db.batch()
    count = 0
    for phone in phones:
        doc_ref = collection.document(f"+{phone}")
        batch.set(
            doc_ref,
            {
                "synthetic_run_id": run_id,
                "synthetic_arm": arm_label,
                "synthetic_tagged_at": now_iso(),
            },
            merge=True,
        )
        count += 1
        if count >= 400:
            batch.commit()
            batch = db.batch()
            count = 0
    if count:
        batch.commit()


def run_arm(
    scenarios: List[Dict[str, Any]],
    arm_label: str,
    arm_index: int,
    qwen_value: bool,
    wave: int,
    run_id: str,
    config: Dict[str, Any],
    args: argparse.Namespace,
) -> Dict[str, Any]:
    project = os.getenv("GOOGLE_CLOUD_PROJECT", "tiendalasmotos")
    service_name = config["meta"].get("beta_service_name", "bot-tiendalasmotos-beta")
    phone_number_id = config["meta"]["beta_phone_number_id"]
    base_url = config["meta"]["beta_base_url"]
    token = load_env_or_die("WEBHOOK_VERIFY_TOKEN")

    print(f"\n🏁 Brazo {arm_label} (qwen_enabled={qwen_value}) — volteando flag...")
    set_qwen_flag(qwen_value, project=project)
    print(f"⏳ Esperando {args.flag_wait}s para refresco de cache...")
    time.sleep(args.flag_wait)

    # Sonda de ruta
    probe_phone = f"5737700{wave}{arm_index}999"
    probe_msg_id = f"f45_{run_id}_probe_{arm_label.lower()}"
    probe_payload = build_payload(
        phone_number_id,
        probe_phone,
        probe_msg_id,
        {"type": "text", "text": "Hola, sonda F4.5"},
        {},
    )

    async def _probe_once():
        async with httpx.AsyncClient() as client:
            return await send_turn(client, base_url.rstrip("/") + TASK_PROCESSOR_PATH, token, probe_payload)

    print(f"🔎 Enviando sonda a {probe_phone}...")
    probe_result = asyncio.run(_probe_once())
    if probe_result["error"]:
        print(f"⚠️  Sonda falló: {probe_result['error']}")
    else:
        print(f"✅ Sonda respondió HTTP {probe_result['status_code']} en {probe_result['latency_ms']}ms")

    print(f"🔎 Verificando ruta en logs (qwen_enabled={qwen_value})...")
    route_ok = verify_route(qwen_value, service_name, project, timeout=args.probe_timeout)
    if route_ok:
        print("✅ Ruta verificada en logs")
    else:
        print("⚠️  No se encontró confirmación de ruta en logs; se continúa bajo riesgo")

    # Media inbound OPCIÓN-A
    media_ids: Dict[str, str] = {}
    if args.skip_media:
        print("ℹ️  Media inbound omitida (--skip-media)")
    else:
        whatsapp_token = load_whatsapp_token()
        if whatsapp_token:
            try:
                from media import upload_image_media, upload_audio_media

                print("📤 Subiendo imagen sintética a Meta...")
                media_ids["image"] = upload_image_media(phone_number_id, whatsapp_token)
                print(f"   image media_id={media_ids['image']}")
                print("📤 Subiendo audio sintético a Meta...")
                media_ids["audio"] = upload_audio_media(phone_number_id, whatsapp_token)
                print(f"   audio media_id={media_ids['audio']}")
            except Exception as exc:
                print(f"⚠️  Fallo al subir media: {exc}. Se omite media inbound.")
                media_ids = {}
        else:
            print("⚠️  WHATSAPP_TOKEN no disponible; se omite media inbound.")

    # Ejecutar corpus
    print(f"🚀 Ejecutando {len(scenarios)} escenarios con concurrencia {args.concurrency}...")
    semaphore = asyncio.Semaphore(args.concurrency)

    async def _run_all() -> List[Dict[str, Any]]:
        tasks = [
            run_scenario(
                sc,
                arm_label,
                arm_index,
                wave,
                run_id,
                phone_number_id,
                base_url,
                token,
                media_ids,
                semaphore,
            )
            for sc in scenarios
        ]
        return await asyncio.gather(*tasks, return_exceptions=True)

    raw_results = asyncio.run(_run_all())

    results: List[Dict[str, Any]] = []
    errors = 0
    for item in raw_results:
        if isinstance(item, Exception):
            results.append({"error": f"exception: {item}"})
            errors += 1
        else:
            results.append(item)
            if item.get("error"):
                errors += 1

    phones = [r["phone"] for r in results if r.get("phone")]
    print(f"🏷️  Etiquetando {len(phones)} docs sintéticos...")
    try:
        tag_synthetic_docs(phones, run_id, arm_label, project=project)
    except Exception as exc:
        print(f"⚠️  Fallo al etiquetar docs: {exc}")

    return {
        "arm": arm_label,
        "qwen_enabled": qwen_value,
        "probe": probe_result,
        "route_verified": route_ok,
        "media_ids": media_ids,
        "scenarios_count": len(scenarios),
        "errors": errors,
        "results": results,
        "started_at": now_iso(),
        "finished_at": now_iso(),
    }


PILOT_SCENARIO_IDS = [
    # BOT-BUILD-MINI-WAVE-EXTENDED-090: 8 MATRIZ + 4 credit_blind con señal financiera explícita.
    # Se excluye credit_apache_cuota (sin ingresos/gastos explícitos).
    "matriz_empleado_alto",
    "matriz_empleado_medio",
    "matriz_independiente_gas",
    "matriz_independiente_reportado",
    "matriz_estudiante",
    "matriz_empleado_premium",
    "matriz_pensionado",
    "matriz_paz_salvo",
    "credit_plausible_2m",
    "credit_combined_work",
    "credit_slang_palos",
    "credit_nkd_cuota",
]


def select_pilot_subset(scenarios: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_id = {sc["id"]: sc for sc in scenarios}
    subset: List[Dict[str, Any]] = []
    for sid in PILOT_SCENARIO_IDS:
        sc = by_id.get(sid)
        if sc:
            sc_copy = dict(sc)
            sc_copy["_index"] = scenarios.index(sc) + 1
            subset.append(sc_copy)
    return subset


def main() -> int:
    parser = argparse.ArgumentParser(description="Runner de oleada A/B F4.5")
    parser.add_argument("--wave", type=int, required=True, help="Número de oleada (1-4)")
    parser.add_argument("--run-id", type=str, required=True, help="ID de la corrida (ej: 2026-08-20T10-00)")
    parser.add_argument("--pilot", action="store_true", help="Ejecutar subset piloto de validación")
    parser.add_argument("--concurrency", type=int, default=6, help="Concurrencia de conversaciones")
    parser.add_argument("--flag-wait", type=int, default=45, help="Segundos de espera tras flip de flag")
    parser.add_argument("--probe-timeout", type=int, default=90, help="Timeout de verificación de ruta en logs")
    parser.add_argument("--results-dir", type=str, default=str(RESULTS_DIR), help="Directorio de resultados")
    parser.add_argument("--skip-media", action="store_true", help="Omitir upload de media inbound")
    parser.add_argument(
        "--arm",
        type=str,
        choices=["A", "B"],
        help="Ejecutar solo un brazo (A o B); útil para reanudar una oleada interrumpida",
    )
    args = parser.parse_args()

    if not (1 <= args.wave <= 4):
        raise SystemExit("--wave debe estar entre 1 y 4")

    corpus_path = SCRIPT_DIR / "corpus.yaml"
    config = load_corpus(corpus_path)

    scenarios = config["scenarios"]
    for idx, sc in enumerate(scenarios, start=1):
        sc["_index"] = idx

    if args.pilot:
        scenarios = select_pilot_subset(scenarios)
        print(f"🧪 MODO PILOTO: {len(scenarios)} escenarios seleccionados")

    # Orden alternado planificado: impares A->B, pares B->A
    arm_a = ("A", 0, False)
    arm_b = ("B", 1, True)
    planned_arms: List[Tuple[str, int, bool]] = (
        [arm_a, arm_b] if args.wave % 2 == 1 else [arm_b, arm_a]
    )

    if args.arm:
        arms = [arm_a if args.arm == "A" else arm_b]
    else:
        arms = planned_arms

    run_dir = Path(args.results_dir) / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = run_dir / "run_manifest.json"

    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        print(f"📂 Manifest existente cargado: {manifest_path}")
    else:
        manifest = {
            "run_id": args.run_id,
            "wave": args.wave,
            "pilot": args.pilot,
            "phone_prefix": config["meta"]["phone_prefix"],
            "beta_phone_number_id": config["meta"]["beta_phone_number_id"],
            "beta_service_name": config["meta"].get("beta_service_name", "bot-tiendalasmotos-beta"),
            "started_at": now_iso(),
            "arm_order": [label for label, _, _ in planned_arms],
            "scenarios_count": len(scenarios),
            "arms": [],
        }

    existing_labels = {a["arm"] for a in manifest.get("arms", [])}

    for label, index, qwen_value in arms:
        if label in existing_labels:
            print(f"⚠️  Brazo {label} ya existe en el manifest; se omite.")
            continue
        arm_result = run_arm(
            scenarios,
            label,
            index,
            qwen_value,
            args.wave,
            args.run_id,
            config,
            args,
        )
        manifest["arms"].append(arm_result)
        arm_file = run_dir / f"arm_{label.lower()}.json"
        with open(arm_file, "w", encoding="utf-8") as f:
            json.dump(arm_result, f, ensure_ascii=False, indent=2)
        print(f"💾 Resultados del brazo {label} guardados en {arm_file}")

    manifest["finished_at"] = now_iso()
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Oleada {args.wave} completada. Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
