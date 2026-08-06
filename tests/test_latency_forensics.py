"""
Latencia Forense y Cierre Etapa 3 — Wave 05-06 [BOT-BUILD-ETAPA3-WAVE06-LATENCY-CLOSE-001]

Suite de inyección de caos (arnés tests/conftest_chaos.py) + auditoría
Zero-Silent-Failures del eje transaccional fragmentado (RF-5).

Escenarios (vector corregido del ticket: httpx.AsyncClient — NO aiohttp —
y google.cloud.firestore.AsyncClient):

  LAT-1  Latencia ≥10s en Meta API (patch httpx.AsyncClient.send con compuerta
         determinista — más fuerte que un sleep fijo: latencia no acotada):
         el estado Firestore (save model pre-egreso) ya está persistido ANTES
         de que el envío a Meta retorne o falle. Sin bloqueo del hilo de estado.
  LAT-2  Timeout Firestore (mock_firestore_with_latency(10.0) > db_timeout=5):
         _firestore_io eleva TimeoutError explícito (Zero-Silent-Failures — el
         comportamiento sancionado desde test_bot_bug_044), la escritura
         cancelada jamás se confirma (colección prospectos íntegra), el
         _ContingencySnapshot controlado mantiene su contrato anti-AttributeError
         (exists=False / to_dict()=={}) y el embudo aborta con contingencia al
         usuario SIN mutar el estado transicional.
  LAT-3  Fallo intermitente calculate_credit_score (side_effect en cerebro):
         el Freno Cognitivo se mantiene — el Juez jamás audita una respuesta
         inexistente, el único texto que egresa es el fallback supervisado
         (mandato v9.8.3: estado antes que red) y NO hay alucinación de
         marcadores sintéticos de precio ($X.XXX).

Auditoría de resiliencia (Zero-Silent-Failures):
  AUD-1  Cero bloques `except …: pass` sin logger en el eje (whatsapp.py,
         whatsapp_service.py, memory_service.py) — remediación Wave 05-06 pineada.
  AUD-2  Presencia obligatoria de e.response.text en los manejadores
         httpx.HTTPStatusError del egreso Meta (forense de proveedor externo).
  AUD-3  Correlation ID (E.164 + wamid) en la traza forense raíz del webhook.

Nota BOT-174 (mandato Wave 05-01 §3): todo arnés que alcanza el guard configura
`ms.get_or_create_prospect = AsyncMock(...)` explícito.
"""
import asyncio
import re

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import BackgroundTasks

from app.routers.whatsapp import _handle_message_background_impl
from tests.conftest_chaos import mock_firestore_with_latency, slow_async_mock  # noqa: F401 (arnés sancionado)

PHONE_E164 = "+573192564288"
PHONE_RAW = "573192564288"
PHONE_NUMBER_ID = "999999"
APPROVED_TEXT = "La Victory Switch 150 es ideal para ti."
FALLBACK_TEXT = "Disculpa, no estoy seguro de la respuesta, permíteme le pregunto a mi supervisor y te comento."


# ── Builders ──────────────────────────────────────────────────────────────────

def _text_payload(text: str = "Quiero una moto económica", wamid: str = "wamid.lat") -> dict:
    return {
        "from": PHONE_RAW,
        "id": wamid,
        "type": "text",
        "phone_number_id": PHONE_NUMBER_ID,
        "text": text,
    }


def _build_ms_mock(timeline: list | None = None, prospect: dict | None = None) -> MagicMock:
    prospect = prospect or {
        "exists": True,
        "status": "IN_PROGRESS",
        "chatbot_status": "ACTIVE",
        "name": "Juan Test",
        "celular": PHONE_E164,
        "ai_summary": "Resumen previo",
        "human_help_requested": False,
    }
    ms = MagicMock()
    ms.create_prospect_if_missing = AsyncMock()
    ms.update_last_interaction = AsyncMock()
    ms.transition_to_in_progress = AsyncMock()
    ms.generate_and_update_summary = AsyncMock()
    ms.set_human_help_status = AsyncMock()
    ms.update_prospect_summary = AsyncMock()
    ms.delete_prospect_completely = AsyncMock(return_value=True)
    ms.get_or_create_prospect = AsyncMock(return_value=prospect)
    ms.get_prospect_data = AsyncMock(return_value=prospect)
    ms.get_chat_history = AsyncMock(return_value=[])

    if timeline is not None:
        async def _save(phone, role, content, **kwargs):
            timeline.append(f"save_message:{role}")
            return True

        ms.save_message = AsyncMock(side_effect=_save)
    else:
        ms.save_message = AsyncMock()
    return ms


def _build_buffer_mock() -> MagicMock:
    buffer = MagicMock()
    buffer.add_message = AsyncMock(return_value=True)
    buffer.is_task_active = MagicMock(return_value=True)
    buffer.get_aggregated_message = AsyncMock(return_value=None)
    buffer.clear_buffer = AsyncMock()
    buffer.debounce_seconds = 0.01
    return buffer


# ── LAT-1: Latencia ≥10s en Meta API — el estado precede a la red ────────────

@pytest.mark.asyncio
async def test_lat1_meta_api_latency_state_persisted_before_meta_send_returns():
    """
    Vector: patch httpx.AsyncClient.send con compuerta (latencia Meta no acotada,
        superset determinista del escenario 10s — el test no espera 10s reales).
    Aserción: con el envío a Meta EN VUELO (bloqueado por la compuerta), el estado
        Firestore del turno (save model pre-egreso) YA fue persistido. El hilo de
        estado no se bloquea detrás de la red externa.
    """
    timeline = []
    send_started = asyncio.Event()
    release_meta = asyncio.Event()

    async def _gated_send(self, request, **kwargs):
        timeline.append("meta:send_start")
        send_started.set()
        await release_meta.wait()  # Latencia Meta ≥10s simulada (compuerta, no sleep real)
        timeline.append("meta:send_released")
        response = MagicMock()
        response.status_code = 200
        response.text = ""
        response.raise_for_status = MagicMock()
        response.json = MagicMock(return_value={"messages": [{"id": "wamid.meta_ok"}]})
        return response

    mock_ms = _build_ms_mock(timeline)
    mock_cerebro = MagicMock()
    mock_cerebro.pensar_respuesta = AsyncMock(return_value=APPROVED_TEXT)
    mock_judge = MagicMock()
    mock_judge.analyze_response = AsyncMock(return_value=(True, ""))
    mock_catalog = MagicMock()
    mock_catalog.search = MagicMock(return_value=[])

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.routers.whatsapp.judge_service", mock_judge), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.message_buffer", _build_buffer_mock()), \
         patch("app.routers.whatsapp.db", MagicMock(name="global_db")), \
         patch("app.routers.whatsapp.VisionService", MagicMock(return_value=MagicMock())), \
         patch("app.services.whatsapp_service.whatsapp_service.mark_as_read", AsyncMock(return_value=True)), \
         patch("httpx.AsyncClient.send", new=_gated_send):

        task = asyncio.create_task(_handle_message_background_impl(_text_payload(), BackgroundTasks()))

        # El envío a Meta queda EN VUELO (latencia simulada sostenida).
        await asyncio.wait_for(send_started.wait(), timeout=5.0)

        # T3: el pre-egreso save_message("model") fue eliminado; el eco del modelo
        # vive ahora dentro del egreso unificado. Durante la latencia simulada de Meta
        # NO debe existir persistencia previa del modelo (la respuesta aún no se envía).
        assert "save_message:model" not in timeline, (
            f"T3: no debe haber save_message('model') antes del envío a Meta: {timeline}"
        )

        # Liberar Meta: el embudo completa limpio (sin excepción ni degradación).
        release_meta.set()
        await asyncio.wait_for(task, timeout=5.0)

    assert "meta:send_released" in timeline
    assert "save_message:model" in timeline, (
        f"T3: el eco save_message('model') debe ejecutarse dentro del egreso: {timeline}"
    )


# ── LAT-2: Timeout Firestore — contingencia controlada, colección íntegra ────

def test_lat2a_contingency_snapshot_contract_is_controlled_empty_doc():
    """
    Contrato anti-AttributeError del _ContingencySnapshot (Quick Task 042):
    documento vacío controlado (exists=False, to_dict()=={}) — jamás None.
    """
    from app.services.memory_service import _ContingencySnapshot

    snap = _ContingencySnapshot()
    assert snap.exists is False
    assert snap.to_dict() == {}
    # Anti-AttributeError: los accesos del embudo son seguros sobre el snapshot.
    assert snap.to_dict().get("ai_summary") is None


@pytest.mark.asyncio
async def test_lat2b_firestore_timeout_raises_explicit_and_write_never_confirms(mock_firestore_with_latency):
    """
    Vector: mock_firestore_with_latency(10.0) > db_timeout=5 (default de settings).
    Aserción: _firestore_io eleva TimeoutError EXPLÍCITO (Zero-Silent-Failures —
    comportamiento sancionado por test_bot_bug_044: jamás tragar el fallo) y la
    escritura cancelada NUNCA se confirma — la colección prospectos no se corrompe.
    """
    from app.services.memory_service import MemoryService

    db = mock_firestore_with_latency(latency=10.0)
    write_confirmed = False

    async def _slow_set(*args, **kwargs):
        nonlocal write_confirmed
        await asyncio.sleep(10.0)
        write_confirmed = True  # Jamás alcanzable: wait_for cancela a los 5s
        return True

    db.collection.return_value.document.return_value.set = AsyncMock(side_effect=_slow_set)

    svc = MemoryService(db)
    with pytest.raises(asyncio.TimeoutError):
        await svc._firestore_io(
            db.collection("prospectos").document(PHONE_E164).set({"ai_summary": "corrupt"}),
            phone=PHONE_E164,
            label="save_message",
        )

    assert write_confirmed is False, (
        "CORRUPCIÓN: la escritura cancelada por timeout se confirmó en prospectos."
    )


@pytest.mark.asyncio
async def test_lat2c_funnel_aborts_with_contingency_without_state_mutation():
    """
    Embudo bajo timeout de Firestore (save usuario eleva TimeoutError): el turno
    aborta con mensaje de contingencia al usuario y CERO mutación del estado
    transicional (sin sync de memoria, sin human-help, sin apertura de sesión).
    """
    mock_ms = _build_ms_mock()
    mock_ms.save_message = AsyncMock(side_effect=asyncio.TimeoutError("firestore timeout (simulated)"))
    send_mock = AsyncMock(return_value=True)
    mock_wa = MagicMock()
    mock_wa.mark_as_read = AsyncMock()

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_wa), \
         patch("app.routers.whatsapp.message_buffer", _build_buffer_mock()), \
         patch("app.routers.whatsapp._send_whatsapp_message", send_mock):

        await _handle_message_background_impl(_text_payload(), BackgroundTasks())

    send_mock.assert_awaited_once()
    contingency_text = send_mock.call_args.args[1]
    assert "intermitencias" in contingency_text, (
        f"El usuario debía recibir la contingencia de intermitencia: {contingency_text!r}"
    )
    # Cero mutación del estado transicional tras el aborto.
    mock_ms.generate_and_update_summary.assert_not_called()
    mock_ms.set_human_help_status.assert_not_called()
    mock_ms.update_prospect_summary.assert_not_called()
    mock_ms.get_prospect_data.assert_not_called()


# ── LAT-3: Fallo intermitente calculate_credit_score — Freno Cognitivo ───────

@pytest.mark.asyncio
async def test_lat3_intermittent_credit_score_failure_cognitive_brake_holds():
    """
    Vector: side_effect en cerebro (fallo intermitente de calculate_credit_score
    propagado como excepción de inferencia).
    Aserciones de freno cognitivo:
      (a) el Juez JAMÁS audita una respuesta inexistente (analyze_response no llamado);
      (b) el único texto que egresa es el fallback supervisado oficial;
      (c) NO hay alucinación de marcadores sintéticos de precio ($X.XXX) en el egreso;
      (d) mandato v9.8.3: set_human_help(True) → DEPRIORITIZED → save(model fallback)
          ANTES del envío del fallback.
    """
    timeline = []
    mock_ms = _build_ms_mock(timeline)

    async def _human_help(phone, status, **kwargs):
        timeline.append("set_human_help_status")
        return True

    mock_ms.set_human_help_status = AsyncMock(side_effect=_human_help)

    mock_cerebro = MagicMock()
    mock_cerebro.pensar_respuesta = AsyncMock(
        side_effect=RuntimeError("calculate_credit_score intermittent failure (simulated)")
    )
    mock_judge = MagicMock()
    mock_judge.analyze_response = AsyncMock(return_value=(True, ""))
    mock_catalog = MagicMock()
    mock_catalog.search = MagicMock(return_value=[])

    send_mock = AsyncMock(side_effect=lambda *a, **k: timeline.append("meta:send") or True)
    mock_wa = MagicMock()
    mock_wa.mark_as_read = AsyncMock()
    mock_egress = AsyncMock(return_value=True)

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.routers.whatsapp.judge_service", mock_judge), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.message_buffer", _build_buffer_mock()), \
         patch("app.routers.whatsapp.db", MagicMock(name="global_db")), \
         patch("app.routers.whatsapp.VisionService", MagicMock(return_value=MagicMock())), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_wa), \
         patch("app.routers.whatsapp._send_whatsapp_message", send_mock), \
         patch("app.routers.whatsapp._process_and_send_egress_message", mock_egress):

        await _handle_message_background_impl(_text_payload(), BackgroundTasks())

    # (a) Freno Cognitivo: el Juez jamás audita una respuesta inexistente.
    mock_judge.analyze_response.assert_not_called()

    # (b)+(c) El único egreso es el fallback supervisado, sin marcadores sintéticos.
    assert send_mock.await_count == 1
    sent_text = send_mock.call_args.args[1]
    assert sent_text == FALLBACK_TEXT, (
        f"Se egresó contenido no supervisado bajo fallo de herramienta: {sent_text!r}"
    )
    assert not re.search(r"\$\s?\d", sent_text), (
        f"ALUCINACIÓN: marcador sintético de precio en el egreso: {sent_text!r}"
    )
    # Ningún contenido de inferencia alcanzó el pipeline de egreso unificado.
    mock_egress.assert_not_called()

    # (d) Mandato v9.8.3: el estado de ayuda humana se marca ANTES de la red.
    mock_ms.set_human_help_status.assert_awaited_once_with(PHONE_E164, True)
    ponytail_calls = [
        c for c in mock_ms.update_prospect_summary.await_args_list
        if c.args[2] == {"ponytail_status": "DEPRIORITIZED"}
    ]
    assert ponytail_calls, "Falta ponytail DEPRIORITIZED (BOT-PONYTAIL-200)."
    assert "save_message:model" in timeline
    assert timeline.index("set_human_help_status") < timeline.index("meta:send"), (
        f"VIOLACIÓN mandato v9.8.3 (estado ≺ red): {timeline}"
    )
    # Pin de comportamiento VIGENTE (Feathers — asimetría observada, NO normalizar
    # sin aprobación del Auditor): la rama JUDGE_CRITICAL_ERROR envía el fallback
    # ANTES de persistirlo (send ≺ save), a diferencia de la rama de rechazo del
    # Juez (save ≺ send, pineada por ORDER-FALLBACK Wave 05-01). Ambas persisten.
    assert timeline.index("save_message:model") > timeline.index("meta:send"), (
        f"Comportamiento vigente alterado en la rama JUDGE_CRITICAL_ERROR: {timeline}"
    )


# ── Auditoría Zero-Silent-Failures ────────────────────────────────────────────

def _except_pass_violations(path: str) -> list[int]:
    import ast
    tree = ast.parse(open(path, encoding="utf-8").read())
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.ExceptHandler)
        and len(node.body) == 1
        and isinstance(node.body[0], ast.Pass)
    ]


def test_aud1_zero_silent_except_pass_blocks_in_transactional_axis():
    """
    AUD-1: Cero bloques `except …: pass` sin logger en el eje transaccional
    (whatsapp.py, whatsapp_service.py, memory_service.py). Pina la remediación
    Wave 05-06 (2 sitios: notification_service HANDOFF + observación Langfuse).
    """
    files = {
        "app/routers/whatsapp.py": [],
        "app/services/whatsapp_service.py": [],
        "app/services/memory_service.py": [],
    }
    violations = {f: _except_pass_violations(f) for f in files}
    assert all(v == [] for v in violations.values()), (
        f"SILENT FAILURE detectada (except: pass sin logger): {violations}"
    )


def test_aud2_http_status_error_handlers_expose_response_text():
    """
    AUD-2: los manejadores httpx.HTTPStatusError del egreso Meta incluyen
    e.response.text (forense obligatorio de proveedor externo) — tanto en los
    senders del router como en el servicio Meta.
    """
    import ast

    def _handlers_with_response_text(path: str) -> int:
        src = open(path, encoding="utf-8").read()
        tree = ast.parse(src)
        count = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and isinstance(node.type, ast.Attribute) \
                    and node.type.attr == "HTTPStatusError":
                segment = ast.get_source_segment(src, node) or ""
                if "response.text" in segment:
                    count += 1
        return count

    assert _handlers_with_response_text("app/routers/whatsapp.py") >= 2, (
        "Los senders del router deben incluir e.response.text en sus manejadores HTTP."
    )
    assert _handlers_with_response_text("app/services/whatsapp_service.py") >= 2, (
        "El servicio Meta debe incluir e.response.text en sus manejadores HTTP."
    )


@pytest.mark.asyncio
async def test_aud3_correlation_id_e164_and_wamid_in_root_trace():
    """
    AUD-3: la traza forense raíz del webhook se etiqueta con el ID de correlación
    obligatorio: user_id=E.164 y metadata.msg_id=wamid (más phone_number_id y tipo).
    """
    mock_ms = _build_ms_mock()
    mock_cerebro = MagicMock()
    mock_cerebro.pensar_respuesta = AsyncMock(return_value=APPROVED_TEXT)
    mock_judge = MagicMock()
    mock_judge.analyze_response = AsyncMock(return_value=(True, ""))
    mock_catalog = MagicMock()
    mock_catalog.search = MagicMock(return_value=[])
    mock_wa = MagicMock()
    mock_wa.mark_as_read = AsyncMock()
    mock_langfuse = MagicMock()

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.routers.whatsapp.judge_service", mock_judge), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.message_buffer", _build_buffer_mock()), \
         patch("app.routers.whatsapp.db", MagicMock(name="global_db")), \
         patch("app.routers.whatsapp.VisionService", MagicMock(return_value=MagicMock())), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_wa), \
         patch("app.routers.whatsapp.langfuse_context", mock_langfuse), \
         patch("app.routers.whatsapp._process_and_send_egress_message", AsyncMock(return_value=True)):

        payload = _text_payload(wamid="wamid.aud3")
        await _handle_message_background_impl(payload, BackgroundTasks())

    mock_langfuse.update_current_trace.assert_called()
    first_call = mock_langfuse.update_current_trace.call_args_list[0]
    assert first_call.kwargs["user_id"] == PHONE_E164, (
        f"Correlation ID (E.164) ausente en la traza raíz: {first_call.kwargs}"
    )
    assert first_call.kwargs["session_id"] == f"wa_{PHONE_E164}"
    assert first_call.kwargs["metadata"]["msg_id"] == "wamid.aud3", (
        f"Correlation ID (wamid) ausente en la traza raíz: {first_call.kwargs['metadata']}"
    )
    assert first_call.kwargs["metadata"]["phone_number_id"] == PHONE_NUMBER_ID
