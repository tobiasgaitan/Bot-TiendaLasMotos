#!/usr/bin/env python3
"""
BOT-BUILD-HYBRID-PROBE-FIX2-099 — Sonda MATRIZ híbrida-consciente para F5.

Inyecta 2 sesiones MATRIZ completas por /webhook/task-processor en beta, SIN tocar
flags de Firestore, y verifica el núcleo de perfilamiento por ESTADO del embudo
(PHASE_3 → deepseek para captured<7, Gemini frontera para captured≥7, Gemini cierre
para COMPLETO). Tolerante al lag de extracción del CRM (duplicados/saltos de
 captured_count) y clasifica failovers entre núcleo y auxiliares.

Autocontenida por diseño: NO importa de run_wave.py (C5-134 contención durante
ventana 48h). Las funciones de inyección básica son trasplante verbatim de
run_wave.py con comentario de procedencia.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

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
TURN_GAP_S = 20.0
SETTLE_S = 90.0
INTER_SESSION_SETTLE_S = 45.0
DEFAULT_TIMEOUT_S = 180.0
RETRY_BACKOFFS = [1.5, 3.0, 4.5]
QUIESCE_MINUTES = 10

# Índices de turno dentro de los escenarios matriz_full.
# Corpus endurecido (BOT-BUILD-F45-PROBE-ROBUST-105): turno 2 solicita el link
# de privacidad; turno 3 es la aceptación; turno 4 es identidad.
HABEAS_ACCEPT_TURN_IDX = 3
IDENTITY_TURN_IDX = 4
FAILFAST_PHASE3_TIMEOUT = 30.0

PRIVACY_LINK = "https://tiendalasmotos.com/politica-de-privacidad"
PRIVACY_LINK_SNIPPET = "tiendalasmotos.com/politica-de-privacidad"

HYBRID_ROUTE_RE = re.compile(
    r"\[HYBRID ROUTE(?: ASYNC)?\] "
    r"provider=(\S+) "
    r"reason=(\S+) "
    r"captured_count=(\S+) "
    r"siguiente=(.*?) "
    r"fase=(\S+)"
)

HYBRID_BACKSTOP_RE = re.compile(
    r"\[HYBRID BACKSTOP ASYNC\] "
    r"reason=(\S+) "
    r"captured_count=(\S+) "
    r"siguiente=(.*?) "
    r"depth=(\S+)"
)

WHITELIST_REASONS = {
    "default_conservador",
    "simulacion_ciega_paso2",
    "tarea_p1_catalogo",
    "tarea_faq_contexto",
    "route_fallback_gemini",
    "frontera_turno_7_matriz",
    "cierre_fase_completo",
}

CORE_PROFILING_RE = re.compile(r"^turno_\d+_profiling$")


def _is_whitelisted_reason(reason: str) -> bool:
    if reason in WHITELIST_REASONS:
        return True
    if CORE_PROFILING_RE.match(reason):
        return True
    return False

DEFAULT_SCENARIOS = ["matriz_empleado_alto", "matriz_independiente_reportado"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_corpus(path: Path) -> Dict[str, Any]:
    """Trasplante verbatim de run_wave.py."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_env_or_die(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"Variable de entorno requerida no definida: {name}")
    return value


def build_payload(
    phone_number_id: str,
    from_phone: str,
    msg_id: str,
    turn: Dict[str, Any],
    media_ids: Dict[str, str],
) -> Dict[str, Any]:
    """
    Trasplante verbatim de run_wave.py.
    Construye payload WhatsApp Business para un turno sintético.
    """
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
                                    "profile": {"name": "SyntheticHybrid"},
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


async def send_turn(
    client: httpx.AsyncClient,
    url: str,
    token: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Trasplante verbatim de run_wave.py.
    POST con X-Task-Token y retry exponencial suave.
    """
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


def tag_synthetic_docs(
    phones: List[str],
    run_id: str,
    project: str = "tiendalasmotos",
) -> None:
    """
    Trasplante verbatim de run_wave.py (arm_label fijado a 'hybrid').
    Escribe en la colección prospectos, NO en llm_runtime.
    """
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
                "synthetic_arm": "hybrid",
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


def _read_prospect_doc(phone: str, project: str = "tiendalasmotos") -> Optional[Dict[str, Any]]:
    """Lectura read-only del doc prospecto para fail-fast de embudo."""
    if firestore is None:
        return None
    db = firestore.Client(project=project)
    doc = db.collection("prospectos").document(f"+{phone}").get()
    return dict(doc.to_dict() or {}) if doc.exists else None


def _read_chat_history(
    phone: str,
    project: str = "tiendalasmotos",
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Lectura read-only del historial prospectos/{phone}/historial para evidencia física del link."""
    if firestore is None:
        return []
    db = firestore.Client(project=project)
    docs = list(
        db.collection("prospectos")
        .document(f"+{phone}")
        .collection("historial")
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    return [dict(d.to_dict() or {}) for d in reversed(docs)]


def script_presented_in_history(history: List[Dict[str, Any]]) -> bool:
    """True si un mensaje del bot (role='model') contiene el link de privacidad."""
    for msg in history:
        role = str(msg.get("role", "")).lower()
        content = str(msg.get("content", "")).lower()
        if role == "model" and PRIVACY_LINK_SNIPPET in content:
            return True
    return False


def _delete_doc_recursively(doc_ref) -> int:
    """Borra un documento de Firestore y todas sus subcolecciones anidadas."""
    deleted = 1
    for coll in doc_ref.collections():
        _delete_collection_recursively(coll)
    doc_ref.delete()
    return deleted


def _delete_collection_recursively(coll_ref, batch_size: int = 50) -> int:
    """Borra recursivamente todos los documentos de una colección."""
    deleted = 0
    docs = list(coll_ref.limit(batch_size).stream())
    while docs:
        for doc in docs:
            deleted += _delete_doc_recursively(doc.reference)
        docs = list(coll_ref.limit(batch_size).stream())
    return deleted


def preclean_synthetic_docs(phones: List[str], project: str = "tiendalasmotos") -> None:
    """Borra los docs prospectos de los teléfonos de esta corrida antes de inyectar."""
    if firestore is None:
        return
    db = firestore.Client(project=project)
    coll = db.collection("prospectos")
    for phone in phones:
        doc_ref = coll.document(f"+{phone}")
        if doc_ref.get().exists:
            print(f"🧹 Preclean borrando +{phone}...")
            _delete_doc_recursively(doc_ref)


def assert_habeas_accepted_sent(phone: str, project: str, scenario_id: str) -> None:
    """Fail-fast: el script legal con link debe haber sido emitido tras la aceptación.

    OBL-3 (Retry defensivo): si el bot efectivamente presentó el link físico en el
    historial pero el latch `habeas_data_accepted_sent` aún no se cerró, esperamos
    hasta 10 s antes de declarar E1. Este retry es un workaround defensivo por
    latencia de persistencia, NO una causa raíz, y solo aplica cuando hay evidencia
    física del script. Si el bot no presentó el link, fallamos inmediatamente.
    """
    deadline = time.monotonic() + 10.0
    last_value: Any = None
    while time.monotonic() < deadline:
        doc = _read_prospect_doc(phone, project)
        if not doc:
            raise SystemExit(f"❌ fail-fast ({scenario_id}): doc +{phone} no existe tras aceptación")
        last_value = doc.get("habeas_data_accepted_sent")
        if last_value:
            print(f"✅ fail-fast ({scenario_id}): habeas_data_accepted_sent=True")
            return
        # Workaround defensivo (OBL-3): solo reintentar si hay evidencia física del link.
        history = _read_chat_history(phone, project)
        if not script_presented_in_history(history):
            break
        print(f"  ⏳ Retry defensivo ({scenario_id}): script presentado, latch pendiente...")
        time.sleep(2.0)
    raise SystemExit(
        f"❌ fail-fast ({scenario_id}): script legal no emitido (E1) — "
        f"habeas_data_accepted_sent={last_value}"
    )


def assert_script_presented(
    phone: str,
    project: str,
    scenario_id: str,
    timeout: float = 30.0,
) -> None:
    """Fail-fast (OBL-1 Ley 1581): el bot debe haber presentado el link de privacidad
    antes de que la sonda envíe el turno de aceptación. Sin link → abort
    ROJO_NO_SCRIPT_PRESENTED.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        history = _read_chat_history(phone, project)
        if script_presented_in_history(history):
            print(f"✅ fail-fast ({scenario_id}): link de privacidad presentado por el bot")
            return
        time.sleep(2.0)
    raise SystemExit(
        f"❌ ROJO_NO_SCRIPT_PRESENTED ({scenario_id}): el bot no presentó el link "
        f"de privacidad ({PRIVACY_LINK}) antes del turno de aceptación."
    )


def assert_phase3_seen(
    service_name: str,
    project: str,
    after: datetime,
    scenario_id: str,
    timeout: float = FAILFAST_PHASE3_TIMEOUT,
) -> None:
    """Fail-fast: tras el turno de identidad el siguiente route debe estar en PHASE_3."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        entries = query_cloud_logging(
            service_name,
            project,
            after,
            datetime.now(timezone.utc),
            "HYBRID ROUTE",
            limit=200,
        )
        events = _extract_route_events(entries)
        if any(e["fase"] == "PHASE_3_CREDIT_PROFILING" for e in events):
            print(f"✅ fail-fast ({scenario_id}): PHASE_3_CREDIT_PROFILING detectado")
            return
        time.sleep(2.0)
    raise SystemExit(
        f"❌ fail-fast ({scenario_id}): PHASE_3_CREDIT_PROFILING no aparece tras turno identidad (E1/E2)"
    )


def _gcloud_ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def query_cloud_logging(
    service_name: str,
    project: str,
    start: datetime,
    end: datetime,
    substring: str,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    """Query Cloud Logging por substring dentro de ventana timestamp."""
    filter_query = (
        f'resource.type="cloud_run_revision" '
        f'AND resource.labels.service_name="{service_name}" '
        f'AND timestamp>="{_gcloud_ts(start)}" '
        f'AND timestamp<="{_gcloud_ts(end)}" '
        f'AND textPayload:"{substring}"'
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
        output = subprocess.check_output(cmd, text=True, stderr=subprocess.PIPE, timeout=60)
        if not output.strip():
            return []
        return json.loads(output)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Cloud Logging query failed: {exc.stderr[:500]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Cloud Logging query timed out") from exc


def _read_runtime_flags(project: str) -> Dict[str, Any]:
    if firestore is None:
        raise RuntimeError("google.cloud.firestore no disponible; no se pueden leer flags")
    db = firestore.Client(project=project)
    doc = db.collection("llm_runtime").document("global").get()
    if doc.exists:
        return dict(doc.to_dict() or {})
    return {}


def assert_flags(project: str, label: str) -> None:
    """Solo lectura. Aborta ante deriva (COND-1)."""
    flags = _read_runtime_flags(project)
    hybrid = bool(flags.get("hybrid_routing_enabled", False))
    qwen = bool(flags.get("qwen_enabled", False))
    if not hybrid or qwen:
        raise SystemExit(
            f"❌ [{label}] Flags inválidos: hybrid_routing_enabled={hybrid} "
            f"qwen_enabled={qwen}. Abortado por COND-1 (sin mutación)."
        )
    print(f"✅ [{label}] Flags estables: hybrid_routing_enabled=true qwen_enabled=false")


def _extract_route_events(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for entry in entries:
        text = (entry.get("textPayload") or "") + (entry.get("jsonPayload", {}).get("message") or "")
        m = HYBRID_ROUTE_RE.search(text)
        if not m:
            continue
        provider, reason, captured, siguiente, fase = m.groups()
        try:
            captured_int = int(captured)
        except Exception:
            captured_int = -1
        events.append(
            {
                "provider": provider,
                "reason": reason,
                "captured_count": captured_int,
                "siguiente": siguiente,
                "fase": fase,
                "timestamp": entry.get("timestamp"),
            }
        )
    return events


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def verify_session_routes(
    session_idx: int,
    all_entries: List[Dict[str, Any]],
    start: datetime,
    end: datetime,
    phone: str,
    project: str,
) -> Dict[str, Any]:
    """Verifica el núcleo por estado del embudo, histograma, failovers y cierre real."""
    window_entries = [
        e
        for e in all_entries
        if start <= _parse_ts(e.get("timestamp", "1970-01-01T00:00:00Z")) < end
    ]

    route_events = _extract_route_events(window_entries)
    # Orden cronológico ascendente (gcloud devuelve newest-first)
    route_events.sort(key=lambda e: _parse_ts(e.get("timestamp", "1970-01-01T00:00:00Z")))

    # Eventos de failover en esta ventana
    failover_entries = [
        e for e in window_entries
        if "failover a Gemini" in (e.get("textPayload") or "")
    ]

    backstop = sum(1 for e in window_entries if "[HYBRID BACKSTOP" in (e.get("textPayload") or ""))
    qwen = sum(1 for e in window_entries if "QWEN ROUTE" in (e.get("textPayload") or ""))
    dual = sum(1 for e in window_entries if "DUAL FAILOVER" in (e.get("textPayload") or ""))
    route_fallback = sum(1 for e in window_entries if "route_fallback_gemini" in (e.get("textPayload") or ""))

    # E3 — errores NoneType.strip en extracción/summary
    none_type_errors = sum(
        1
        for e in window_entries
        if "Error generating summary" in (e.get("textPayload") or "")
        and "NoneType" in (e.get("textPayload") or "")
    )

    # [BOT-BUILD-E2-FIX-107] F-D: errores de summary con mensaje vacío o
    # TimeoutError (type=... en el log tras F-A). Antes de F-A el mensaje
    # terminaba en ':'; después contiene 'type=TimeoutError'.
    summary_timeout_errors = sum(
        1
        for e in window_entries
        if "Error generating summary" in (e.get("textPayload") or "")
        and (
            "type=" in (e.get("textPayload") or "")
            or (e.get("textPayload") or "").rstrip().endswith(":")
        )
    )

    # Clasificar failovers por timestamp (±2s) contra el evento route de la misma llamada
    core_failovers = 0
    aux_failovers = 0
    unclassified_failovers = 0
    for fo in failover_entries:
        fo_ts = _parse_ts(fo.get("timestamp", "1970-01-01T00:00:00Z"))
        matched: Optional[Dict[str, Any]] = None
        for ev in route_events:
            ev_ts = _parse_ts(ev.get("timestamp", "1970-01-01T00:00:00Z"))
            if abs((fo_ts - ev_ts).total_seconds()) <= 2.0:
                matched = ev
                break
        if matched is None:
            unclassified_failovers += 1
            continue
        if matched["reason"] in {"frontera_turno_7_matriz", "cierre_fase_completo"} or CORE_PROFILING_RE.match(matched["reason"]):
            core_failovers += 1
        else:
            aux_failovers += 1

    # Verificación estado-basada del núcleo
    errors: List[str] = []
    profiling_turns: List[Dict[str, Any]] = []
    frontera_events: List[Dict[str, Any]] = []
    cierre_events: List[Dict[str, Any]] = []
    captured_progression: List[int] = []

    for ev in route_events:
        fase = ev.get("fase")
        siguiente = ev.get("siguiente")
        captured = ev.get("captured_count", -1)
        provider = ev.get("provider")
        reason = ev.get("reason")

        if fase != "PHASE_3_CREDIT_PROFILING":
            continue

        if siguiente == "COMPLETO":
            cierre_events.append(ev)
            if provider != "gemini" or reason != "cierre_fase_completo":
                errors.append(f"cierre_fase_completo con provider={provider}/reason={reason}")
            if captured != 8:
                errors.append(f"cierre_fase_completo con captured_count={captured} (esperado 8)")
        elif captured >= 7:
            frontera_events.append(ev)
            if provider != "gemini" or reason != "frontera_turno_7_matriz":
                errors.append(f"frontera_turno_7_matriz con provider={provider}/reason={reason}")
        elif captured >= 0:
            profiling_turns.append(ev)
            expected_reason = f"turno_{captured + 1}_profiling"
            if provider != "deepseek" or reason != expected_reason:
                errors.append(
                    f"turno de profiling captured={captured}: provider={provider}/reason={reason} "
                    f"(esperado deepseek/{expected_reason})"
                )
            captured_progression.append(captured)
        else:
            errors.append(f"evento PHASE_3 con captured_count inválido: {captured}")

    if not profiling_turns:
        errors.append("no hay turnos de profiling deepseek en PHASE_3")
    elif len(profiling_turns) < 6:
        errors.append(f"esperaba >=6 turnos de profiling deepseek, hay {len(profiling_turns)}")

    if captured_progression:
        if captured_progression[0] != 0:
            errors.append(f"el primer captured_count de profiling no es 0: {captured_progression[0]}")
        if captured_progression != sorted(captured_progression):
            errors.append(f"captured_count de profiling no es no-decreciente: {captured_progression}")
        if captured_progression[-1] < 5:
            errors.append(f"captured_count no progresa lo suficiente: {captured_progression[-1]} (esperado >=5)")

    warnings: List[str] = []

    if not cierre_events:
        errors.append("falta cierre_fase_completo (gemini)")
    else:
        last_cierre_ts = max(_parse_ts(e["timestamp"]) for e in cierre_events)
        for ev in profiling_turns + frontera_events:
            if _parse_ts(ev["timestamp"]) > last_cierre_ts:
                errors.append("cierre_fase_completo no es el ultimo evento del nucleo")

    cierre_complete = any(e.get("captured_count") == 8 for e in cierre_events)
    if not frontera_events:
        if not cierre_complete and captured_progression and captured_progression[-1] < 7:
            errors.append("falta frontera_turno_7_matriz y captured final <7; matriz incompleta")
        elif cierre_complete:
            warnings.append("frontera_turno_7_matriz omitida; matriz completa por cierre_fase_completo (8 campos)")

    # Asercion de cierre real: score_resultado persistido en Firestore
    score_resultado: Optional[Any] = None
    doc = _read_prospect_doc(phone, project)
    if doc:
        score_resultado = doc.get("score_resultado")
    if score_resultado is None:
        errors.append("score_resultado no esta presente en el doc prospecto (calculate_credit_score no ejecuto)")
    else:
        print(f"✅ Sesion {session_idx}: score_resultado={score_resultado}")

    unknown = [ev["reason"] for ev in route_events if not _is_whitelisted_reason(ev["reason"])]
    if unknown:
        errors.append(f"razones no esperadas: {sorted(set(unknown))}")

    if backstop:
        errors.append(f"HYBRID BACKSTOP detectado: {backstop}")
    if qwen:
        errors.append(f"QWEN ROUTE detectado: {qwen}")
    if dual:
        errors.append(f"DUAL FAILOVER detectado: {dual}")
    if route_fallback:
        errors.append(f"route_fallback_gemini detectado: {route_fallback}")
    if core_failovers:
        errors.append(f"failover a Gemini en llamadas del nucleo: {core_failovers}")
    if unclassified_failovers:
        errors.append(f"failovers no clasificados: {unclassified_failovers}")

    if aux_failovers:
        warnings.append(f"failover a Gemini en llamadas auxiliares: {aux_failovers}")
    if none_type_errors:
        warnings.append(f"errores NoneType.strip en extraccion/summary: {none_type_errors}")
    if summary_timeout_errors:
        warnings.append(f"errores de summary con mensaje vacio/TimeoutError: {summary_timeout_errors}")
    if not frontera_events and captured_progression and captured_progression[-1] >= 7:
        warnings.append("frontera_turno_7_matriz omitida por salto de captured_count (6->8); cierre sigue siendo Gemini")

    verdict = "ROJO" if errors else "VERDE"

    return {
        "session_idx": session_idx,
        "route_events": len(route_events),
        "histogram": route_events,
        "profiling_count": len(profiling_turns),
        "frontera_count": len(frontera_events),
        "cierre_count": len(cierre_events),
        "captured_progression": captured_progression,
        "core_failovers": core_failovers,
        "aux_failovers": aux_failovers,
        "none_type_errors": none_type_errors,
        "summary_timeout_errors": summary_timeout_errors,
        "backstop": backstop,
        "qwen": qwen,
        "dual": dual,
        "route_fallback": route_fallback,
        "score_resultado": score_resultado,
        "errors": errors,
        "warnings": warnings,
        "verdict": verdict,
    }



def verify_paso2_session(
    session_idx: int,
    all_route_entries: List[Dict[str, Any]],
    start: datetime,
    end: datetime,
    phone: str,
    project: str,
    service_name: str,
) -> Dict[str, Any]:
    """Verifica que PASO 2 (simulación ciega / excepción de crédito) entregue la cuota JSON sin backstop."""
    errors: List[str] = []
    warnings: List[str] = []

    # Bug A: parsear entradas crudas de Cloud Logging antes de ponerlas en el histograma.
    raw_window = [
        e
        for e in all_route_entries
        if start <= _parse_ts(e.get("timestamp", "1970-01-01T00:00:00Z")) < end
    ]
    raw_window.sort(key=lambda e: _parse_ts(e.get("timestamp", "1970-01-01T00:00:00Z")))
    route_events = _extract_route_events(raw_window)

    backstop_entries = query_cloud_logging(
        service_name, project, start, end, "[HYBRID BACKSTOP ASYNC]", limit=100
    )
    premature_none = 0
    for entry in backstop_entries:
        text = (entry.get("textPayload") or "") + (entry.get("jsonPayload", {}).get("message") or "")
        m = HYBRID_BACKSTOP_RE.search(text)
        if not m:
            continue
        reason, captured, siguiente, _depth = m.groups()
        if reason == "backstop_tool_prematuro" and captured in ("0", "-1") and (not siguiente or siguiente == "None"):
            premature_none += 1
    if premature_none:
        errors.append(f"backstop_tool_prematuro stripó {premature_none} llamada(s) PASO 2 (captured=0/None)")

    # Bug B: la simulación ciega de PASO 2 no persiste score_resultado; verificamos el egreso real.
    phone_entries = query_cloud_logging(service_name, project, start, end, phone, limit=200)
    texts = [(e.get("textPayload") or "") for e in phone_entries]
    canonical_hits = sum(1 for t in texts if "¿Me confirmas el dato que falta?" in t)
    if canonical_hits:
        errors.append(f"egreso contiene la pregunta canónica del backstop ({canonical_hits} veces); la cuota JSON no llegó")

    cuota_present = False
    for t in texts:
        low = t.lower()
        if "$" in low and any(k in low for k in ("cuota", "meses", "enganche", "inicial", "financi")):
            cuota_present = True
            break
    if not cuota_present:
        errors.append("egreso no contiene cuota/simulación de crédito (modelo no invocó calculate_credit_score o devolvió solo ficha)")

    score_resultado: Optional[Any] = None
    doc = _read_prospect_doc(phone, project)
    if doc:
        score_resultado = doc.get("score_resultado")
    if score_resultado is None:
        warnings.append("score_resultado no está presente (esperado en simulación ciega de PASO 2)")
    else:
        print(f"✅ Sesión {session_idx}: score_resultado={score_resultado}")

    if not route_events:
        errors.append("no se encontraron eventos HYBRID ROUTE en la ventana")

    verdict = "ROJO" if errors else "VERDE"

    return {
        "session_idx": session_idx,
        "route_events": len(route_events),
        "histogram": route_events,
        "profiling_count": 0,
        "frontera_count": 0,
        "cierre_count": 0,
        "captured_progression": [],
        "core_failovers": 0,
        "aux_failovers": 0,
        "none_type_errors": 0,
        "backstop": len(backstop_entries),
        "qwen": 0,
        "dual": 0,
        "route_fallback": 0,
        "score_resultado": score_resultado,
        "errors": errors,
        "warnings": warnings,
        "verdict": verdict,
    }

async def run_session(
    session_idx: int,
    scenario: Dict[str, Any],
    run_id: str,
    config: Dict[str, Any],
    token: str,
    dry_run: bool,
    project: str,
    service_name: str,
) -> Dict[str, Any]:
    """Ejecuta una sesión MATRIZ secuencial con fail-fast de embudo."""
    phone_number_id = config["meta"]["beta_phone_number_id"]
    base_url = config["meta"]["beta_base_url"]
    url = base_url.rstrip("/") + TASK_PROCESSOR_PATH
    phone = f"573770099{session_idx:02d}"
    scenario_id = scenario["id"]

    result: Dict[str, Any] = {
        "session_idx": session_idx,
        "scenario_id": scenario_id,
        "phone": phone,
        "turns": [],
        "started_at": now_iso(),
    }

    print(f"\n🚀 Sesión {session_idx} ({scenario_id}) → {phone}")
    async with httpx.AsyncClient() as client:
        for turn_idx, turn in enumerate(scenario["turns"]):
            msg_id = f"hybm_{run_id}_s{session_idx}_t{turn_idx}"
            payload = build_payload(phone_number_id, phone, msg_id, turn, {})

            if dry_run:
                print(f"  [DRY-RUN] turno {turn_idx}: {turn.get('text', turn.get('type'))[:60]}...")
                result["turns"].append({
                    "turn_idx": turn_idx,
                    "msg_id": msg_id,
                    "dry_run": True,
                    "payload_preview": str(build_payload(phone_number_id, phone, msg_id, turn, {}))[:200],
                })
                continue

            # OBL-1 (Ley 1581): antes de enviar el turno de aceptación, exigir
            # evidencia física de que el bot presentó el link de privacidad.
            if (
                turn_idx == HABEAS_ACCEPT_TURN_IDX
                and scenario.get("type") == "matriz_full"
            ):
                assert_script_presented(phone, project, scenario_id)

            # Marca de tiempo para fail-fast PHASE_3 (ventana propia de este turno)
            turn_query_start = datetime.now(timezone.utc)

            payload = build_payload(phone_number_id, phone, msg_id, turn, {})
            turn_result = await send_turn(client, url, token, payload)
            turn_result["msg_id"] = msg_id
            turn_result["turn_idx"] = turn_idx
            # OBL-2: response_body se vuelca en el log de resultados para cierre de
            # la brecha entre ruteo (HYBRID ROUTE) y contenido real de la respuesta.
            result["turns"].append(turn_result)

            if turn_result["error"]:
                print(f"  ❌ Turno {turn_idx} falló: {turn_result['error']}")
                break
            print(f"  ✅ Turno {turn_idx}: HTTP {turn_result['status_code']} en {turn_result['latency_ms']}ms")

            # Fail-fast de embudo (directiva del ticket)
            if turn_idx == HABEAS_ACCEPT_TURN_IDX:
                assert_habeas_accepted_sent(phone, project, scenario_id)
            if turn_idx == IDENTITY_TURN_IDX:
                assert_phase3_seen(service_name, project, turn_query_start, scenario_id)

            if turn_idx < len(scenario["turns"]) - 1:
                await asyncio.sleep(TURN_GAP_S)

    result["finished_at"] = now_iso()
    return result


def render_markdown(report: Dict[str, Any]) -> str:
    lines = [
        f"# Sonda híbrida MATRIZ — {report['run_id']}",
        "",
        f"- **Ejecutado:** {report['generated_at']}",
        f"- **dry_run:** {report['dry_run']}",
        f"- **preclean:** {report.get('preclean', 'N/A')}",
        f"- **Veredicto global:** {report['global_verdict']}",
        f"- **Flags pre/post:** hybrid=true qwen=false ({report['flag_check']})",
        "",
        "## Resumen por sesión",
        "",
        "| Sesión | Escenario | Profiling | Frontera | Cierre | CoreFail | AuxFail | NoneType | SummaryTimeout | Errores | Veredicto |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for s in report["sessions"]:
        lines.append(
            f"| {s['session_idx']} | {s['scenario_id']} | {s.get('profiling_count', 0)} | "
            f"{s.get('frontera_count', 0)} | {s.get('cierre_count', 0)} | "
            f"{s.get('core_failovers', 0)} | {s.get('aux_failovers', 0)} | "
            f"{s.get('none_type_errors', 0)} | {s.get('summary_timeout_errors', 0)} | "
            f"{len(s['errors'])} | {s['verdict']} |"
        )
    lines.append("")
    for s in report["sessions"]:
        lines.append(f"### Sesión {s['session_idx']} — {s['scenario_id']}")
        lines.append(f"- Teléfono: `{s['phone']}`")
        lines.append(f"- captured_progression: `{s.get('captured_progression', [])}`")
        lines.append(f"- score_resultado: `{s.get('score_resultado')}`")
        lines.append(f"- HYBRID BACKSTOP: {s.get('backstop', 0)} | QWEN ROUTE: {s.get('qwen', 0)} | DUAL FAILOVER: {s.get('dual', 0)} | route_fallback: {s.get('route_fallback', 0)}")
        lines.append(f"- core_failovers: {s.get('core_failovers', 0)} | aux_failovers: {s.get('aux_failovers', 0)}")
        lines.append(f"- Errores NoneType.strip: {s.get('none_type_errors', 0)} | summary timeout: {s.get('summary_timeout_errors', 0)}")
        if s["errors"]:
            lines.append("- **Errores:**")
            for err in s["errors"]:
                lines.append(f"  - {err}")
        if s.get("warnings"):
            lines.append("- **Advertencias:**")
            for warn in s["warnings"]:
                lines.append(f"  - {warn}")
        hist = s.get("histogram", [])
        if hist:
            lines.append(f"- **Histograma ({len(hist)} eventos):**")
            lines.append("  | provider | reason | captured | siguiente | fase | timestamp |")
            lines.append("  |---|---|---|---|---|---|")
            render_warnings: List[str] = []
            for ev in hist:
                provider = ev.get("provider", "unknown")
                reason = ev.get("reason", "unknown")
                captured = ev.get("captured_count", "?")
                siguiente = ev.get("siguiente", "")
                fase = ev.get("fase", "?")
                ts = ev.get("timestamp", "?")
                if provider == "unknown" or reason == "unknown":
                    render_warnings.append(f"evento de histograma incompleto: {ev}")
                lines.append(
                    f"  | {provider} | {reason} | {captured} | {siguiente} | {fase} | {ts} |"
                )
            if render_warnings:
                lines.append("- **Advertencias de histograma:**")
                for w in render_warnings:
                    lines.append(f"  - {w}")
        lines.append("")
    if report.get("global_errors"):
        lines.append("## Errores globales")
        for err in report["global_errors"]:
            lines.append(f"- {err}")
    if report.get("global_warnings"):
        lines.append("## Advertencias globales")
        for warn in report["global_warnings"]:
            lines.append(f"- {warn}")
    return "\n".join(lines)


async def _run_sessions(
    scenarios: List[Dict[str, Any]],
    run_id: str,
    config: Dict[str, Any],
    token: str,
    dry_run: bool,
    project: str,
    service_name: str,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for idx, scenario in enumerate(scenarios, start=1):
        result = await run_session(idx, scenario, run_id, config, token, dry_run, project, service_name)
        results.append(result)
        if not dry_run and idx < len(scenarios):
            print(f"⏳ Settle inter-sesión {INTER_SESSION_SETTLE_S}s...")
            await asyncio.sleep(INTER_SESSION_SETTLE_S)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Sonda MATRIZ híbrida-consciente F5")
    parser.add_argument("--run-id", type=str, required=True, help="ID de la corrida (ej: 2026-08-24T10-00)")
    parser.add_argument(
        "--scenarios",
        type=str,
        default=",".join(DEFAULT_SCENARIOS),
        help="IDs de escenarios MATRIZ separados por coma",
    )
    parser.add_argument("--project", type=str, default="tiendalasmotos", help="GCP project")
    parser.add_argument("--service", type=str, default="bot-tiendalasmotos-beta", help="Cloud Run service")
    parser.add_argument("--settle", type=int, default=int(SETTLE_S), help="Segundos de settle antes de query logs")
    parser.add_argument("--dry-run", action="store_true", help="Valida payloads sin enviar ni tocar logs")
    parser.add_argument(
        "--preclean",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Borrar docs prospectos sintéticos antes de inyectar (default: on)",
    )
    parser.add_argument(
        "--fault-injection",
        action="store_true",
        help="[RESERVADO] No implementado en FASE 1",
    )
    args = parser.parse_args()

    if args.fault_injection:
        print("⚠️  --fault-injection está reservado para FASE posterior; se ignora.")

    corpus_path = SCRIPT_DIR / "corpus.yaml"
    config = load_corpus(corpus_path)
    scenarios_all = {sc["id"]: sc for sc in config["scenarios"]}
    scenario_ids = [s.strip() for s in args.scenarios.split(",")]
    selected = []
    for sid in scenario_ids:
        sc = scenarios_all.get(sid)
        if not sc:
            raise SystemExit(f"Escenario no encontrado en corpus: {sid}")
        selected.append(sc)

    if len(selected) != 2:
        print(f"⚠️  Se seleccionaron {len(selected)} escenarios; el ticket pide 2 sesiones MATRIZ.")

    dry_run = args.dry_run
    token = os.getenv("WEBHOOK_VERIFY_TOKEN", "dry-run-token") if dry_run else load_env_or_die("WEBHOOK_VERIFY_TOKEN")

    # Teléfonos deterministas de la corrida
    phones = [f"573770099{i:02d}" for i in range(1, len(selected) + 1)]

    global_errors: List[str] = []
    global_warnings: List[str] = []
    flag_check = "skipped (dry-run)"

    if not dry_run:
        print("🔎 Pre-vuelo: aserción de flags (solo lectura)...")
        try:
            assert_flags(args.project, "PRE")
            flag_check = "OK"
        except SystemExit as exc:
            print(str(exc))
            return 1

        if args.preclean:
            print(f"🧹 Preclean: borrando docs sintéticos de {phones}...")
            try:
                preclean_synthetic_docs(phones, args.project)
            except Exception as exc:
                global_errors.append(f"preclean falló: {exc}")
                print(f"⚠️  {exc}")

        print(f"🔎 Quiesce check: últimos {QUIESCE_MINUTES} min sin HYBRID ROUTE...")
        t0 = datetime.now(timezone.utc)
        quiesce_start = t0 - timedelta(minutes=QUIESCE_MINUTES)
        quiesce_entries = query_cloud_logging(
            args.service, args.project,
            quiesce_start,
            t0,
            "HYBRID ROUTE",
            limit=10,
        )
        if quiesce_entries:
            msg = f"quiesce check: {len(quiesce_entries)} eventos HYBRID ROUTE en los últimos {QUIESCE_MINUTES} minutos"
            print(f"⚠️  {msg}")
            if len(quiesce_entries) > 20:
                global_errors.append(msg)
            else:
                global_warnings.append(msg)

    print(f"\n🧪 run_id={args.run_id} dry_run={dry_run} preclean={args.preclean} escenarios={[s['id'] for s in selected]}")
    session_start = datetime.now(timezone.utc)

    raw_sessions = asyncio.run(
        _run_sessions(selected, args.run_id, config, token, dry_run, args.project, args.service)
    )

    if not dry_run:
        print(f"⏳ Settle {args.settle}s para propagación de logs...")
        time.sleep(args.settle)
    session_end = datetime.now(timezone.utc)

    sessions_report: List[Dict[str, Any]] = []
    if not dry_run:
        print("📡 Query Cloud Logging (HYBRID ROUTE)...")
        all_route_entries = query_cloud_logging(
            args.service, args.project, session_start, session_end, "HYBRID ROUTE", limit=2000
        )
        print(f"   {len(all_route_entries)} entradas HYBRID ROUTE")

        for idx, raw in enumerate(raw_sessions):
            s_start = _parse_ts(raw["started_at"])
            s_end = _parse_ts(raw_sessions[idx + 1]["started_at"]) if idx + 1 < len(raw_sessions) else session_end
            scenario = selected[idx]
            if scenario.get("type") == "paso2_cuota":
                s_report = verify_paso2_session(
                    idx + 1, all_route_entries, s_start, s_end, raw["phone"], args.project, args.service
                )
            else:
                s_report = verify_session_routes(
                    idx + 1, all_route_entries, s_start, s_end, raw["phone"], args.project
                )
            s_report["scenario_id"] = raw["scenario_id"]
            s_report["phone"] = raw["phone"]
            sessions_report.append(s_report)
    else:
        for idx, raw in enumerate(raw_sessions):
            sessions_report.append({
                "session_idx": idx + 1,
                "scenario_id": raw["scenario_id"],
                "phone": raw["phone"],
                "route_events": 0,
                "histogram": [],
                "profiling_count": 0,
                "frontera_count": 0,
                "cierre_count": 0,
                "captured_progression": [],
                "core_failovers": 0,
                "aux_failovers": 0,
                "none_type_errors": 0,
                "backstop": 0,
                "qwen": 0,
                "dual": 0,
                "route_fallback": 0,
                "score_resultado": None,
                "errors": [],
                "warnings": [],
                "verdict": "VERDE (dry-run)",
            })

    if not dry_run:
        print("🔎 Post-vuelo: aserción de flags (solo lectura)...")
        try:
            assert_flags(args.project, "POST")
        except SystemExit as exc:
            global_errors.append("post-flag assertion failed")
            print(str(exc))

    if not dry_run:
        print(f"🏷️  Etiquetando {len(phones)} docs sintéticos...")
        try:
            tag_synthetic_docs(phones, f"f5-hybrid-{args.run_id}", project=args.project)
        except Exception as exc:
            global_errors.append(f"tag_synthetic_docs falló: {exc}")
            print(f"⚠️  {exc}")

    verdicts = [s["verdict"] for s in sessions_report]
    if any(v.startswith("ROJO") for v in verdicts) or global_errors:
        global_verdict = "ROJO"
    elif any(v.startswith("AMARILLO") for v in verdicts):
        global_verdict = "AMARILLO"
    else:
        global_verdict = "VERDE"

    report = {
        "run_id": args.run_id,
        "dry_run": dry_run,
        "preclean": args.preclean,
        "generated_at": now_iso(),
        "flag_check": flag_check,
        "global_verdict": global_verdict,
        "global_errors": global_errors,
        "global_warnings": global_warnings,
        "sessions": sessions_report,
        "raw_sessions": raw_sessions,
    }

    run_dir = RESULTS_DIR / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    json_path = run_dir / "hybrid_probe.json"
    md_path = run_dir / "hybrid_probe.md"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(render_markdown(report))

    print(f"\n💾 {json_path}")
    print(f"📄 {md_path}")
    print(f"🚦 Veredicto global: {global_verdict}")
    return 0 if global_verdict == "VERDE" else 1


if __name__ == "__main__":
    sys.exit(main())
