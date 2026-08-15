import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import BackgroundTasks
from app.routers.whatsapp import webhook_handler, _handle_message_background_impl
from tests.factories import make_catalog, make_domain_item, format_cop

@pytest.mark.asyncio
async def test_audio_regression_last_bot_question_injection():
    """
    Test para validar que en el procesamiento de audios, el pipeline:
    1. Responda 200 OK (síncronamente del webhook_handler).
    2. Extraiga correctamente la última pregunta del bot (last_bot_question) desde la historia del chat.
    3. Inyecte esta pregunta en generate_and_update_summary en lugar de una cadena vacía.
    """
    # 1. Payload de webhook de WhatsApp con tipo 'audio'
    payload_dict = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "123",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "123456", "phone_number_id": "999999"},
                    "messages": [{
                        "from": "573192564288",
                        "id": "wamid.test_audio_regression_123",
                        "timestamp": "1672531199",
                        "audio": {
                            "id": "audio_media_id_123",
                            "mime_type": "audio/ogg; codecs=opus"
                        },
                        "type": "audio"
                    }]
                },
                "field": "messages"
            }]
        }]
    }

    mock_request = MagicMock()
    async def mock_body():
        import json
        return json.dumps(payload_dict).encode("utf-8")
    mock_request.body = mock_body
    mock_request.headers = {"X-Hub-Signature-256": "sha256=dummy"}
    # [Incidente H-A · HA-2] Guard estricto: el request debe presentar catálogo listo.
    mock_request.app.state.catalog_ready = True

    # Mock del MemoryService
    mock_memory_service = MagicMock()
    mock_memory_service.create_prospect_if_missing = AsyncMock()
    mock_memory_service.update_last_interaction = AsyncMock()
    mock_memory_service.save_message = AsyncMock()
    mock_memory_service.transition_to_in_progress = AsyncMock()
    mock_memory_service.delete_prospect_completely = AsyncMock()
    mock_memory_service.get_prospect_data = AsyncMock(return_value={
        "exists": True,
        "status": "PENDING",
        "chatbot_status": "ACTIVE",
        "name": "Juan Test",
        "celular": "+573192564288"
    })
    
    # Historia de chat simulada: la última pregunta del bot fue "¿Qué tipo de moto buscas?"
    mock_history = [
        {"role": "user", "content": "hola"},
        {"role": "model", "content": "¿Qué tipo de moto buscas?"}
    ]
    mock_memory_service.get_chat_history = AsyncMock(return_value=mock_history)
    mock_memory_service.generate_and_update_summary = AsyncMock()

    # Mocks de servicios requeridos
    mock_storage = MagicMock()
    mock_storage.download_media = AsyncMock(return_value=b"mock_audio_bytes")

    mock_audio = MagicMock()
    mock_audio.transcribe_audio = AsyncMock(return_value="Quiero comprar una Victory")

    catalog_items = make_catalog(100)
    mock_cerebro = MagicMock()
    mock_cerebro.pensar_respuesta = AsyncMock(return_value=f"Perfecto. La Victory está disponible por {format_cop(catalog_items[0]['price'])}. Ficha Tecnica: http://... ![](http://victory.png)")

    mock_whatsapp = MagicMock()
    mock_whatsapp.mark_as_read = AsyncMock()
    mock_whatsapp.send_text_message = AsyncMock()
    mock_whatsapp.send_image_message = AsyncMock()

    mock_catalog = MagicMock()
    mock_catalog.search = MagicMock(return_value=[])
    mock_catalog.get_all_items = MagicMock(return_value=catalog_items)
    mock_catalog.normalize_transcription = MagicMock(side_effect=lambda x: x)

    mock_judge = MagicMock()
    mock_judge.analyze_response = AsyncMock(return_value=(True, ""))

    # Parchear todas las dependencias
    with patch("app.routers.whatsapp.settings") as mock_settings, \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_memory_service), \
         patch("app.routers.whatsapp.storage_service", mock_storage), \
         patch("app.routers.whatsapp.AudioService", return_value=mock_audio), \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_whatsapp), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.judge_service", mock_judge):

        mock_settings.whatsapp_app_secret = None  # Bypass firma
        mock_settings.cloud_tasks_queue_path = None
        mock_settings.task_processor_url = None
        mock_settings.min_catalog_items = 0

        # 1. Ejecutar webhook_handler y verificar respuesta síncrona
        background_tasks = BackgroundTasks()
        response = await webhook_handler(mock_request, background_tasks)
        assert response == {"status": "received"}

        # 2. Ejecutar la lógica de fondo de forma directa para inspeccionar el flujo
        msg_data = {
            "from": "573192564288",
            "id": "wamid.test_audio_regression_123",
            "timestamp": "1672531199",
            "type": "audio",
            "media_id": "audio_media_id_123",
            "mime_type": "audio/ogg; codecs=opus"
        }
        
        # Desactivamos el buffer de mensajes para evitar falsos positivos
        with patch("app.routers.whatsapp.message_buffer.add_message", AsyncMock(return_value=True)):
            await _handle_message_background_impl(msg_data, background_tasks)

        # 3. Validaciones
        # - El audio debe haber sido descargado
        mock_storage.download_media.assert_called_once_with("audio_media_id_123")
        # - La transcripción debe haber sido solicitada con los bytes descargados
        mock_audio.transcribe_audio.assert_called_once_with(b"mock_audio_bytes", "audio/ogg; codecs=opus")
        # - El mensaje transcrito debe haber sido guardado en Firestore
        mock_memory_service.save_message.assert_any_call(
            "+573192564288", "user", "Quiero comprar una Victory"
        )
        # - generate_and_update_summary debe ser llamado con la última pregunta del bot extraída del historial
        mock_memory_service.generate_and_update_summary.assert_called_once_with(
            "+573192564288",
            "User sent audio. Transcription: Quiero comprar una Victory",
            mock_cerebro,
            last_bot_question="¿Qué tipo de moto buscas?"
        )


@pytest.mark.asyncio
async def test_audio_lineage_post_reset_no_desertion():
    """
    [BOT-ROUTER-AUDIO-LINEAGE-123] Test de Caracterización — Ráfaga /reset + Audio ('Reader').

    Simula la condición de carrera crítica donde:
    1. /reset limpia Firestore → documento recreado.
    2. Payload de audio llega inmediatamente después.
    3. El pre-fetch (pre-sync) del bloque audio devuelve human_help_requested=True (dato residual).
    4. El re-fetch POST-generate_and_update_summary devuelve human_help_requested=False (dato fresco).

    PROHIBICIÓN RÍGIDA: El bot NO debe silenciarse con el dato obsoleto del pre-fetch.
    MANDATO: generate_and_update_summary debe ejecutarse exactamente una vez.
    MANDATO: pensar_respuesta debe ser invocado (el flujo no abortó por datos obsoletos).
    MANDATO: set_human_help_status(True) NO debe ser llamado (no hay falsa deserción).
    """
    from app.routers.whatsapp import _handle_message_background_impl
    from fastapi import BackgroundTasks

    msg_data = {
        "from": "573199999999",
        "id": "wamid.audio_lineage_post_reset_001",
        "timestamp": "1672531200",
        "type": "audio",
        "media_id": "audio_media_post_reset_999",
        "mime_type": "audio/ogg; codecs=opus",
        "phone_number_id": "555555"
    }

    # --- Estado residual pre-sync: flag de deserción activo (residuo pre-reset)
    stale_prospect_data = {
        "exists": True,
        "status": "IN_PROGRESS",
        "chatbot_status": "ACTIVE",
        "name": "Carlos Reset",
        "celular": "+573199999999",
        "human_help_requested": True,  # ← DATO OBSOLETO / RESIDUAL
        "ai_summary": "Prospecto histórico pre-reset"
    }

    # --- Estado fresco post-sync: flag limpiado por Firestore post-reset
    fresh_prospect_data = {
        "exists": True,
        "status": "IN_PROGRESS",
        "chatbot_status": "ACTIVE",
        "name": "Carlos Reset",
        "celular": "+573199999999",
        "human_help_requested": False,  # ← DATO FRESCO POST-SYNC
        "ai_summary": ""
    }

    # get_prospect_data: 1ra llamada (pre-sync) → dato obsoleto; 2da+ (post-sync) → dato fresco
    call_count_prospect = {"n": 0}
    async def mock_get_prospect_data(phone):
        call_count_prospect["n"] += 1
        if call_count_prospect["n"] == 1:
            return stale_prospect_data   # pre-fetch pre-sync
        return fresh_prospect_data       # re-fetch post-sync

    mock_memory_service = MagicMock()
    mock_memory_service.create_prospect_if_missing = AsyncMock()
    mock_memory_service.update_last_interaction = AsyncMock()
    mock_memory_service.save_message = AsyncMock()
    mock_memory_service.transition_to_in_progress = AsyncMock()
    mock_memory_service.update_prospect_summary = AsyncMock()
    mock_memory_service.update_last_interaction = AsyncMock()
    mock_memory_service.set_human_help_status = AsyncMock()
    mock_memory_service.get_prospect_data = AsyncMock(side_effect=mock_get_prospect_data)
    mock_memory_service.generate_and_update_summary = AsyncMock()
    mock_memory_service.get_chat_history = AsyncMock(return_value=[
        {"role": "user", "content": "/reset"},
        {"role": "model", "content": "✅ Tu sesión ha sido reiniciada por completo. Cuéntame, ¿en qué moto estás interesado?"}
    ])

    mock_storage = MagicMock()
    mock_storage.download_media = AsyncMock(return_value=b"mock_audio_bytes_reset")

    mock_audio = MagicMock()
    mock_audio.transcribe_audio = AsyncMock(return_value="Busco una moto económica para trabajo")

    catalog_items = make_catalog(50)
    mock_cerebro = MagicMock()
    mock_cerebro.pensar_respuesta = AsyncMock(
        return_value=f"Perfecto Carlos! La TVS Sport 100 es ideal. Precio: {format_cop(catalog_items[0]['price'])}. Ficha Tecnica: specs... ![TVS](http://tvs.png)"
    )

    mock_whatsapp = MagicMock()
    mock_whatsapp.mark_as_read = AsyncMock()
    mock_whatsapp.send_text_message = AsyncMock()

    mock_catalog = MagicMock()
    mock_catalog.search = MagicMock(return_value=[])
    mock_catalog.get_all_items = MagicMock(return_value=catalog_items)
    mock_catalog._items = []
    mock_catalog.normalize_transcription = MagicMock(side_effect=lambda x: x)

    mock_judge = MagicMock()
    mock_judge.analyze_response = AsyncMock(return_value=(True, ""))

    mock_config = MagicMock()

    with patch("app.routers.whatsapp.memory_service_module.memory_service", mock_memory_service), \
         patch("app.routers.whatsapp.storage_service", mock_storage), \
         patch("app.routers.whatsapp.AudioService", return_value=mock_audio), \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.routers.whatsapp.VisionService", return_value=MagicMock()), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_whatsapp), \
         patch("app.routers.whatsapp.whatsapp_service", mock_whatsapp, create=True), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.judge_service", mock_judge), \
         patch("app.routers.whatsapp.config_loader", mock_config), \
         patch("app.routers.whatsapp.motor_financiero", None), \
         patch("app.routers.whatsapp.message_buffer") as mock_buffer, \
         patch("app.routers.whatsapp._ensure_services", AsyncMock()):

        mock_buffer.add_message = AsyncMock(return_value=True)
        mock_buffer.clear_messages = AsyncMock()
        mock_buffer.debounce_seconds = 0
        mock_buffer.is_task_active = MagicMock(return_value=True)

        background_tasks = BackgroundTasks()
        await _handle_message_background_impl(msg_data, background_tasks)

    # === ASERCIONES RÍGIDAS ===

    # 1. generate_and_update_summary DEBE haber sido llamado (LINEAR BLOCKING ejecutado)
    mock_memory_service.generate_and_update_summary.assert_called_once()
    call_args = mock_memory_service.generate_and_update_summary.call_args
    assert "Busco una moto económica para trabajo" in str(call_args), \
        "generate_and_update_summary no recibió la transcripción correcta"

    # 2. pensar_respuesta DEBE haber sido invocado (el bot no abortó con dato obsoleto)
    mock_cerebro.pensar_respuesta.assert_called_once(), \
        "FALLO CRÍTICO: pensar_respuesta no fue llamado. El bot se silenció con datos obsoletos (pre-sync)"

    # 3. set_human_help_status(True) NO debe haber sido invocado (no hay falsa deserción)
    for call in mock_memory_service.set_human_help_status.call_args_list:
        args = call[0]
        if len(args) >= 2:
            assert args[1] != True, \
                "FALLO CRÍTICO: set_human_help_status(True) fue invocado — falso positivo de deserción por contexto residual"

    # 4. get_prospect_data fue llamado al menos 2 veces (pre-fetch + re-fetch post-sync)
    assert call_count_prospect["n"] >= 2, \
        f"get_prospect_data llamado solo {call_count_prospect['n']} vez — el re-fetch post-sync no ocurrió"

@pytest.mark.asyncio
async def test_audio_post_reset_credit_intent_no_fallback():
    """
    [BOT-BUILD-ETAPA3-POST-RESET-C9-GRACE-001] Regresión E2E — Audio post-reset con
    intención de crédito NO debe caer al fallback de handoff humano.

    Escenario: /reset → wipe → audio preguntando por crédito/cuotas. prospect_data
    fresco SIN 'ciudad' ni 'name'. El cerebro responde hablando de crédito (keyword
    de _detect_credit_advance) sin mencionar modelos de moto ni URLs. El Juez es
    REAL (auditoría semántica C4 desactivada — patrón del fixture de
    test_judge_service.py).

    CONTRATO:
    1. C9 se condona en el primer turno legítimo: pensar_respuesta se invoca
       exactamente 1 vez (cero reintentos por rechazo del Juez).
    2. set_human_help_status JAMÁS se invoca con True (no hay falsa deserción).
    3. El orquestador egresa la respuesta APROBADA del cerebro (NO el fallback
       'Disculpa, no estoy seguro...').
    """
    from app.services.judge_service import JudgeService

    msg_data = {
        "from": "573199999998",
        "id": "wamid.audio_post_reset_c9_grace_001",
        "timestamp": "1672531200",
        "type": "audio",
        "media_id": "audio_media_post_reset_c9_001",
        "mime_type": "audio/ogg; codecs=opus",
        "phone_number_id": "555555"
    }

    # Estado fresco post-reset: SIN 'ciudad' ni 'name' (el Juez evalúa has_city=False)
    fresh_prospect_data = {
        "exists": True,
        "status": "IN_PROGRESS",
        "chatbot_status": "ACTIVE",
        "celular": "+573199999998",
        "human_help_requested": False,
        "ai_summary": ""
    }

    credit_response = (
        "¡Hola! Soy Juan Pablo de Tienda Las Motos. "
        "Claro que sí, el crédito lo manejamos directamente y las cuotas dependen del plazo."
    )

    mock_memory_service = MagicMock()
    mock_memory_service.create_prospect_if_missing = AsyncMock()
    mock_memory_service.update_last_interaction = AsyncMock()
    mock_memory_service.save_message = AsyncMock()
    mock_memory_service.transition_to_in_progress = AsyncMock()
    mock_memory_service.update_prospect_summary = AsyncMock()
    mock_memory_service.set_human_help_status = AsyncMock()
    mock_memory_service.get_prospect_data = AsyncMock(return_value=fresh_prospect_data)
    mock_memory_service.get_or_create_prospect = AsyncMock(return_value=fresh_prospect_data)
    mock_memory_service.generate_and_update_summary = AsyncMock()
    # Historial post-reset REALISTA: incluye el comando /reset (excluido por el
    # filtro BOT-206), la confirmación (model) y la transcripción del turno actual.
    mock_memory_service.get_chat_history = AsyncMock(return_value=[
        {"role": "user", "content": "/reset"},
        {"role": "model", "content": "✅ Tu sesión ha sido reiniciada por completo. Cuéntame, ¿en qué moto estás interesado?"},
        {"role": "user", "content": "cuánto es la cuota para financiar una moto"},
    ])

    mock_storage = MagicMock()
    mock_storage.download_media = AsyncMock(return_value=b"mock_audio_bytes_reset_c9")

    mock_audio = MagicMock()
    mock_audio.transcribe_audio = AsyncMock(return_value="cuánto es la cuota para financiar una moto")

    mock_cerebro = MagicMock()
    mock_cerebro.pensar_respuesta = AsyncMock(return_value=credit_response)

    mock_whatsapp = MagicMock()
    mock_whatsapp.mark_as_read = AsyncMock()
    mock_whatsapp.send_text_message = AsyncMock()

    mock_catalog = MagicMock()
    mock_catalog.search = MagicMock(return_value=[])
    mock_catalog.get_all_items = MagicMock(return_value=[])
    mock_catalog._items = []
    mock_catalog.normalize_transcription = MagicMock(side_effect=lambda x: x)

    # Juez REAL con auditoría semántica (C4) desactivada.
    real_judge = JudgeService(cerebro_ia=MagicMock())
    real_judge._client = None

    mock_config = MagicMock()
    mock_egress = AsyncMock(return_value=True)

    with patch("app.routers.whatsapp.memory_service_module.memory_service", mock_memory_service), \
         patch("app.routers.whatsapp.storage_service", mock_storage), \
         patch("app.routers.whatsapp.AudioService", return_value=mock_audio), \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.routers.whatsapp.VisionService", return_value=MagicMock()), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_whatsapp), \
         patch("app.routers.whatsapp.whatsapp_service", mock_whatsapp, create=True), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.judge_service", real_judge), \
         patch("app.routers.whatsapp.config_loader", mock_config), \
         patch("app.routers.whatsapp.motor_financiero", None), \
         patch("app.routers.whatsapp._process_and_send_egress_message", mock_egress), \
         patch("app.routers.whatsapp.message_buffer") as mock_buffer, \
         patch("app.routers.whatsapp._ensure_services", AsyncMock()):

        mock_buffer.add_message = AsyncMock(return_value=True)
        mock_buffer.clear_messages = AsyncMock()
        mock_buffer.debounce_seconds = 0
        mock_buffer.is_task_active = MagicMock(return_value=True)

        background_tasks = BackgroundTasks()
        await _handle_message_background_impl(msg_data, background_tasks)

    # === ASERCIONES RÍGIDAS ===

    # 1. C9 condonado → aprobación en el primer intento: UNA sola inferencia.
    mock_cerebro.pensar_respuesta.assert_called_once()

    # 2. NO hay falsa deserción: set_human_help_status(True) jamás invocado.
    for call in mock_memory_service.set_human_help_status.call_args_list:
        args = call[0]
        if len(args) >= 2:
            assert args[1] is not True, \
                "FALLO CRÍTICO: set_human_help_status(True) invocado — el audio post-reset cayó al fallback."

    # 3. El egreso consolida la respuesta APROBADA del cerebro (no el fallback).
    mock_egress.assert_awaited_once()
    egress_args = mock_egress.call_args
    assert egress_args.args[1] == credit_response, \
        f"El egreso debió enviar la respuesta aprobada del cerebro; recibió: {egress_args.args[1]!r}"


@pytest.mark.asyncio
async def test_audio_service_live_integration():

    """
    Test de Integración Desacoplado (Live/Integration Test)
    Intenta instanciar AudioService de forma nativa en ambos canales de autenticación
    (API Key y Vertex AI) y valida aserciones rígidas sobre el model_id unificado,
    mientras simula las llamadas a la API de Google de forma segura.
    """
    from google.auth.exceptions import DefaultCredentialsError
    from google.genai.errors import APIError, ClientError
    from app.services.audio_service import AudioService
    from unittest.mock import patch, MagicMock
    import logging
    import os

    logger = logging.getLogger("tests.test_audio_regression")

    # 1. Canal 1: API Key
    logger.info("Testing AudioService initialization via API Key channel...")
    mock_client_instance = MagicMock()
    mock_client_instance.models.list.return_value = [MagicMock()]
    
    with patch.dict(os.environ, {"GEMINI_API_KEY": "fake_api_key", "GOOGLE_GENAI_USE_VERTEXAI": "false"}), \
         patch("app.services.genai_client_service.genai.Client", return_value=mock_client_instance) as mock_client_cls:
        
        service = AudioService()
        assert service._model_id == "gemini-2.5-flash", "model_id no coincide con la constante unificada en el canal de API Key"
        
        # Validar la llamada simulada
        models = list(service.client.models.list())
        assert len(models) > 0
        mock_client_cls.assert_called_once_with(api_key="fake_api_key")

    # 2. Canal 2: Vertex AI
    logger.info("Testing AudioService initialization via Vertex AI channel...")
    mock_client_instance_vertex = MagicMock()
    mock_client_instance_vertex.models.list.return_value = [MagicMock()]
    mock_creds = MagicMock()
    
    with patch.dict(os.environ, {"GOOGLE_GENAI_USE_VERTEXAI": "true", "GOOGLE_CLOUD_PROJECT": "test-project", "GOOGLE_CLOUD_LOCATION": "us-central1"}), \
         patch("google.auth.default", return_value=(mock_creds, "test-project")), \
         patch("app.services.genai_client_service.genai.Client", return_value=mock_client_instance_vertex) as mock_client_cls_vertex:
        
        service_vertex = AudioService()
        assert service_vertex._model_id == "gemini-2.5-flash", "model_id no coincide con la constante unificada en el canal de Vertex AI"
        
        # Validar la llamada simulada
        models = list(service_vertex.client.models.list())
        assert len(models) > 0
        mock_client_cls_vertex.assert_called_once_with(
            vertexai=True,
            project="test-project",
            location="us-central1",
        )


@pytest.mark.asyncio
async def test_audio_fuzzy_alignment_rader():
    """
    [BOT-ROUTER-AUDIO-FUZZY-ALIGNMENT-124] Test de Caracterización Abierto:
    Valida que una nota de voz con la transcripción degradada 'rader' sea normalizada
    y alineada a 'raider' usando el motor fonético de CatalogService, y que el Juez
    la apruebe sin forzar la deserción humana (human_help_requested=False).
    """
    from app.routers.whatsapp import _handle_message_background_impl
    from fastapi import BackgroundTasks
    from app.services.catalog_service import CatalogService

    msg_data = {
        "from": "573198888888",
        "id": "wamid.audio_fuzzy_rader_999",
        "timestamp": "1672531300",
        "type": "audio",
        "media_id": "audio_media_rader_999",
        "mime_type": "audio/ogg; codecs=opus",
        "phone_number_id": "555555"
    }

    # Instanciamos CatalogService real pero con un catálogo mockeado en memoria para aislar
    real_catalog = CatalogService()
    # Ítem de dominio generado por factories.py (precio dinámico, seed fija) con
    # overrides semánticos para el matching fuzzy — cero literales de precio [HA-3].
    raider_item = make_domain_item(
        name="TVS Raider 125",
        category="deportiva",
        search_tags=["sport", "tecnologia"],
        search_text="tvs raider 125 deportiva sport tecnologia",
        search_tokens=["tvs", "raider", "125", "deportiva", "sport", "tecnologia"],
        searchBy=["sport", "tecnologia"],
        description="Moto deportiva con tecnologia de punta y gran desempeño.",
        active=True,
        cc=125
    )
    real_catalog._items = [raider_item]
    real_catalog._items_by_id = {i["id"]: i for i in real_catalog._items}

    mock_memory_service = MagicMock()
    mock_memory_service.create_prospect_if_missing = AsyncMock()
    mock_memory_service.update_last_interaction = AsyncMock()
    mock_memory_service.save_message = AsyncMock()
    mock_memory_service.transition_to_in_progress = AsyncMock()
    mock_memory_service.get_prospect_data = AsyncMock(return_value={
        "exists": True,
        "status": "IN_PROGRESS",
        "chatbot_status": "ACTIVE",
        "name": "Cliente Raider",
        "celular": "+573198888888",
        "human_help_requested": False
    })
    mock_memory_service.get_chat_history = AsyncMock(return_value=[])
    mock_memory_service.generate_and_update_summary = AsyncMock()
    mock_memory_service.set_human_help_status = AsyncMock()

    mock_storage = MagicMock()
    mock_storage.download_media = AsyncMock(return_value=b"mock_audio_bytes_rader")

    # Forzar la transcripción cruda hacia el token degradado 'rader'
    mock_audio = MagicMock()
    mock_audio.transcribe_audio = AsyncMock(return_value="Quiero cotizar una rader")

    # Cerebro IA devuelve una respuesta mencionando la Raider con el precio
    # GENERADO por la fábrica (consistencia PCC sin literales [HA-3])
    mock_cerebro = MagicMock()
    mock_cerebro.pensar_respuesta = AsyncMock(
        return_value=f"Perfecto. La TVS Raider 125 está disponible por {format_cop(raider_item['price'])} (incluye SOAT, Matrícula, y tramites). Ficha Tecnica: http://... ![](http://raider.png)"
    )

    mock_whatsapp = MagicMock()
    mock_whatsapp.mark_as_read = AsyncMock()
    mock_whatsapp.send_text_message = AsyncMock()

    # Juez de aprobación
    mock_judge = MagicMock()
    mock_judge.analyze_response = AsyncMock(return_value=(True, ""))

    with patch("app.routers.whatsapp.memory_service_module.memory_service", mock_memory_service), \
         patch("app.routers.whatsapp.storage_service", mock_storage), \
         patch("app.routers.whatsapp.AudioService", return_value=mock_audio), \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.routers.whatsapp.VisionService", return_value=MagicMock()), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_whatsapp), \
         patch("app.routers.whatsapp.whatsapp_service", mock_whatsapp, create=True), \
         patch("app.routers.whatsapp.catalog_service", real_catalog), \
         patch("app.routers.whatsapp.judge_service", mock_judge), \
         patch("app.routers.whatsapp.message_buffer") as mock_buffer, \
         patch("app.routers.whatsapp._ensure_services", AsyncMock()):

        mock_buffer.add_message = AsyncMock(return_value=True)
        mock_buffer.clear_messages = AsyncMock()
        mock_buffer.debounce_seconds = 0
        mock_buffer.is_task_active = MagicMock(return_value=True)

        background_tasks = BackgroundTasks()
        await _handle_message_background_impl(msg_data, background_tasks)

    # Aserciones rígidas:
    # 1. El mensaje guardado en memoria debe ser el normalizado 'raider' en vez del degradado 'rader'
    # 2. set_human_help_status(True) no debe ser invocado
    # 3. El judge no debe fallar (is_approved=True)

    # Verificamos que la transcripción guardada y transmitida fue normalizada a 'raider'
    mock_memory_service.save_message.assert_any_call("+573198888888", "user", "Quiero cotizar una raider")
    
    # Aseguramos que no se active la deserción humana
    for call in mock_memory_service.set_human_help_status.call_args_list:
        args = call[0]
        if len(args) >= 2:
            assert args[1] != True, "Falso positivo de deserción humana activo."
