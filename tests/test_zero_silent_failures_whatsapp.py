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
    mock_config_loader = MagicMock()
    mock_catalog = MagicMock()
    mock_config_service = MagicMock()
    mock_judge = AsyncMock()
    mock_wa_service = AsyncMock()

    with patch("app.routers.whatsapp.db", mock_db), \
         patch("app.routers.whatsapp.message_buffer", mock_message_buffer), \
         patch("app.routers.whatsapp.config_loader", mock_config_loader), \
         patch("app.routers.whatsapp.catalog_service_local", mock_catalog), \
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
    mock_config_loader = MagicMock()
    mock_catalog = MagicMock()
    mock_config_service = MagicMock()
    mock_judge = AsyncMock()
    mock_wa_service = AsyncMock()

    with patch("app.routers.whatsapp.db", mock_db), \
         patch("app.routers.whatsapp.message_buffer", mock_message_buffer), \
         patch("app.routers.whatsapp.config_loader", mock_config_loader), \
         patch("app.routers.whatsapp.catalog_service_local", mock_catalog), \
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
    mock_config_loader = MagicMock()
    mock_catalog = MagicMock()
    mock_config_service = MagicMock()
    mock_judge = AsyncMock()
    mock_wa_service = AsyncMock()

    with patch("app.routers.whatsapp.db", mock_db), \
         patch("app.routers.whatsapp.message_buffer", mock_message_buffer), \
         patch("app.routers.whatsapp.config_loader", mock_config_loader), \
         patch("app.routers.whatsapp.catalog_service_local", mock_catalog), \
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

