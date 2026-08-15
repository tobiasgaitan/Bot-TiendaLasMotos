import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import BackgroundTasks
from google.api_core import exceptions as gcp_exceptions
from app.routers.whatsapp import _handle_message_background

@pytest.mark.asyncio
async def test_whatsapp_save_message_propagates_logic_error():
    """
    DADO: un error de tipo (TypeError) o lógica interna (AttributeError) durante save_message.
    CUANDO: _handle_message_background ejecuta la persistencia.
    ENTONCES:
      - La excepción TypeError/AttributeError explota y escala hacia arriba (Zero-Silent-Failures).
      - NO se consume recursos de red externa llamando a _send_whatsapp_message para enviar fallbacks.
    """
    msg_data = {
        "from": "573192564288",
        "id": "wamid.text_logic_err_123",
        "type": "text",
        "text": "hola",
        "phone_number_id": "1021779847693778"
    }
    background_tasks = BackgroundTasks()

    # Configurar mock de MemoryService que lanza TypeError (fallo lógico)
    mock_ms = AsyncMock()
    mock_ms.save_message = AsyncMock(side_effect=TypeError("Simulated logical TypeError"))

    # Configuración de Mocks genéricos del entorno
    mock_db = MagicMock()
    mock_db.project = "tiendalasmotos"
    mock_message_buffer = AsyncMock()
    mock_message_buffer.add_message = AsyncMock(return_value=True)
    mock_message_buffer.clear_messages = AsyncMock()
    mock_config_loader = MagicMock()
    mock_catalog = MagicMock()
    mock_config_service = MagicMock()
    mock_judge = AsyncMock()
    mock_wa_service = AsyncMock()

    with patch("app.routers.whatsapp.db", mock_db), \
         patch("app.routers.whatsapp.message_buffer", mock_message_buffer), \
         patch("app.routers.whatsapp.config_loader", mock_config_loader), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.config_service", mock_config_service), \
         patch("app.routers.whatsapp.judge_service", mock_judge), \
         patch("app.routers.whatsapp.memory_service_module") as mock_mem_module, \
         patch("app.routers.whatsapp._send_whatsapp_message") as mock_send_wa, \
         patch("app.services.whatsapp_service.whatsapp_service", mock_wa_service):

        mock_mem_module.memory_service = mock_ms

        # ASERCIÓN RÍGIDA: Debe explotar hacia arriba con TypeError
        with pytest.raises(TypeError, match="Simulated logical TypeError"):
            await _handle_message_background(msg_data, background_tasks)

        # Probar que no se envió ningún mensaje de fallback al usuario (sin llamadas a red externa)
        mock_send_wa.assert_not_called()


@pytest.mark.asyncio
async def test_whatsapp_save_message_handles_network_error():
    """
    DADO: un fallo de red/timeout de Firestore (ServiceUnavailable).
    CUANDO: _handle_message_background ejecuta la persistencia.
    ENTONCES:
      - La excepción se captura y se activa la contingencia (intermitencia).
      - Se despacha el mensaje de intermitencia al cliente.
    """
    msg_data = {
        "from": "573192564288",
        "id": "wamid.text_net_err_123",
        "type": "text",
        "text": "hola",
        "phone_number_id": "1021779847693778"
    }
    background_tasks = BackgroundTasks()

    # Configurar mock de MemoryService que lanza ServiceUnavailable (fallo de red/GCP)
    mock_ms = AsyncMock()
    mock_ms.save_message = AsyncMock(side_effect=gcp_exceptions.ServiceUnavailable("GCP Service Unavailable"))

    # Configuración de Mocks genéricos del entorno
    mock_db = MagicMock()
    mock_db.project = "tiendalasmotos"
    mock_message_buffer = AsyncMock()
    mock_message_buffer.add_message = AsyncMock(return_value=True)
    mock_message_buffer.clear_messages = AsyncMock()
    mock_config_loader = MagicMock()
    mock_catalog = MagicMock()
    mock_config_service = MagicMock()
    mock_judge = AsyncMock()
    mock_wa_service = AsyncMock()

    with patch("app.routers.whatsapp.db", mock_db), \
         patch("app.routers.whatsapp.message_buffer", mock_message_buffer), \
         patch("app.routers.whatsapp.config_loader", mock_config_loader), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.config_service", mock_config_service), \
         patch("app.routers.whatsapp.judge_service", mock_judge), \
         patch("app.routers.whatsapp.memory_service_module") as mock_mem_module, \
         patch("app.routers.whatsapp._send_whatsapp_message") as mock_send_wa, \
         patch("app.services.whatsapp_service.whatsapp_service", mock_wa_service):

        mock_mem_module.memory_service = mock_ms

        # Ejecutar: no debe explotar (es capturada y manejada por la contingencia)
        await _handle_message_background(msg_data, background_tasks)

        # Debe haber enviado el mensaje de intermitencia
        mock_send_wa.assert_called_once()
        args, _ = mock_send_wa.call_args
        sent_text = args[1]
        assert "intermitencias" in sent_text


@pytest.mark.asyncio
async def test_whatsapp_handle_message_structured_forensic_logging():
    """
    Verifica que ante una excepción crítica de desarrollo en _handle_message_background:
    1. Se intercepte el error y se genere el payload JSON Voorhees con firma 'CRITICAL_CODE_FAULT'.
    2. El payload contenga error_type, error_message, file, line, y stack_trace.
    3. Se registre a través de logger.error.
    4. La excepción se relance (raise) sin silenciarse.
    """
    msg_data = {
        "from": "573192564288",
        "id": "wamid.text_logic_err_forensic",
        "type": "text",
        "text": "hola",
        "phone_number_id": "1021779847693778"
    }
    background_tasks = BackgroundTasks()

    # Lanzamos un AttributeError que es una falla de desarrollo típica
    mock_ms = AsyncMock()
    mock_ms.save_message = AsyncMock(side_effect=AttributeError("Atributo incorrecto simulado"))

    mock_db = MagicMock()
    mock_db.project = "tiendalasmotos"
    mock_message_buffer = AsyncMock()
    mock_message_buffer.add_message = AsyncMock(return_value=True)
    mock_message_buffer.clear_messages = AsyncMock()
    mock_config_loader = MagicMock()
    mock_catalog = MagicMock()
    mock_config_service = MagicMock()
    mock_judge = AsyncMock()
    mock_wa_service = AsyncMock()

    with patch("app.routers.whatsapp.db", mock_db), \
         patch("app.routers.whatsapp.message_buffer", mock_message_buffer), \
         patch("app.routers.whatsapp.config_loader", mock_config_loader), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.config_service", mock_config_service), \
         patch("app.routers.whatsapp.judge_service", mock_judge), \
         patch("app.routers.whatsapp.memory_service_module") as mock_mem_module, \
         patch("app.routers.whatsapp._send_whatsapp_message"), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_wa_service), \
         patch("app.routers.whatsapp.logger") as mock_logger:

        mock_mem_module.memory_service = mock_ms

        with pytest.raises(AttributeError, match="Atributo incorrecto simulado"):
            await _handle_message_background(msg_data, background_tasks)

        # Verificar que logger.error fue llamado con el diccionario estructurado conteniendo 'CRITICAL_CODE_FAULT'
        mock_logger.error.assert_called_once()
        args, _ = mock_logger.error.call_args
        logged_payload = args[0]

        assert isinstance(logged_payload, dict), "El log forense debe ser un diccionario estructurado"
        assert "CRITICAL_CODE_FAULT" in logged_payload, "Debe contener la firma estricta 'CRITICAL_CODE_FAULT'"
        
        fault_data = logged_payload["CRITICAL_CODE_FAULT"]
        assert fault_data["error_type"] == "AttributeError"
        assert fault_data["error_message"] == "Atributo incorrecto simulado"
        assert any(x in fault_data["file"] for x in ["whatsapp.py", "mock.py", "memory_service.py"])
        assert isinstance(fault_data["line"], int)
        assert "stack_trace" in fault_data
        assert "AttributeError: Atributo incorrecto simulado" in fault_data["stack_trace"]


@pytest.mark.asyncio
async def test_whatsapp_handle_message_habeas_data_bypass_interrupt():
    """
    Verifica que si pensar_respuesta lanza HabeasDataBypassInterrupt:
    1. El router captura la excepción y no la propaga como error.
    2. Trata la respuesta de legalización como aprobada (is_approved=True).
    3. Envía la respuesta legal + simulación al usuario directamente.
    4. No activa el supervisor / fallback.
    """
    from app.core.exceptions import HabeasDataBypassInterrupt
    
    msg_data = {
        "from": "573192564288",
        "id": "wamid.text_habeas_bypass_123",
        "type": "text",
        "text": "quiero simular mi credito",
        "phone_number_id": "1021779847693778"
    }
    background_tasks = BackgroundTasks()

    # CerebroIA que lanza HabeasDataBypassInterrupt
    mock_cerebro = MagicMock()
    mock_cerebro.pensar_respuesta = AsyncMock(
        side_effect=HabeasDataBypassInterrupt("Simulacion ciega + Habeas Data disclaimer")
    )

    mock_ms = AsyncMock()
    mock_ms.get_prospect_data = AsyncMock(return_value={"nombre": "Pedro", "habeas_data_accepted": False})
    mock_ms.get_chat_history = AsyncMock(return_value=[])
    mock_ms.generate_and_update_summary = AsyncMock()
    mock_ms.save_message = AsyncMock()
    mock_ms.create_prospect_if_missing = AsyncMock()
    mock_ms.update_last_interaction = AsyncMock()
    mock_ms.transition_to_in_progress = AsyncMock()

    mock_db = MagicMock()
    mock_db.project = "tiendalasmotos"
    mock_message_buffer = AsyncMock()
    mock_message_buffer.add_message = AsyncMock(return_value=True)
    mock_message_buffer.clear_messages = AsyncMock()
    mock_config_loader = MagicMock()
    mock_catalog = MagicMock()
    mock_config_service = MagicMock()
    mock_judge = AsyncMock()
    mock_wa_service = AsyncMock()

    with patch("app.routers.whatsapp.db", mock_db), \
         patch("app.routers.whatsapp.message_buffer", mock_message_buffer), \
         patch("app.routers.whatsapp.config_loader", mock_config_loader), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.config_service", mock_config_service), \
         patch("app.routers.whatsapp.judge_service", mock_judge), \
         patch("app.routers.whatsapp.memory_service_module") as mock_mem_module, \
         patch("app.routers.whatsapp._send_whatsapp_message") as mock_send_wa, \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_wa_service):

        mock_mem_module.memory_service = mock_ms

        await _handle_message_background(msg_data, background_tasks)

        # 1. Asegurar que se llamó a pensar_respuesta
        mock_cerebro.pensar_respuesta.assert_called_once()
        
        # 2. Asegurar que _send_whatsapp_message fue llamado con la respuesta de la excepción
        mock_send_wa.assert_called_once_with(
            "+573192564288", 
            "Simulacion ciega + Habeas Data disclaimer", 
            phone_number_id="1021779847693778"
        )
        
        # 3. Asegurar que no se llamó a set_human_help_status (que es parte del fallback)
        mock_ms.set_human_help_status.assert_not_called()


# ============================================================================
# BOT-AUDIT-ETAPA5-ZSF-001 — Tests de caracterización: helpers de parsing Meta
# Certifican: (a) fallback intacto (False/None), (b) logger.exception invocado
# ante payloads malformados, (c) happy path sin logging de excepción.
# ============================================================================

from app.routers.whatsapp import (
    _is_valid_statuses,
    _is_valid_message,
    _extract_message_data,
)


def test_is_valid_statuses_fallback_on_malformed_payload():
    """entry no-dict → AttributeError interno → False + log forense (antes: silencio)."""
    with patch("app.routers.whatsapp.logger") as mock_logger:
        assert _is_valid_statuses({"entry": ["no-es-un-dict"]}) is False
        mock_logger.exception.assert_called_once()


def test_is_valid_statuses_happy_path_untouched():
    """INVARIANTE: payload statuses válido → True y CERO logging de excepción."""
    payload = {"entry": [{"changes": [{"value": {"statuses": [{"id": "wamid.1"}]}}]}]}
    with patch("app.routers.whatsapp.logger") as mock_logger:
        assert _is_valid_statuses(payload) is True
        mock_logger.exception.assert_not_called()


def test_is_valid_message_fallback_on_malformed_payload():
    """entry no-dict → AttributeError interno → False + log forense."""
    with patch("app.routers.whatsapp.logger") as mock_logger:
        assert _is_valid_message({"entry": ["no-es-un-dict"]}) is False
        mock_logger.exception.assert_called_once()


def test_is_valid_message_happy_path_untouched():
    """INVARIANTE: payload messages válido → True y CERO logging de excepción."""
    payload = {"entry": [{"changes": [{"value": {"messages": [{"id": "wamid.1"}]}}]}]}
    with patch("app.routers.whatsapp.logger") as mock_logger:
        assert _is_valid_message(payload) is True
        mock_logger.exception.assert_not_called()


def test_extract_message_data_fallback_none_on_keyerror():
    """messages[0] sin 'from' → KeyError interno → None + log forense."""
    payload = {"entry": [{"changes": [{"value": {"messages": [{"type": "text"}]}}]}]}
    with patch("app.routers.whatsapp.logger") as mock_logger:
        assert _extract_message_data(payload) is None
        mock_logger.exception.assert_called_once()


def test_extract_message_data_happy_path_untouched():
    """INVARIANTE: extracción completa de mensaje text permanece intacta."""
    payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "metadata": {"phone_number_id": "123"},
                    "messages": [{
                        "from": "573000000000",
                        "id": "wamid.abc",
                        "timestamp": "1622548800",
                        "type": "text",
                        "text": {"body": "hola"},
                    }],
                }
            }]
        }]
    }
    with patch("app.routers.whatsapp.logger") as mock_logger:
        data = _extract_message_data(payload)
        assert data is not None
        assert data["from"] == "573000000000"
        assert data["id"] == "wamid.abc"
        assert data["type"] == "text"
        assert data["text"] == "hola"
        assert data["phone_number_id"] == "123"
        mock_logger.exception.assert_not_called()


def test_is_valid_statuses_non_dict_payload_guard():
    """REGRESIÓN del guard PII: payload top-level no-dict → False sin romper el handler."""
    with patch("app.routers.whatsapp.logger") as mock_logger:
        assert _is_valid_statuses(["no", "soy", "dict"]) is False
        mock_logger.exception.assert_called_once()

