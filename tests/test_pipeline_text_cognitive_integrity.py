"""
Integridad del Pipeline Text/Cognitivo — Etapa 3 Wave 05-05
[BOT-BUILD-ETAPA3-WAVE05-FRAGMENT-TEXT-EGRESS-001]

Pins de paridad pre/post extracción de `_pipeline_text_cognitive` (sprout method
intra-archivo; cuerpo VERBATIM). Certifican que el comportamiento post-extracción
es idéntico al pre-extracción pineado por E2E-TEXT / ORDER-TEXT / CH-5 (Wave 05-01).

  TCI-1  Paridad de invocación a pensar_respuesta: mismos argumentos (input,
         context, prospect_data con phone inyectado, history, skip_greeting).
  TCI-2  Paridad de escrituras Firestore: generate_and_update_summary BLOQUEANTE
         (anclado con last_bot_question) ≺ re-fetch ≺ pensar ≺ save(model).
  TCI-3  Fallback del Juez (mandato v9.8.3): 3 intentos ⇒ set_human_help(True) →
         ponytail DEPRIORITIZED → save(model fallback) → envío fallback, y
         retorno (None, prospect_data) — el orquestador omite el egreso.
  TCI-4  Costura catalog: kwarg prioritario sobre el global; sin kwargs el global
         parcheado dirige el contexto del Juez (patch targets vigentes).
  TCI-5  Cableado del orquestador: la rama text del impl delega en el pipeline
         (ctx completo, incl. cerebro_ia de sesión) y egresa el texto retornado.

Nota BOT-174 (mandato Wave 05-01 §3): `ms.get_or_create_prospect` se configura
como AsyncMock explícito en todos los arneses que alcanzan el guard.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import BackgroundTasks

from app.routers.whatsapp import (
    _handle_message_background_impl,
    _pipeline_text_cognitive,
)

PHONE_E164 = "+573192564288"
PHONE_RAW = "573192564288"
PHONE_NUMBER_ID = "999999"
USER_QUERY = "Quiero una moto económica"
APPROVED_TEXT = "La Victory Switch 150 es ideal. Precio: $8.000.000."
FALLBACK_TEXT = "Disculpa, no estoy seguro de la respuesta, permíteme le pregunto a mi supervisor y te comento."


# ── Builders ──────────────────────────────────────────────────────────────────

def _text_payload() -> dict:
    return {
        "from": PHONE_RAW,
        "id": "wamid.tci",
        "type": "text",
        "phone_number_id": PHONE_NUMBER_ID,
        "text": USER_QUERY,
    }


def _build_prospect() -> dict:
    return {
        "exists": True,
        "status": "IN_PROGRESS",
        "chatbot_status": "ACTIVE",
        "name": "Juan Test",
        "celular": PHONE_E164,
        "ai_summary": "Resumen previo",
        "human_help_requested": False,
    }


def _build_ms_mock(timeline: list | None = None, prospect: dict | None = None,
                   history: list | None = None) -> MagicMock:
    prospect = prospect or _build_prospect()
    ms = MagicMock()
    ms.create_prospect_if_missing = AsyncMock()
    ms.update_last_interaction = AsyncMock()
    ms.transition_to_in_progress = AsyncMock()
    ms.set_human_help_status = AsyncMock()
    ms.update_prospect_summary = AsyncMock()
    ms.delete_prospect_completely = AsyncMock(return_value=True)
    ms.get_or_create_prospect = AsyncMock(return_value=prospect)
    ms.get_prospect_data = AsyncMock(return_value=prospect)
    ms.get_chat_history = AsyncMock(return_value=history if history is not None else [])

    if timeline is not None:
        async def _sync(phone, conversation, cerebro, last_bot_question="", **kwargs):
            timeline.append(("generate_and_update_summary", last_bot_question))
            return True

        ms.generate_and_update_summary = AsyncMock(side_effect=_sync)

        async def _save(phone, role, content, **kwargs):
            timeline.append((f"save_message:{role}", content))
            return True

        ms.save_message = AsyncMock(side_effect=_save)
    else:
        ms.generate_and_update_summary = AsyncMock()
        ms.save_message = AsyncMock()
    return ms


def _build_cerebro(timeline: list | None = None, text: str = APPROVED_TEXT) -> MagicMock:
    cerebro = MagicMock()
    if timeline is not None:
        async def _pensar(*args, **kwargs):
            timeline.append(("pensar_respuesta", None))
            return text
        cerebro.pensar_respuesta = AsyncMock(side_effect=_pensar)
    else:
        cerebro.pensar_respuesta = AsyncMock(return_value=text)
    return cerebro


def _base_patches(mock_ms, mock_judge, mock_catalog) -> tuple:
    return (
        patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms),
        patch("app.routers.whatsapp.judge_service", mock_judge),
        patch("app.routers.whatsapp.catalog_service", mock_catalog),
        patch("app.routers.whatsapp._send_whatsapp_message", AsyncMock(return_value=True)),
    )


async def _run_text_pipeline(mock_ms, mock_cerebro, mock_judge, mock_catalog, **kwargs):
    patches = _base_patches(mock_ms, mock_judge, mock_catalog)
    with patches[0], patches[1], patches[2], patches[3]:
        return await _pipeline_text_cognitive(
            _text_payload(),
            user_phone=PHONE_E164,
            phone_number_id=PHONE_NUMBER_ID,
            message_body=USER_QUERY,
            cerebro_ia=mock_cerebro,
            context="",
            prospect_data=None,
            current_history=kwargs.pop("history", []),
            skip_greeting=False,
            **kwargs,
        )


# ── TCI-1: Paridad de invocación a pensar_respuesta ───────────────────────────

@pytest.mark.asyncio
async def test_tci1_pensar_respuesta_call_parity():
    """
    pensar_respuesta se invoca una vez (Juez aprueba al primer intento) con los
    argumentos heredados exactos: input=message_body, context, prospect_data con
    phone inyectado, history y skip_greeting.
    """
    history = [{"role": "user", "content": "hola"}, {"role": "model", "content": "¿Qué buscas?"}]
    prospect = _build_prospect()
    mock_ms = _build_ms_mock(prospect=prospect, history=history)
    mock_cerebro = _build_cerebro()
    mock_judge = MagicMock()
    mock_judge.analyze_response = AsyncMock(return_value=(True, ""))
    mock_catalog = MagicMock()
    mock_catalog.search = MagicMock(return_value=[])

    result = await _run_text_pipeline(mock_ms, mock_cerebro, mock_judge, mock_catalog,
                                      history=history, catalog=mock_catalog)

    mock_cerebro.pensar_respuesta.assert_awaited_once()
    call = mock_cerebro.pensar_respuesta.call_args
    assert call.args[0] == USER_QUERY
    assert call.kwargs["context"] == ""
    assert call.kwargs["history"] == history
    assert call.kwargs["skip_greeting"] is False
    assert call.kwargs["prospect_data"]["phone"] == PHONE_E164
    assert result[0] == APPROVED_TEXT
    assert result[1] is prospect


# ── TCI-2: Paridad de escrituras Firestore (LINEAR BLOCKING bloqueante) ──────

@pytest.mark.asyncio
async def test_tci2_firestore_writes_parity_and_blocking_memory_sync():
    """
    Orden pineado: generate_and_update_summary (bloqueante, anclado con la última
    pregunta del bot) ≺ re-fetch get_prospect_data ≺ pensar_respuesta.
    T3: save(model) ya no ocurre en este pipeline; vive en el egreso unificado.
    """
    history = [
        {"role": "user", "content": "hola"},
        {"role": "model", "content": "¿Qué tipo de moto buscas?"},
    ]
    timeline = []
    mock_ms = _build_ms_mock(timeline, history=history)

    get_calls = []
    prospect = _build_prospect()

    async def _get(phone):
        get_calls.append(phone)
        timeline.append(("get_prospect_data", None))
        return prospect

    mock_ms.get_prospect_data = AsyncMock(side_effect=_get)
    mock_cerebro = _build_cerebro(timeline)
    mock_judge = MagicMock()
    mock_judge.analyze_response = AsyncMock(return_value=(True, ""))
    mock_catalog = MagicMock()
    mock_catalog.search = MagicMock(return_value=[])

    await _run_text_pipeline(mock_ms, mock_cerebro, mock_judge, mock_catalog,
                           history=history, catalog=mock_catalog)

    labels = [label for label, _ in timeline]
    sync_calls = [c for label, c in timeline if label == "generate_and_update_summary"]
    assert len(sync_calls) == 1, f"Memory sync debía ser 1 (bloqueante): {labels}"
    assert sync_calls[0] == "¿Qué tipo de moto buscas?", (
        f"last_bot_question no anclado desde el historial: {sync_calls[0]!r}"
    )
    mock_ms.generate_and_update_summary.assert_awaited_once()

    i_sync = labels.index("generate_and_update_summary")
    i_refetch = labels.index("get_prospect_data")
    i_pensar = labels.index("pensar_respuesta")
    assert i_sync < i_refetch < i_pensar, (
        f"Orden LINEAR BLOCKING alterado: {labels}"
    )
    # T3: save(model) fue movido al egreso unificado; no debe aparecer en este pipeline.
    assert "save_message:model" not in labels, (
        f"T3: save_message('model') inesperado en pipeline cognitivo: {labels}"
    )


# ── TCI-3: Fallback del Juez (mandato v9.8.3) ────────────────────────────────

@pytest.mark.asyncio
async def test_tci3_judge_fallback_mandato_v983_and_none_contract():
    """
    Juez rechaza 3 veces ⇒ mandato v9.8.3 intacto: set_human_help_status(True) →
    ponytail DEPRIORITIZED → save(model fallback) → envío fallback (estado antes
    que red). Retorna (None, prospect_data): el orquestador omite el egreso.
    """
    prospect = _build_prospect()
    mock_ms = _build_ms_mock(prospect=prospect)
    mock_cerebro = _build_cerebro(text="Respuesta rechazada")
    mock_judge = MagicMock()
    mock_judge.analyze_response = AsyncMock(return_value=(False, "C1_VISUAL_LOCK: falta imagen"))
    mock_catalog = MagicMock()
    mock_catalog.search = MagicMock(return_value=[])

    send_mock = AsyncMock(return_value=True)
    with patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.judge_service", mock_judge), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp._send_whatsapp_message", send_mock):
        result = await _pipeline_text_cognitive(
            _text_payload(),
            catalog=mock_catalog,
            user_phone=PHONE_E164,
            phone_number_id=PHONE_NUMBER_ID,
            message_body=USER_QUERY,
            cerebro_ia=mock_cerebro,
            context="",
            prospect_data=None,
            current_history=[],
            skip_greeting=False,
        )

    assert mock_cerebro.pensar_respuesta.await_count == 3, (
        f"El bucle del Juez debía agotar 3 intentos: {mock_cerebro.pensar_respuesta.await_count}"
    )
    assert result[0] is None, f"El fallback debía codificar response_text=None: {result[0]!r}"
    assert result[1] is prospect

    mock_ms.set_human_help_status.assert_awaited_once_with(PHONE_E164, True)
    ponytail_calls = [
        c for c in mock_ms.update_prospect_summary.await_args_list
        if c.args[2] == {"ponytail_status": "DEPRIORITIZED"}
    ]
    assert ponytail_calls, "Falta la persistencia ponytail_status=DEPRIORITIZED (BOT-PONYTAIL-200)."
    mock_ms.save_message.assert_any_await(PHONE_E164, "model", FALLBACK_TEXT)
    send_mock.assert_awaited_once_with(PHONE_E164, FALLBACK_TEXT, phone_number_id=PHONE_NUMBER_ID)

    # Sincronía de Oficio: set_human_help ≺ envío del fallback (estado antes que red).
    assert mock_ms.set_human_help_status.await_count == 1


# ── TCI-4: Costura catalog (kwarg prioritario + fallback al global) ──────────

@pytest.mark.asyncio
async def test_tci4_catalog_kwarg_priority_and_global_fallback():
    """
    Con catalog=inyectado, el contexto del Juez (search) usa el inyectado y el
    global queda intacto. Sin kwargs, el global catalog_service parcheado dirige
    la búsqueda — patch targets vigentes (resolución en tiempo de llamada).
    """
    # (a) kwarg prioritario
    injected = MagicMock(name="injected_catalog")
    injected.search = MagicMock(return_value=[])
    sentinel = MagicMock(name="global_catalog_sentinel")
    mock_ms = _build_ms_mock()
    mock_cerebro = _build_cerebro()
    mock_judge = MagicMock()
    mock_judge.analyze_response = AsyncMock(return_value=(True, ""))

    await _run_text_pipeline(mock_ms, mock_cerebro, mock_judge, sentinel, catalog=injected)
    injected.search.assert_called()
    sentinel.search.assert_not_called()

    # (b) fallback al global (sin kwargs)
    global_catalog = MagicMock(name="global_catalog")
    global_catalog.search = MagicMock(return_value=[])
    mock_ms2 = _build_ms_mock()
    mock_cerebro2 = _build_cerebro()
    mock_judge2 = MagicMock()
    mock_judge2.analyze_response = AsyncMock(return_value=(True, ""))

    await _run_text_pipeline(mock_ms2, mock_cerebro2, mock_judge2, global_catalog)
    global_catalog.search.assert_called()


# ── TCI-5: Cableado del orquestador (delegación + egreso del texto retornado) ─

@pytest.mark.asyncio
async def test_tci5_orchestrator_delegates_text_branch_and_egresses_returned_text():
    """
    La rama text del impl delega en `_pipeline_text_cognitive` propagando las
    costuras resueltas y el ctx completo (message_body, cerebro_ia de sesión,
    prospect_data post-apertura, current_history, skip_greeting), y luego egresa
    exactamente el response_text retornado por el pipeline.
    """
    prospect = _build_prospect()
    returned = ("Texto final aprobado", prospect)
    mock_pipeline = AsyncMock(name="patched__pipeline_text_cognitive", return_value=returned)
    mock_ms = _build_ms_mock(prospect=prospect)
    mock_cerebro = MagicMock()
    mock_catalog_global = MagicMock(name="global_catalog")
    mock_wa = MagicMock()
    mock_wa.mark_as_read = AsyncMock()
    mock_egress = AsyncMock(return_value=True)
    buffer = MagicMock()
    buffer.add_message = AsyncMock(return_value=True)
    buffer.clear_messages = AsyncMock()

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp._pipeline_text_cognitive", mock_pipeline), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.routers.whatsapp.VisionService", MagicMock(return_value=MagicMock())), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog_global), \
         patch("app.routers.whatsapp.db", MagicMock(name="global_db")), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_wa), \
         patch("app.routers.whatsapp.message_buffer", buffer), \
         patch("app.routers.whatsapp._process_and_send_egress_message", mock_egress):

        payload = _text_payload()
        await _handle_message_background_impl(payload, BackgroundTasks())

    mock_pipeline.assert_awaited_once()
    call = mock_pipeline.call_args
    assert call.args[0] is payload
    assert call.kwargs["catalog"] is mock_catalog_global
    assert call.kwargs["cerebro_ia"] is mock_cerebro
    assert call.kwargs["message_body"] == USER_QUERY
    assert call.kwargs["user_phone"] == PHONE_E164
    assert call.kwargs["phone_number_id"] == PHONE_NUMBER_ID
    assert call.kwargs["context"] == ""
    assert call.kwargs["prospect_data"] == prospect
    assert call.kwargs["current_history"] == []
    assert isinstance(call.kwargs["skip_greeting"], bool)

    mock_egress.assert_awaited_once_with(PHONE_E164, "Texto final aprobado", phone_number_id=PHONE_NUMBER_ID)
