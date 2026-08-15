"""
Integridad del Pipeline Reaction/Debounce — Etapa 3 Wave 05-05
[BOT-BUILD-ETAPA3-WAVE05-FRAGMENT-TEXT-EGRESS-001]

Pins de paridad pre/post extracción de `_pipeline_reaction_debounce` (sprout
method intra-archivo; cuerpo VERBATIM). Certifican que el comportamiento
post-extracción es idéntico al pre-extracción pineado por E2E-REACTION /
ORDER-REACTION (Wave 05-01).

  PRI-1  Intercept Habeas Data 👍: escritura BLOQUEANTE de
         {"habeas_data_accepted": True, "ponytail_status": "PENDING"} y retorno
         del cuerpo mutado ("Sí") para alimentar la inferencia (quick-138).
  PRI-2  Salidas tempranas codificadas con None: tarea superada por debounce y
         cuerpo agregado vacío — sin escritura habeas.
  PRI-3  Agregación del buffer: el cuerpo agregado tiene prioridad sobre el
         original y clear_buffer se await-ea (paridad de debounce).
  PRI-4  Patch targets de MessageBuffer vigentes: el buffer parcheado dirige el
         flujo (resolución del global en tiempo de llamada).
  PRI-5  Cableado del orquestador: la rama reaction del impl delega en el
         pipeline, muta msg_type→"text" con el cuerpo retornado y continúa el
         embudo cognitivo; el guardrail de deduplicación (add_message/wamid)
         permanece intacto aguas arriba.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import BackgroundTasks

from app.routers.whatsapp import (
    _handle_message_background_impl,
    _pipeline_reaction_debounce,
)

PHONE_E164 = "+573192564288"
PHONE_RAW = "573192564288"
PHONE_NUMBER_ID = "999999"
WAMID = "wamid.pri"


def _reaction_payload(emoji: str = "👍") -> dict:
    return {
        "from": PHONE_RAW,
        "id": WAMID,
        "type": "reaction",
        "phone_number_id": PHONE_NUMBER_ID,
        "reaction": {"message_id": "wamid.parent_1", "emoji": emoji},
    }


def _build_buffer_mock(*, is_active: bool = True, aggregated=None) -> MagicMock:
    buffer = MagicMock()
    buffer.add_message = AsyncMock(return_value=True)
    buffer.clear_messages = AsyncMock()
    buffer.is_task_active = MagicMock(return_value=is_active)
    buffer.get_aggregated_message = AsyncMock(return_value=aggregated)
    buffer.clear_buffer = AsyncMock()
    buffer.debounce_seconds = 0.01
    return buffer


def _build_ms_mock() -> MagicMock:
    ms = MagicMock()
    ms.update_prospect_summary = AsyncMock(return_value=True)
    return ms


# ── PRI-1: Intercept Habeas Data (escritura bloqueante + cuerpo mutado) ──────

@pytest.mark.asyncio
async def test_pri1_habeas_intercept_blocking_write_and_mutated_body():
    """
    Reacción 👍: la aceptación de Habeas Data se persiste de forma bloqueante
    (await sobre el futuro retornado) con el payload exacto pineado, y el
    pipeline devuelve el cuerpo "Sí" para alimentar el embudo cognitivo.
    """
    mock_ms = _build_ms_mock()
    buffer = _build_buffer_mock(is_active=True, aggregated=None)

    with patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.message_buffer", buffer):
        result = await _pipeline_reaction_debounce(
            _reaction_payload(),
            user_phone=PHONE_E164,
            msg_id_unique=WAMID,
            message_body="Sí",
            is_positive_reaction=True,
        )

    assert result == "Sí", f"El cuerpo mutado debía ser 'Sí'; recibido: {result!r}"
    mock_ms.update_prospect_summary.assert_awaited_once_with(
        PHONE_E164, "", {"habeas_data_accepted": True, "ponytail_status": "PENDING"}
    )


# ── PRI-2: Salidas tempranas (None) — tarea superada y cuerpo vacío ──────────

@pytest.mark.asyncio
async def test_pri2_early_exits_return_none_without_habeas_write():
    """
    (a) Tarea superada durante el debounce ⇒ None, sin agregación ni escritura.
    (b) Cuerpo agregado vacío ⇒ None, sin escritura habeas.
    """
    mock_ms = _build_ms_mock()
    buffer_superseded = _build_buffer_mock(is_active=False)

    with patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.message_buffer", buffer_superseded):
        result_a = await _pipeline_reaction_debounce(
            _reaction_payload(),
            user_phone=PHONE_E164,
            msg_id_unique=WAMID,
            message_body="Sí",
            is_positive_reaction=True,
        )

    assert result_a is None
    buffer_superseded.get_aggregated_message.assert_not_called()
    mock_ms.update_prospect_summary.assert_not_called()

    buffer_empty = _build_buffer_mock(is_active=True, aggregated=None)
    with patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.message_buffer", buffer_empty):
        result_b = await _pipeline_reaction_debounce(
            _reaction_payload(),
            user_phone=PHONE_E164,
            msg_id_unique=WAMID,
            message_body="",
            is_positive_reaction=False,
        )

    assert result_b is None
    mock_ms.update_prospect_summary.assert_not_called()


# ── PRI-3: Agregación del buffer (prioridad + clear bloqueante) ──────────────

@pytest.mark.asyncio
async def test_pri3_aggregated_body_takes_priority_and_clear_buffer_awaited():
    """
    Con agregación disponible, el pipeline devuelve el cuerpo agregado (no el
    original) y clear_buffer es await-eado dentro de la ventana de debounce.
    """
    mock_ms = _build_ms_mock()
    buffer = _build_buffer_mock(is_active=True, aggregated="Sí claro, autorizo")

    with patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.message_buffer", buffer):
        result = await _pipeline_reaction_debounce(
            _reaction_payload(),
            user_phone=PHONE_E164,
            msg_id_unique=WAMID,
            message_body="Sí",
            is_positive_reaction=True,
        )

    assert result == "Sí claro, autorizo", f"La agregación debía prevalecer: {result!r}"
    buffer.get_aggregated_message.assert_awaited_once_with(PHONE_E164)
    buffer.clear_buffer.assert_awaited_once_with(PHONE_E164)
    # El intercept habeas sigue ejecutándose con el cuerpo agregado presente.
    mock_ms.update_prospect_summary.assert_awaited_once()


# ── PRI-4: Patch targets de MessageBuffer vigentes ───────────────────────────

@pytest.mark.asyncio
async def test_pri4_message_buffer_patch_target_drives_debounce_flow():
    """
    El global message_buffer parcheado controla la ventana de debounce
    (debounce_seconds, is_task_active, agregación) — prueba de que el pipeline
    lee el singleton del módulo en tiempo de llamada.
    """
    buffer = _build_buffer_mock(is_active=True, aggregated="Sí")
    buffer.debounce_seconds = 0.05
    mock_ms = _build_ms_mock()

    with patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.message_buffer", buffer):
        result = await _pipeline_reaction_debounce(
            _reaction_payload(),
            user_phone=PHONE_E164,
            msg_id_unique=WAMID,
            message_body="Sí",
            is_positive_reaction=True,
        )

    assert result == "Sí"
    buffer.is_task_active.assert_called_once_with(PHONE_E164, WAMID)


# ── PRI-5: Cableado del orquestador (delegación + mutación msg_type→text) ────

@pytest.mark.asyncio
async def test_pri5_orchestrator_delegates_reaction_and_continues_as_text():
    """
    La rama reaction del impl delega en el pipeline (ctx propagado), muta
    msg_type→"text" con el cuerpo retornado y continúa el embudo: el pipeline
    cognitivo de texto recibe el cuerpo mutado. El guardrail de deduplicación
    (add_message con el wamid) permanece intacto aguas arriba de la delegación.
    """
    mock_reaction_pipeline = AsyncMock(return_value="Sí")
    mock_text_pipeline = AsyncMock(return_value=("Entendido, gracias por autorizar.", {"exists": True}))
    buffer = _build_buffer_mock(is_active=True, aggregated=None)
    mock_wa = MagicMock()
    mock_wa.mark_as_read = AsyncMock()
    mock_ms = MagicMock()
    ms_methods = (
        "create_prospect_if_missing", "update_last_interaction", "transition_to_in_progress",
        "generate_and_update_summary", "save_message", "set_human_help_status",
        "update_prospect_summary", "delete_prospect_completely",
    )
    for name in ms_methods:
        setattr(mock_ms, name, AsyncMock())
    mock_ms.get_or_create_prospect = AsyncMock(return_value={"exists": True})
    mock_ms.get_prospect_data = AsyncMock(return_value={"exists": True, "ai_summary": "x", "human_help_requested": False})
    mock_ms.get_chat_history = AsyncMock(return_value=[])
    mock_cerebro = MagicMock()
    mock_egress = AsyncMock(return_value=True)

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp._pipeline_reaction_debounce", mock_reaction_pipeline), \
         patch("app.routers.whatsapp._pipeline_text_cognitive", mock_text_pipeline), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.routers.whatsapp.VisionService", MagicMock(return_value=MagicMock())), \
         patch("app.routers.whatsapp.catalog_service", MagicMock(name="global_catalog")), \
         patch("app.routers.whatsapp.db", MagicMock(name="global_db")), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_wa), \
         patch("app.routers.whatsapp.message_buffer", buffer), \
         patch("app.routers.whatsapp._process_and_send_egress_message", mock_egress):

        payload = _reaction_payload()
        await _handle_message_background_impl(payload, BackgroundTasks())

    # Guardrail de deduplicación intacto aguas arriba (wamid registrado pre-delegación).
    buffer.add_message.assert_awaited_once_with(PHONE_E164, "Sí", WAMID)

    mock_reaction_pipeline.assert_awaited_once()
    call = mock_reaction_pipeline.call_args
    assert call.args[0] is payload
    assert call.kwargs["user_phone"] == PHONE_E164
    assert call.kwargs["msg_id_unique"] == WAMID
    assert call.kwargs["message_body"] == "Sí"
    assert call.kwargs["is_positive_reaction"] is True

    # El cuerpo mutado alimenta el embudo cognitivo (quick-138) vía msg_type→text.
    mock_text_pipeline.assert_awaited_once()
    assert mock_text_pipeline.call_args.kwargs["message_body"] == "Sí"
