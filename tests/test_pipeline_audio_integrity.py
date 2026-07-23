"""
Integridad del Pipeline de Audio — Etapa 3 Wave 05-04
[BOT-BUILD-ETAPA3-WAVE04-FRAGMENT-MEDIA-AUDIO-001]

Pins de paridad pre/post extracción de `_pipeline_audio` (sprout method
intra-archivo extraído del God Node; el cuerpo se movió VERBATIM). Certifican que
el comportamiento post-extracción es idéntico al pre-extracción pineado por las
waves 05-01 (E2E-AUDIO / ORDER-AUDIO) y el mandato BOT-ROUTER-AUDIO-LINEAGE-123.

  AI-1  Paridad de transcripción fuzzy: normalize_transcription se aplica a la
        transcripción cruda y el historial persiste la versión ALINEADA (blinding fix).
  AI-2  Paridad de escrituras Firestore: save(user=transcripción) ≺
        generate_and_update_summary (BLOQUEANTE, con last_bot_question anclado)
        ≺ pensar_respuesta. La matriz de perfilamiento se sincroniza antes de inferir.
  AI-3  Contrato de retorno (response_text, prospect_data): None codifica la
        salida temprana por human_help post-sync; el texto aprobado fluye al egreso.
  AI-4  Costuras: el kwarg catalog tiene prioridad sobre el global; sin kwargs el
        global parcheado dirige el flujo (patch targets heredados vigentes).
  AI-5  Cableado del orquestador: la rama audio del impl delega en el pipeline con
        propagación de costuras + ctx (cerebro_ia de sesión) y egresa el texto
        retornado.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import BackgroundTasks

from app.routers.whatsapp import (
    _handle_message_background_impl,
    _pipeline_audio,
)

PHONE_E164 = "+573192564288"
PHONE_RAW = "573192564288"
PHONE_NUMBER_ID = "999999"
RAW_TRANSCRIPTION = "Quiero comprar una Victory"
ALIGNED_TRANSCRIPTION = "QUIERO COMPRAR UNA VICTORY"


# ── Builders ──────────────────────────────────────────────────────────────────

def _audio_payload() -> dict:
    return {
        "from": PHONE_RAW,
        "id": "wamid.ai",
        "type": "audio",
        "phone_number_id": PHONE_NUMBER_ID,
        "media_id": "media-ai-1",
        "mime_type": "audio/ogg; codecs=opus",
    }


def _build_prospect(human_help: bool = False) -> dict:
    return {
        "exists": True,
        "status": "IN_PROGRESS",
        "chatbot_status": "ACTIVE",
        "name": "Juan Test",
        "celular": PHONE_E164,
        "ai_summary": "Resumen previo",
        "human_help_requested": human_help,
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
        async def _save(phone, role, content, **kwargs):
            timeline.append((f"save_message:{role}", content))
            return True

        ms.save_message = AsyncMock(side_effect=_save)

        async def _sync(phone, conversation, cerebro, last_bot_question="", **kwargs):
            timeline.append(("generate_and_update_summary", last_bot_question))
            return True

        ms.generate_and_update_summary = AsyncMock(side_effect=_sync)
    else:
        ms.save_message = AsyncMock()
        ms.generate_and_update_summary = AsyncMock()
    return ms


def _build_audio_mocks(transcription: str = RAW_TRANSCRIPTION) -> tuple[MagicMock, MagicMock, MagicMock]:
    mock_audio = MagicMock()
    mock_audio.transcribe_audio = AsyncMock(return_value=transcription)
    mock_storage = MagicMock()
    mock_storage.download_media = AsyncMock(return_value=b"fake_audio_bytes")
    mock_cerebro = MagicMock()
    mock_cerebro.pensar_respuesta = AsyncMock(return_value="Perfecto, la Victory es ideal.")
    return mock_audio, mock_storage, mock_cerebro


def _base_patches(mock_ms, mock_audio, mock_storage, mock_cerebro, mock_judge,
                  mock_catalog) -> tuple:
    return (
        patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock),
        patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms),
        patch("app.routers.whatsapp.AudioService", return_value=mock_audio),
        patch("app.routers.whatsapp.storage_service", mock_storage),
        patch("app.routers.whatsapp.judge_service", mock_judge),
        patch("app.routers.whatsapp.catalog_service", mock_catalog),
        patch("app.routers.whatsapp._send_whatsapp_message", AsyncMock(return_value=True)),
    )


# ── AI-1: Paridad de transcripción fuzzy ──────────────────────────────────────

@pytest.mark.asyncio
async def test_ai1_fuzzy_transcription_parity_and_aligned_persistence():
    """
    La sanitización fonética fuzzy se aplica a la transcripción cruda y el
    historial persiste la versión ALINEADA (blinding fix
    BOT-BUGFIX-AUDIO-REGRESSION-121), con el mismo receptor (catalog resuelto).
    """
    timeline = []
    mock_ms = _build_ms_mock(timeline)
    mock_audio, mock_storage, mock_cerebro = _build_audio_mocks()
    mock_judge = MagicMock()
    mock_judge.analyze_response = AsyncMock(return_value=(True, ""))
    mock_catalog = MagicMock()
    mock_catalog.normalize_transcription = MagicMock(return_value=ALIGNED_TRANSCRIPTION)
    mock_catalog.search = MagicMock(return_value=[])

    patches = _base_patches(mock_ms, mock_audio, mock_storage, mock_cerebro, mock_judge, mock_catalog)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
        await _pipeline_audio(
            _audio_payload(),
            user_phone=PHONE_E164,
            phone_number_id=PHONE_NUMBER_ID,
            cerebro_ia=mock_cerebro,
            context="",
            prospect_data=None,
        )

    mock_catalog.normalize_transcription.assert_called_once_with(RAW_TRANSCRIPTION)
    saved = [content for label, content in timeline if label == "save_message:user"]
    assert saved == [ALIGNED_TRANSCRIPTION], (
        f"El historial debía persistir la transcripción ALINEADA; recibido: {saved!r}"
    )


# ── AI-2: Paridad de escrituras Firestore + generate_and_update_summary ──────

@pytest.mark.asyncio
async def test_ai2_firestore_parity_and_blocking_memory_sync():
    """
    Orden transaccional pineado: save(user=transcripción) ≺
    generate_and_update_summary (await bloqueante, anclado con la última pregunta
    del bot del historial) ≺ pensar_respuesta. Cero fire-and-forget.
    """
    history = [
        {"role": "user", "content": "hola"},
        {"role": "model", "content": "¿Qué tipo de moto buscas?"},
    ]
    timeline = []
    mock_ms = _build_ms_mock(timeline, history=history)
    mock_audio, mock_storage, mock_cerebro = _build_audio_mocks()

    async def _pensar(*args, **kwargs):
        timeline.append(("pensar_respuesta", None))
        return "Perfecto, la Victory es ideal."

    mock_cerebro.pensar_respuesta = AsyncMock(side_effect=_pensar)
    mock_judge = MagicMock()
    mock_judge.analyze_response = AsyncMock(return_value=(True, ""))
    mock_catalog = MagicMock()
    mock_catalog.normalize_transcription = MagicMock(side_effect=lambda x: x)
    mock_catalog.search = MagicMock(return_value=[])

    patches = _base_patches(mock_ms, mock_audio, mock_storage, mock_cerebro, mock_judge, mock_catalog)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
        await _pipeline_audio(
            _audio_payload(),
            user_phone=PHONE_E164,
            phone_number_id=PHONE_NUMBER_ID,
            cerebro_ia=mock_cerebro,
            context="",
            prospect_data=None,
        )

    labels = [label for label, _ in timeline]
    assert "save_message:user" in labels, f"Falta save(user=transcripción): {labels}"
    sync_calls = [content for label, content in timeline if label == "generate_and_update_summary"]
    assert len(sync_calls) == 1, (
        f"generate_and_update_summary debía ejecutarse exactamente 1 vez (bloqueante): {labels}"
    )
    assert sync_calls[0] == "¿Qué tipo de moto buscas?", (
        f"last_bot_question no se ancló desde el historial: {sync_calls[0]!r}"
    )
    i_save = labels.index("save_message:user")
    i_sync = labels.index("generate_and_update_summary")
    i_pensar = labels.index("pensar_respuesta")
    assert i_save < i_sync < i_pensar, (
        f"VIOLACIÓN de orden post-extracción: {labels}. "
        "Se exige save(user) ≺ generate_and_update_summary ≺ pensar_respuesta."
    )
    # Blocking: la sincronía de memoria fue await-eada (AsyncMock awaited, no fire-and-forget).
    mock_ms.generate_and_update_summary.assert_awaited_once()


# ── AI-3: Contrato de retorno (salida temprana vs texto aprobado) ────────────

@pytest.mark.asyncio
async def test_ai3_return_contract_human_help_early_exit():
    """
    human_help_requested=True en el re-fetch post-sync (único dato autoritativo,
    BOT-ROUTER-AUDIO-LINEAGE-123): el pipeline retorna (None, prospect_data) y
    JAMÁS invoca pensar_respuesta — el orquestador omite el egreso.
    """
    prospect = _build_prospect(human_help=True)
    mock_ms = _build_ms_mock(prospect=prospect)
    mock_audio, mock_storage, mock_cerebro = _build_audio_mocks()
    mock_judge = MagicMock()
    mock_judge.analyze_response = AsyncMock(return_value=(True, ""))
    mock_catalog = MagicMock()
    mock_catalog.normalize_transcription = MagicMock(side_effect=lambda x: x)

    patches = _base_patches(mock_ms, mock_audio, mock_storage, mock_cerebro, mock_judge, mock_catalog)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
        result = await _pipeline_audio(
            _audio_payload(),
            user_phone=PHONE_E164,
            phone_number_id=PHONE_NUMBER_ID,
            cerebro_ia=mock_cerebro,
            context="",
            prospect_data=None,
        )

    assert result[0] is None, (
        f"La salida temprana por human_help debe codificar response_text=None; recibido: {result[0]!r}"
    )
    assert result[1] is prospect, "El prospect_data post-sync no se devolvió al orquestador."
    mock_cerebro.pensar_respuesta.assert_not_called()
    mock_judge.analyze_response.assert_not_called()


@pytest.mark.asyncio
async def test_ai3b_return_contract_approved_text_flows_to_egress():
    """
    Ruta aprobada: el pipeline retorna (response_text, prospect_data) y el Juez
    audita exactamente una vez (intacto el flujo de inferencia con auditoría).
    """
    prospect = _build_prospect()
    mock_ms = _build_ms_mock(prospect=prospect)
    mock_audio, mock_storage, mock_cerebro = _build_audio_mocks()
    mock_judge = MagicMock()
    mock_judge.analyze_response = AsyncMock(return_value=(True, ""))
    mock_catalog = MagicMock()
    mock_catalog.normalize_transcription = MagicMock(side_effect=lambda x: x)
    mock_catalog.search = MagicMock(return_value=[])

    patches = _base_patches(mock_ms, mock_audio, mock_storage, mock_cerebro, mock_judge, mock_catalog)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
        result = await _pipeline_audio(
            _audio_payload(),
            user_phone=PHONE_E164,
            phone_number_id=PHONE_NUMBER_ID,
            cerebro_ia=mock_cerebro,
            context="",
            prospect_data=None,
        )

    assert result[0] == "Perfecto, la Victory es ideal.", (
        f"response_text alterado tras la extracción: {result[0]!r}"
    )
    assert result[1] is prospect
    mock_judge.analyze_response.assert_awaited_once()


# ── AI-4: Costuras (prioridad del kwarg + fallback al global) ────────────────

@pytest.mark.asyncio
async def test_ai4_catalog_kwarg_priority_and_global_fallback():
    """
    Con catalog=inyectado, la sanitización fuzzy usa el inyectado (centinela global
    intacto). Sin kwargs, el global catalog_service parcheado dirige el flujo
    (patch targets heredados vigentes — resolución en tiempo de llamada).
    """
    # (a) Prioridad del kwarg
    injected_catalog = MagicMock(name="injected_catalog")
    injected_catalog.normalize_transcription = MagicMock(return_value=ALIGNED_TRANSCRIPTION)
    injected_catalog.search = MagicMock(return_value=[])
    sentinel_catalog = MagicMock(name="global_catalog_sentinel")

    mock_ms = _build_ms_mock()
    mock_audio, mock_storage, mock_cerebro = _build_audio_mocks()
    mock_judge = MagicMock()
    mock_judge.analyze_response = AsyncMock(return_value=(True, ""))

    patches = _base_patches(mock_ms, mock_audio, mock_storage, mock_cerebro, mock_judge, sentinel_catalog)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
        await _pipeline_audio(
            _audio_payload(),
            catalog=injected_catalog,
            user_phone=PHONE_E164,
            phone_number_id=PHONE_NUMBER_ID,
            cerebro_ia=mock_cerebro,
            context="",
            prospect_data=None,
        )

    injected_catalog.normalize_transcription.assert_called_once_with(RAW_TRANSCRIPTION)
    sentinel_catalog.normalize_transcription.assert_not_called()

    # (b) Fallback al global (sin kwargs)
    global_catalog = MagicMock(name="global_catalog")
    global_catalog.normalize_transcription = MagicMock(side_effect=lambda x: x)
    global_catalog.search = MagicMock(return_value=[])
    mock_ms2 = _build_ms_mock()
    mock_audio2, mock_storage2, mock_cerebro2 = _build_audio_mocks()
    mock_judge2 = MagicMock()
    mock_judge2.analyze_response = AsyncMock(return_value=(True, ""))

    patches2 = _base_patches(mock_ms2, mock_audio2, mock_storage2, mock_cerebro2, mock_judge2, global_catalog)
    with patches2[0], patches2[1], patches2[2], patches2[3], patches2[4], patches2[5], patches2[6]:
        await _pipeline_audio(
            _audio_payload(),
            user_phone=PHONE_E164,
            phone_number_id=PHONE_NUMBER_ID,
            cerebro_ia=mock_cerebro2,
            context="",
            prospect_data=None,
        )

    global_catalog.normalize_transcription.assert_called_once_with(RAW_TRANSCRIPTION)
    global_catalog.search.assert_called()


# ── AI-5: Cableado del orquestador (delegación + egreso del texto retornado) ──

@pytest.mark.asyncio
async def test_ai5_orchestrator_delegates_audio_branch_and_egresses_returned_text():
    """
    La rama audio del impl delega en `_pipeline_audio` propagando las costuras
    resueltas y el ctx (cerebro_ia de la sesión, context, prospect_data), y luego
    egresa exactamente el response_text retornado por el pipeline.
    """
    prospect = _build_prospect()
    returned = ("Texto respuesta final", prospect)
    mock_pipeline = AsyncMock(name="patched__pipeline_audio", return_value=returned)
    mock_ms = _build_ms_mock(prospect=prospect)
    mock_cerebro = MagicMock()
    mock_catalog_global = MagicMock(name="global_catalog")
    mock_wa = MagicMock()
    mock_wa.mark_as_read = AsyncMock()
    mock_egress = AsyncMock(return_value=True)

    buffer = MagicMock()
    buffer.add_message = AsyncMock(return_value=True)

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp._pipeline_audio", mock_pipeline), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.routers.whatsapp.VisionService", MagicMock(return_value=MagicMock())), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog_global), \
         patch("app.routers.whatsapp.db", MagicMock(name="global_db")), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_wa), \
         patch("app.routers.whatsapp.message_buffer", buffer), \
         patch("app.routers.whatsapp._process_and_send_egress_message", mock_egress):

        payload = _audio_payload()
        await _handle_message_background_impl(payload, BackgroundTasks())

    mock_pipeline.assert_awaited_once()
    call = mock_pipeline.call_args
    assert call.args[0] is payload, "El payload no se propagó posicionalmente."
    assert call.kwargs["catalog"] is mock_catalog_global
    assert call.kwargs["cerebro_ia"] is mock_cerebro, (
        "La instancia cerebro_ia de la sesión no se propagó al pipeline."
    )
    assert call.kwargs["user_phone"] == PHONE_E164
    assert call.kwargs["phone_number_id"] == PHONE_NUMBER_ID
    assert call.kwargs["context"] == ""
    assert call.kwargs["prospect_data"] == prospect

    # El orquestador egresa exactamente el texto retornado por el pipeline.
    mock_egress.assert_awaited_once_with(PHONE_E164, "Texto respuesta final", phone_number_id=PHONE_NUMBER_ID)
