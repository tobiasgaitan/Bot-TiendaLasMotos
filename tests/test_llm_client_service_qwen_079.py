"""
Tests BOT-BUILD-MIGRATE-QWEN-079 — Fase F1 (adapter dormido).

Ficheros creados:
  - app/services/llm_client_service.py (DualProviderClient)
  - tests/test_llm_client_service_qwen_079.py (este archivo)

Restricción: NO modificar prompts.py, personality.json, ai_brain.py,
vision_service.py, judge_service.py, audio_service.py, admin.py,
config_loader.py ni workflows.
"""

import asyncio
import base64
import json
import logging
import os
from enum import Enum
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pydantic import BaseModel

from app.services.genai_client_service import reset_shared_clients
from app.services.genai_client_service import get_shared_genai_client
from app.services.llm_client_service import (
    DualProviderClient,
    _parse_openai_response,
    format_qwen_error_structured,
    get_active_model_id,
    get_shared_llm_client,
    get_shared_llm_client_async,
    is_qwen_enabled,
    reset_shared_llm_clients,
)

try:
    from google import genai
    from google.genai import types

    SDK_AVAILABLE = True
except ImportError:  # pragma: no cover
    genai = None
    types = None
    SDK_AVAILABLE = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _openai_response_json(
    content: Any = None,
    tool_calls: List[Dict[str, Any]] = None,
    usage: Dict[str, int] = None,
) -> Dict[str, Any]:
    message: Dict[str, Any] = {"role": "assistant"}
    if tool_calls:
        message["tool_calls"] = tool_calls
        message["content"] = None
    elif isinstance(content, str):
        message["content"] = content
    else:
        message["content"] = content

    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
        "usage": usage or {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


def _make_mock_post(response_data: Dict[str, Any], status: int = 200):
    """Crea un mock para httpx.AsyncClient.post / httpx.Client.post."""
    mock_response = MagicMock()
    mock_response.status_code = status
    mock_response.json.return_value = response_data
    mock_response.raise_for_status.return_value = None
    return AsyncMock(return_value=mock_response)


def _gemini_response(text: str = "gemini fallback"):
    """Crea un mock de respuesta google-genai mínimo."""
    response = MagicMock()
    response.text = text
    part = MagicMock()
    part.text = text
    part.function_call = None
    candidate = MagicMock()
    content = MagicMock()
    content.parts = [part]
    candidate.content = content
    response.candidates = [candidate]
    usage = MagicMock()
    usage.prompt_token_count = 1
    usage.candidates_token_count = 1
    usage.total_token_count = 2
    response.usage_metadata = usage
    return response


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Limpia singletons LLM y genai entre tests."""
    reset_shared_llm_clients()
    reset_shared_clients()
    yield
    reset_shared_llm_clients()
    reset_shared_clients()


@pytest.fixture
def qwen_env(monkeypatch):
    """Ambiente Qwen habilitado para tests."""
    monkeypatch.setenv("QWEN_ENABLED", "true")
    monkeypatch.setenv("QWEN_BASE_URL", "https://qwen.test")
    monkeypatch.setenv("QWEN_OMNI_API_KEY", "test-qwen-key")
    monkeypatch.setenv("QWEN_PRIMARY_MODEL", "qwen-omni-turbo")
    monkeypatch.setenv("QWEN_CALL_TIMEOUT_S", "21")
    monkeypatch.setenv("GEMINI_MODEL_ID", "gemini-2.5-flash")


# ---------------------------------------------------------------------------
# T1 — OFF default; backend Gemini singleton real + delegación __getattr__
# ---------------------------------------------------------------------------
def test_t1_off_default_backend_is_gemini_singleton_and_list_delegates(monkeypatch):
    """T1: Con QWEN_ENABLED=false el backend del facade es el singleton real de
    get_shared_genai_client y facade.models.list() delega correctamente."""
    monkeypatch.delenv("QWEN_ENABLED", raising=False)

    with patch("app.services.genai_client_service.genai.Client") as mock_client_class:
        mock_gemini = MagicMock()
        mock_client_class.return_value = mock_gemini

        facade = get_shared_llm_client()
        backend = get_shared_genai_client(
            vertexai=True,
            project="tiendalasmotos",
            location="us-central1",
        )

        # El backend del facade ES el singleton real
        assert facade._gemini_sync is backend
        # Y el singleton es el mock creado por el patch
        assert facade._gemini_sync is mock_gemini

        # Delegación genérica
        facade.models.list()
        mock_gemini.models.list.assert_called_once()


# ---------------------------------------------------------------------------
# T2 — pin _model_id según env
# ---------------------------------------------------------------------------
def test_t2_model_id_off_default_and_env_override(monkeypatch):
    """T2: OFF → GEMINI_MODEL_ID (default gemini-2.5-flash); si se setea env,
    respeta el valor."""
    monkeypatch.delenv("QWEN_ENABLED", raising=False)
    monkeypatch.delenv("GEMINI_MODEL_ID", raising=False)

    with patch("app.services.genai_client_service.genai.Client"):
        facade = get_shared_llm_client()
        assert facade._model_id == "gemini-2.5-flash"
        assert get_active_model_id() == "gemini-2.5-flash"

    monkeypatch.setenv("GEMINI_MODEL_ID", "gemini-custom-pro")
    reset_shared_llm_clients()
    with patch("app.services.genai_client_service.genai.Client"):
        facade2 = get_shared_llm_client()
        assert facade2._model_id == "gemini-custom-pro"
        assert get_active_model_id() == "gemini-custom-pro"


# ---------------------------------------------------------------------------
# T3 — traducción config → OpenAI params
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t3_config_translation_to_openai_params(qwen_env, monkeypatch):
    """T3: temperature, max_output_tokens clamp a 2048, response_format json_object."""
    monkeypatch.setattr(
        "app.services.llm_client_service.is_qwen_enabled", lambda: True
    )

    response_data = _openai_response_json(content='{"ok": true}')
    with patch("httpx.AsyncClient.post", _make_mock_post(response_data)) as mock_post:
        facade = await get_shared_llm_client_async()
        await facade.aio.models.generate_content(
            model="qwen-omni-turbo",
            contents="hello",
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=4096,
                response_mime_type="application/json",
            ),
        )

        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        assert payload["temperature"] == 0.7
        assert payload["max_tokens"] == 2048
        assert payload["response_format"] == {"type": "json_object"}
        assert payload["model"] == "qwen-omni-turbo"


# ---------------------------------------------------------------------------
# T4 — traducción contents multimodal
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t4_multimodal_contents_translation(qwen_env, monkeypatch):
    """T4: texto, image_url data URL y audio input_audio se traducen al payload OpenAI.

    Nota: audio va a Gemini por defecto (guard de audio). Se activa QWEN_AUDIO_ENABLED
    para certificar que la traducción input_audio sigue disponible vía opt-in.
    """
    monkeypatch.setattr(
        "app.services.llm_client_service.is_qwen_enabled", lambda: True
    )
    monkeypatch.setenv("QWEN_AUDIO_ENABLED", "true")

    image_bytes = b"fake-image-png"
    audio_bytes = b"fake-audio-wav"
    image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/png")
    audio_part = types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav")
    contents = ["describe", image_part, audio_part]

    response_data = _openai_response_json(content="ok")
    with patch("httpx.AsyncClient.post", _make_mock_post(response_data)) as mock_post:
        facade = await get_shared_llm_client_async()
        await facade.aio.models.generate_content(
            model="qwen-omni-turbo",
            contents=contents,
        )

        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        user_msg = payload["messages"][-1]
        assert user_msg["role"] == "user"
        assert len(user_msg["content"]) == 3

        text_item = user_msg["content"][0]
        assert text_item["type"] == "text"
        assert text_item["text"] == "describe"

        image_item = user_msg["content"][1]
        assert image_item["type"] == "image_url"
        assert image_item["image_url"]["url"].startswith("data:image/png;base64,")
        b64 = image_item["image_url"]["url"].split(",")[-1]
        assert base64.b64decode(b64) == image_bytes

        audio_item = user_msg["content"][2]
        assert audio_item["type"] == "input_audio"
        assert audio_item["input_audio"]["format"] == "wav"


# ---------------------------------------------------------------------------
# T5 — Rama A: tool_calls nativos → function_call google-shaped
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t5_rama_a_native_toolcalls(qwen_env, monkeypatch):
    """T5: tools nativas se pasan serializadas a JSON; tool_calls de Qwen se mapean a parts function_call."""
    monkeypatch.setattr(
        "app.services.llm_client_service.is_qwen_enabled", lambda: True
    )
    monkeypatch.setenv("QWEN_TOOLCALL_MODE", "native")

    response_data = _openai_response_json(
        tool_calls=[
            {
                "id": "call_abc",
                "type": "function",
                "function": {
                    "name": "search_catalog",
                    "arguments": json.dumps({"query": "Apache 160"}),
                },
            }
        ]
    )

    tool_decl = types.FunctionDeclaration(
        name="search_catalog",
        description="Busca motos",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    )

    with patch("httpx.AsyncClient.post", _make_mock_post(response_data)) as mock_post:
        facade = await get_shared_llm_client_async()
        response = await facade.aio.models.generate_content(
            model="qwen-omni-turbo",
            contents="busco Apache 160",
            config=types.GenerateContentConfig(
                temperature=0.2,
                tools=[types.Tool(function_declarations=[tool_decl])],
            ),
        )

        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        assert "tools" in payload
        assert payload["tools"][0]["type"] == "function"
        assert payload["tools"][0]["function"]["name"] == "search_catalog"

        # [BOT-PLAN-GATES-OVERRIDE-080] Pin reforzado: mordida contra schema sin serializar.
        # Si _convert_tools_to_openai deja instancias types.Schema, json.dumps explota.
        assert json.dumps(payload) is not None
        parameters = payload["tools"][0]["function"]["parameters"]
        assert isinstance(parameters, dict)
        assert parameters.get("type", "").lower() == "object"
        assert "properties" in parameters
        assert "query" in parameters["properties"]
        assert parameters.get("required") == ["query"]

        parts = response.candidates[0].content.parts
        assert len(parts) == 1
        assert parts[0].function_call.name == "search_catalog"
        assert parts[0].function_call.args == {"query": "Apache 160"}


def test_t5b_convert_tools_to_openai_serializes_schema():
    """T5b: _convert_tools_to_openai devuelve dicts JSON-nativos incluso cuando
    google-genai expone types.Schema en decl.parameters."""
    from app.services.llm_client_service import _convert_tools_to_openai

    tool = types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="calculate_credit_score",
                description="Calcula score",
                parameters={
                    "type": "object",
                    "properties": {
                        "ingresos_mensuales": {"type": "string"},
                        "gastos_mensuales": {"type": "string"},
                    },
                    "required": ["ingresos_mensuales", "gastos_mensuales"],
                },
            )
        ]
    )
    openai_tools = _convert_tools_to_openai([tool])
    assert len(openai_tools) == 1
    assert openai_tools[0]["type"] == "function"
    func = openai_tools[0]["function"]
    assert func["name"] == "calculate_credit_score"
    # Mordida: la salida debe ser serializable por httpx/json.dumps.
    assert json.dumps(openai_tools) is not None
    parameters = func["parameters"]
    assert isinstance(parameters, dict)
    assert parameters["type"].lower() == "object"
    assert set(parameters["properties"].keys()) == {"ingresos_mensuales", "gastos_mensuales"}
    assert parameters["required"] == ["ingresos_mensuales", "gastos_mensuales"]


# ---------------------------------------------------------------------------
# T6 — Rama B: directiva JSON emulada
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t6_rama_b_emulated_toolcall(qwen_env, monkeypatch):
    """T6: Rama B no envía tools; parsea JSON y sintetiza function_call."""
    monkeypatch.setattr(
        "app.services.llm_client_service.is_qwen_enabled", lambda: True
    )
    monkeypatch.setenv("QWEN_TOOLCALL_MODE", "emulated")

    response_data = _openai_response_json(
        content=json.dumps({"tool_call": {"name": "search_catalog", "args": {"query": "Apache 160"}}})
    )

    with patch("httpx.AsyncClient.post", _make_mock_post(response_data)) as mock_post:
        facade = await get_shared_llm_client_async()
        response = await facade.aio.models.generate_content(
            model="qwen-omni-turbo",
            contents="busco Apache 160",
            config=types.GenerateContentConfig(temperature=0.2),
        )

        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        # Rama B: NO debe aparecer tools
        assert "tools" not in payload
        # La directiva JSON debe estar en el system message
        system_msg = payload["messages"][0]
        assert system_msg["role"] == "system"
        assert "TRANSPORT TOOLCALL DIRECTIVE" in system_msg["content"]

        parts = response.candidates[0].content.parts
        assert parts[0].function_call.name == "search_catalog"
        assert parts[0].function_call.args == {"query": "Apache 160"}


# ---------------------------------------------------------------------------
# T7 — Failover DUAL DashScope → Gemini
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t7_dual_failover_to_gemini(qwen_env, monkeypatch, caplog):
    """T7: error DashScope → Gemini recibe payload original y log [DUAL FAILOVER]."""
    caplog.set_level(logging.WARNING)
    monkeypatch.setattr(
        "app.services.llm_client_service.is_qwen_enabled", lambda: True
    )
    monkeypatch.setenv("QWEN_TOOLCALL_MODE", "native")

    gemini_response = _gemini_response(text="fallback desde gemini")

    with patch(
        "httpx.AsyncClient.post", side_effect=httpx.TimeoutException("timeout")
    ) as mock_post:
        with patch(
            "app.services.genai_client_service.genai.Client"
        ) as mock_client_class:
            mock_gemini = MagicMock()
            mock_gemini.aio.models.generate_content = AsyncMock(return_value=gemini_response)
            mock_client_class.return_value = mock_gemini

            facade = await get_shared_llm_client_async()
            response = await facade.aio.models.generate_content(
                model="qwen-omni-turbo",
                contents=["prompt"],
                config=types.GenerateContentConfig(temperature=0.2),
            )

            assert response.text == "fallback desde gemini"
            mock_gemini.aio.models.generate_content.assert_awaited_once()
            _, kwargs = mock_gemini.aio.models.generate_content.call_args
            # F1.5: failover DEBE usar el model ID de Gemini, no el de Qwen.
            assert kwargs["model"] == "gemini-2.5-flash"
            assert kwargs["contents"] == ["prompt"]
            assert kwargs["config"] is not None

    assert "[DUAL FAILOVER]" in caplog.text
    assert "provider=dashscope→gemini" in caplog.text
    assert "forensic=" in caplog.text


# ---------------------------------------------------------------------------
# T8 — Sin Gemini backend o sin gate → raise
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t8_no_gemini_backend_raises(qwen_env, monkeypatch):
    """T8: si Qwen falla y Gemini no está disponible, no hay respaldo muerto."""
    monkeypatch.setattr(
        "app.services.llm_client_service.is_qwen_enabled", lambda: True
    )

    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("timeout")):
        with patch(
            "app.services.llm_client_service.get_shared_genai_client_async",
            return_value=None,
        ):
            facade = await get_shared_llm_client_async()
            with pytest.raises(RuntimeError) as exc_info:
                await facade.aio.models.generate_content(
                    model="qwen-omni-turbo",
                    contents="hola",
                )
            assert "Gemini backend not available" in str(exc_info.value)


# ---------------------------------------------------------------------------
# T9 — Presupuesto de contexto 33K
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t9_context_budget_trims_and_failover(qwen_env, monkeypatch, caplog):
    """T9: historial viejo se recorta; turno actual over-budget → failover + log [QWEN CONTEXT]."""
    monkeypatch.setattr(
        "app.services.llm_client_service.is_qwen_enabled", lambda: True
    )
    caplog.set_level(logging.ERROR)

    captured_messages: List[Dict[str, Any]] = []

    async def _capture_post(*args, **kwargs):
        captured_messages.append(kwargs["json"]["messages"])
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _openai_response_json(content="ok")
        mock_response.raise_for_status.return_value = None
        return mock_response

    with patch("httpx.AsyncClient.post", _capture_post):
        facade = await get_shared_llm_client_async()
        chat = facade.aio.chats.create(model="qwen-omni-turbo")

        # Poblar historial
        for i in range(5):
            await chat.send_message(f"mensaje {i}")

        # Mensaje largo: debe recortar historial antiguo preservando turno actual
        long_msg = "x" * 80_000
        await chat.send_message(long_msg)

    final_messages = captured_messages[-1]
    assert final_messages[-1]["role"] == "user"
    assert long_msg in str(final_messages)

    # F1.5 (NB-c): el annex/directive de transporte con role=system nunca es
    # eviccionado. En modo nativo sin schema no hay system; forzamos emulated.
    reset_shared_llm_clients()
    reset_shared_clients()
    captured_system_test: List[Dict[str, Any]] = []
    monkeypatch.setenv("QWEN_TOOLCALL_MODE", "emulated")

    async def _capture_system_test(*args, **kwargs):
        captured_system_test.append(kwargs["json"]["messages"])
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _openai_response_json(content="ok")
        mock_response.raise_for_status.return_value = None
        return mock_response

    with patch("httpx.AsyncClient.post", _capture_system_test):
        facade = await get_shared_llm_client_async()
        chat = facade.aio.chats.create(model="qwen-omni-turbo")
        for i in range(5):
            await chat.send_message(f"mensaje preservado {i}")
        long_msg2 = "y" * 80_000
        await chat.send_message(long_msg2)

    final_system_test = captured_system_test[-1]
    assert final_system_test[0]["role"] == "system"
    assert "TRANSPORT TOOLCALL DIRECTIVE" in final_system_test[0]["content"]
    assert long_msg2 in str(final_system_test)

    # Turno actual solo excede presupuesto → failover a Gemini
    gemini_response = _gemini_response(text="gemini por exceso")
    reset_shared_llm_clients()
    reset_shared_clients()

    with patch("httpx.AsyncClient.post") as mock_post:
        with patch(
            "app.services.genai_client_service.genai.Client"
        ) as mock_client_class:
            mock_gemini = MagicMock()
            mock_gemini.aio.models.generate_content = AsyncMock(return_value=gemini_response)
            mock_client_class.return_value = mock_gemini

            facade = await get_shared_llm_client_async()
            chat = facade.aio.chats.create(model="qwen-omni-turbo")
            huge_msg = "x" * 200_000
            response = await chat.send_message(huge_msg)

            assert response.text == "gemini por exceso"
            mock_post.assert_not_called()
            mock_gemini.aio.models.generate_content.assert_awaited_once()

    assert "[QWEN CONTEXT]" in caplog.text
    assert "budget_exceeded" in caplog.text


# ---------------------------------------------------------------------------
# T10 — format_qwen_error_structured PII-safe
# ---------------------------------------------------------------------------
def test_t10_format_qwen_error_structured_pii_safe():
    """T10: whitelist PII-safe y fallback no-vacío."""
    # Error con campos permitidos
    class DummyError(Exception):
        code = "InvalidParameter"
        status = 400
        request_id = "req-123"

    formatted = format_qwen_error_structured(DummyError("mensaje con PII"))
    assert "code='InvalidParameter'" in formatted
    assert "status=400" in formatted
    assert "request_id='req-123'" in formatted
    # El mensaje de error (PII) NO debe filtrarse
    assert "mensaje con PII" not in formatted
    assert "body_redacted" not in formatted

    # Error sin campos permitidos → fallback no-vacío
    class PlainError(Exception):
        pass

    fallback = format_qwen_error_structured(PlainError("PII"))
    assert fallback
    assert "error_type='PlainError'" in fallback
    assert "body_redacted=True" in fallback


# ---------------------------------------------------------------------------
# T11 — Rollback Firestore flip
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t11_firestore_flag_rollback_to_gemini(qwen_env, monkeypatch):
    """T11: flip del flag Firestore → siguiente llamada 100% Gemini sin restart."""

    class FakeDoc:
        def __init__(self, value: bool):
            self._value = value

        def exists(self):
            return True

        def to_dict(self):
            return {"qwen_enabled": self._value}

    class FakeCollection:
        def __init__(self, value: bool):
            self._value = value

        def document(self, _name: str):
            class FakeDocRef:
                def get(self2):
                    return FakeDoc(self._value)

            return FakeDocRef()

    class FakeDb:
        def __init__(self, value: bool):
            self._value = value

        def collection(self, _name: str):
            return FakeCollection(self._value)

    # Llamada 1: flag True
    with patch("google.cloud.firestore.Client") as mock_fs:
        mock_fs.return_value = FakeDb(True)
        assert is_qwen_enabled() is True

    reset_shared_llm_clients()

    # Llamada 2: flag False
    with patch("google.cloud.firestore.Client") as mock_fs:
        mock_fs.return_value = FakeDb(False)
        assert is_qwen_enabled() is False

    # Ahora una llamada async debe ir 100% a Gemini
    gemini_response = _gemini_response(text="solo gemini")
    with patch("httpx.AsyncClient.post") as mock_post:
        with patch(
            "app.services.genai_client_service.genai.Client"
        ) as mock_client_class:
            mock_gemini = MagicMock()
            mock_gemini.aio.models.generate_content = AsyncMock(return_value=gemini_response)
            mock_client_class.return_value = mock_gemini

            facade = await get_shared_llm_client_async()
            response = await facade.aio.models.generate_content(
                model="qwen-omni-turbo",
                contents="hola",
            )

            assert response.text == "solo gemini"
            mock_post.assert_not_called()
            mock_gemini.aio.models.generate_content.assert_awaited_once()


# ---------------------------------------------------------------------------
# T12 — Usage mapping con nombres google
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t12_usage_mapping_google_names(qwen_env, monkeypatch):
    """T12: usage_metadata expone prompt_token_count, candidates_token_count, total_token_count."""
    monkeypatch.setattr(
        "app.services.llm_client_service.is_qwen_enabled", lambda: True
    )

    response_data = _openai_response_json(
        content="ok",
        usage={"prompt_tokens": 100, "completion_tokens": 40, "total_tokens": 140},
    )

    with patch("httpx.AsyncClient.post", _make_mock_post(response_data)):
        facade = await get_shared_llm_client_async()
        response = await facade.aio.models.generate_content(
            model="qwen-omni-turbo",
            contents="hola",
        )

        assert response.usage_metadata.prompt_token_count == 100
        assert response.usage_metadata.candidates_token_count == 40
        assert response.usage_metadata.total_token_count == 140


# ---------------------------------------------------------------------------
# T13 — Chat multi-turn orden mixto
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t13_chat_multiturn_ordering(qwen_env, monkeypatch):
    """T13: chat multi-turn conserva orden de text/function_call/function_response."""
    monkeypatch.setattr(
        "app.services.llm_client_service.is_qwen_enabled", lambda: True
    )
    monkeypatch.setenv("QWEN_TOOLCALL_MODE", "native")

    captured_messages: List[Dict[str, Any]] = []

    def _make_side_effect_sequence():
        counter = 0

        async def _side_effect(*args, **kwargs):
            nonlocal counter
            captured_messages.append(kwargs["json"]["messages"])
            counter += 1
            if counter == 1:
                # Respuesta del asistente con tool_call
                return _async_response(
                    _openai_response_json(
                        tool_calls=[
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "search_catalog",
                                    "arguments": json.dumps({"query": "Apache"}),
                                },
                            }
                        ]
                    )
                )
            else:
                # Respuesta final de texto
                return _async_response(_openai_response_json(content="La Apache cuesta $8M"))

        return _side_effect

    def _async_response(data):
        m = MagicMock()
        m.status_code = 200
        m.json.return_value = data
        m.raise_for_status.return_value = None
        return m

    with patch("httpx.AsyncClient.post", side_effect=_make_side_effect_sequence()):
        facade = await get_shared_llm_client_async()
        chat = facade.aio.chats.create(model="qwen-omni-turbo")

        # Turno 1: usuario
        await chat.send_message("busco Apache")
        # Turno 2: función (model hace function_call)
        # Turno 3: usuario devuelve function_response
        await chat.send_message(
            [
                types.Part.from_function_response(
                    name="search_catalog",
                    response={"result": "Apache 160"},
                )
            ]
        )
        # Turno 4: asistente final
        response = await chat.send_message("cuánto cuesta")
        assert response.text == "La Apache cuesta $8M"

    # Verificar que en el payload del último turno el orden es correcto:
    # system, user1, assistant(tool_call), tool, user3, user4
    final = captured_messages[-1]
    roles = [m["role"] for m in final]
    assert "assistant" in roles
    assert "tool" in roles
    # user1 antes de assistant
    assert roles.index("user") < roles.index("assistant")
    # tool después de assistant
    assert roles.index("assistant") < roles.index("tool")


# ---------------------------------------------------------------------------
# T14 — EXTRACION_SCHEMA complejo
# ---------------------------------------------------------------------------
class _T14Color(Enum):
    rojo = "rojo"
    azul = "azul"


class _T14Address(BaseModel):
    city: str
    phone: str


class _T14Profile(BaseModel):
    name: str
    age: int
    color: _T14Color
    address: _T14Address


@pytest.mark.asyncio
async def test_t14_complex_response_schema_translation(qwen_env, monkeypatch):
    """T14: response_schema complejo se serializa a JSON válido y se inyecta en system."""
    monkeypatch.setattr(
        "app.services.llm_client_service.is_qwen_enabled", lambda: True
    )

    response_data = _openai_response_json(content="ok")
    with patch("httpx.AsyncClient.post", _make_mock_post(response_data)) as mock_post:
        facade = await get_shared_llm_client_async()
        await facade.aio.models.generate_content(
            model="qwen-omni-turbo",
            contents="extrae perfil",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_T14Profile,
            ),
        )

        _, kwargs = mock_post.call_args
        messages = kwargs["json"]["messages"]
        system_msg = messages[0]
        assert system_msg["role"] == "system"
        content = system_msg["content"]
        assert "TRANSPORT SCHEMA ANNEX" in content

        # Extraer JSON del annex (aislado de FIELD RULES posteriores)
        prefix = "[TRANSPORT SCHEMA ANNEX] You MUST obey this JSON schema: "
        schema_json = content.split(prefix, 1)[1].split("\n[", 1)[0]
        schema = json.loads(schema_json)
        assert schema["type"] == "OBJECT"
        assert "properties" in schema
        assert "name" in schema["properties"]
        assert "age" in schema["properties"]
        # Enum de color presente
        assert "enum" in schema["properties"]["color"]
        assert set(schema["properties"]["color"]["enum"]) == {"rojo", "azul"}
        # Nested object
        assert schema["properties"]["address"]["type"] == "OBJECT"


# ---------------------------------------------------------------------------
# T15 — Concurrencia N=50
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t15_concurrency_n50(qwen_env, monkeypatch):
    """T15: 50 llamadas paralelas sin corrupción."""
    monkeypatch.setattr(
        "app.services.llm_client_service.is_qwen_enabled", lambda: True
    )

    response_data = _openai_response_json(content="ok")
    with patch("httpx.AsyncClient.post", _make_mock_post(response_data)) as mock_post:
        facade = await get_shared_llm_client_async()

        async def _call(i: int):
            return await facade.aio.models.generate_content(
                model="qwen-omni-turbo",
                contents=f"msg {i}",
            )

        results = await asyncio.gather(*(_call(i) for i in range(50)))

        assert len(results) == 50
        assert all(r.text == "ok" for r in results)
        assert mock_post.await_count == 50


# ---------------------------------------------------------------------------
# T16 — Clasificación de timeouts
# ---------------------------------------------------------------------------
def test_t16_timeout_classification(qwen_env, monkeypatch):
    """T16: QWEN_CALL_TIMEOUT_S y effective_gemini_timeout_s se respetan."""
    import app.core.deadline_policy as deadline_module
    from app.services.llm_client_service import _gemini_timeout_default, _qwen_timeout_default

    # Con QWEN_CALL_TIMEOUT_S=21 seteado en fixture
    assert _qwen_timeout_default() == 21.0

    # Gemini timeout default respeta GEMINI_CALL_TIMEOUT_S o ai_brain constante
    monkeypatch.setenv("GEMINI_CALL_TIMEOUT_S", "30")
    assert _gemini_timeout_default() == 30.0

    # effective_gemini_timeout_s respeta GEMINI_COLD_CALL_TIMEOUT_S cuando la política está activa
    monkeypatch.setenv("GEMINI_COLD_CALL_TIMEOUT_S", "45")
    monkeypatch.setenv("COLD_WINDOW_S", "99999")
    monkeypatch.setattr(deadline_module, "GEMINI_COLD_CALL_TIMEOUT_S", 45.0)
    monkeypatch.setattr(deadline_module, "COLD_WINDOW_S", 99999.0)
    assert deadline_module.effective_gemini_timeout_s() == 45.0


# ---------------------------------------------------------------------------
# T17 — Candado H3: directiva Rama B NO está en prompts/personality
# ---------------------------------------------------------------------------
def test_t17_rama_b_directive_not_in_prompt_assets():
    """T17: la directiva JSON de Rama B aparece en payload httpx y NO en prompts.py ni personality.json."""
    directive = "TRANSPORT TOOLCALL DIRECTIVE"

    with open("app/core/prompts.py", "r", encoding="utf-8") as f:
        prompts_text = f.read()
    with open("app/core/personality.json", "r", encoding="utf-8") as f:
        personality_text = f.read()

    assert directive not in prompts_text
    assert directive not in personality_text


# ---------------------------------------------------------------------------
# T18 — Chat: turno actual exactamente una vez; function_response → tool válido
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t18_chat_current_turn_exactly_once_and_tool_message(qwen_env, monkeypatch):
    """T18: send_message no duplica el turno actual y convierte function_response a role='tool'."""
    monkeypatch.setattr(
        "app.services.llm_client_service.is_qwen_enabled", lambda: True
    )
    monkeypatch.setenv("QWEN_TOOLCALL_MODE", "native")

    captured: List[List[Dict[str, Any]]] = []
    counter = 0

    def _async_response(data):
        m = MagicMock()
        m.status_code = 200
        m.json.return_value = data
        m.raise_for_status.return_value = None
        return m

    async def _side_effect(*args, **kwargs):
        nonlocal counter
        captured.append(kwargs["json"]["messages"])
        counter += 1
        if counter == 1:
            return _async_response(
                _openai_response_json(
                    tool_calls=[
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "search_catalog",
                                "arguments": json.dumps({"query": "Apache 160"}),
                            },
                        }
                    ]
                )
            )
        return _async_response(_openai_response_json(content="La Apache cuesta $8M"))

    with patch("httpx.AsyncClient.post", side_effect=_side_effect):
        facade = await get_shared_llm_client_async()
        chat = facade.aio.chats.create(model="qwen-omni-turbo")

        await chat.send_message("busco Apache 160")
        await chat.send_message(
            [
                types.Part.from_function_response(
                    name="search_catalog",
                    response={"result": "Apache 160 disponible"},
                )
            ]
        )
        response = await chat.send_message("cuánto cuesta")
        assert response.text == "La Apache cuesta $8M"

    second_turn = captured[1]
    tool_msgs = [m for m in second_turn if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    assert json.loads(tool_msgs[0]["content"]) == {"result": "Apache 160 disponible"}

    # El turno actual (function_response) no debe aparecer como content tipo inválido
    for msg in second_turn:
        content = msg.get("content")
        if isinstance(content, list):
            for frag in content:
                assert frag.get("type") != "function_response"

    # El prompt del usuario aparece exactamente una vez en todo el payload
    payload_text = json.dumps(captured[-1], ensure_ascii=False)
    assert payload_text.count("busco Apache 160") == 1


# ---------------------------------------------------------------------------
# T19 — Failover usa GEMINI_MODEL_ID en los 3 caminos
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t19_failover_uses_gemini_model_id(qwen_env, monkeypatch):
    """T19: todas las patas de failover envían el model ID de Gemini, no el de Qwen."""
    monkeypatch.setenv("GEMINI_MODEL_ID", "gemini-2.5-flash-test")
    monkeypatch.setattr(
        "app.services.llm_client_service.is_qwen_enabled", lambda: True
    )

    gemini_response = _gemini_response(text="fallback")

    # Camino async generate_content
    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("timeout")):
        with patch(
            "app.services.genai_client_service.genai.Client"
        ) as mock_client_class:
            mock_gemini = MagicMock()
            mock_gemini.aio.models.generate_content = AsyncMock(return_value=gemini_response)
            mock_client_class.return_value = mock_gemini

            facade = await get_shared_llm_client_async()
            await facade.aio.models.generate_content(
                model="qwen-omni-turbo",
                contents="hola",
            )
            _, kwargs = mock_gemini.aio.models.generate_content.call_args
            assert kwargs["model"] == "gemini-2.5-flash-test"

    # Camino chat send_message
    reset_shared_llm_clients()
    reset_shared_clients()
    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("timeout")):
        with patch(
            "app.services.genai_client_service.genai.Client"
        ) as mock_client_class:
            mock_gemini = MagicMock()
            mock_gemini.aio.models.generate_content = AsyncMock(return_value=gemini_response)
            mock_client_class.return_value = mock_gemini

            facade = await get_shared_llm_client_async()
            chat = facade.aio.chats.create(model="qwen-omni-turbo")
            await chat.send_message("hola chat")
            _, kwargs = mock_gemini.aio.models.generate_content.call_args
            assert kwargs["model"] == "gemini-2.5-flash-test"

    # Camino sync generate_content
    reset_shared_llm_clients()
    reset_shared_clients()
    monkeypatch.setenv("QWEN_CALL_TIMEOUT_S", "1")
    with patch("httpx.Client.post", side_effect=httpx.TimeoutException("timeout")):
        with patch(
            "app.services.genai_client_service.genai.Client"
        ) as mock_client_class:
            mock_gemini = MagicMock()
            mock_gemini.models.generate_content = MagicMock(return_value=gemini_response)
            mock_client_class.return_value = mock_gemini

            facade = get_shared_llm_client()
            facade.models.generate_content(
                model="qwen-omni-turbo",
                contents="hola sync",
            )
            _, kwargs = mock_gemini.models.generate_content.call_args
            assert kwargs["model"] == "gemini-2.5-flash-test"


# ---------------------------------------------------------------------------
# T20 — Rama B: .text nunca devuelve el envelope JSON crudo
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t20_rama_b_text_not_raw_envelope(qwen_env, monkeypatch):
    """T20: Rama B parsea 'final' y text es el contenido limpio, no el JSON."""
    monkeypatch.setattr(
        "app.services.llm_client_service.is_qwen_enabled", lambda: True
    )
    monkeypatch.setenv("QWEN_TOOLCALL_MODE", "emulated")

    response_data = _openai_response_json(
        content=json.dumps({"final": "Texto limpio de Rama B"})
    )

    with patch("httpx.AsyncClient.post", _make_mock_post(response_data)):
        facade = await get_shared_llm_client_async()
        response = await facade.aio.models.generate_content(
            model="qwen-omni-turbo",
            contents="resume",
            config=types.GenerateContentConfig(temperature=0.2),
        )

        assert response.text == "Texto limpio de Rama B"
        parts = response.candidates[0].content.parts
        assert parts[0].text == "Texto limpio de Rama B"
        assert not getattr(parts[0], "function_call", None)


# ---------------------------------------------------------------------------
# T21 — get_active_model_id honra el rol (C5-098 cerrado)
# ---------------------------------------------------------------------------
def test_t21_get_active_model_id_honors_role(qwen_env, monkeypatch):
    """T21: get_active_model_id resuelve modelo por rol; fallback conservador."""
    monkeypatch.setattr("app.services.llm_client_service.is_qwen_enabled", lambda: True)

    # Env explícito por rol
    monkeypatch.setenv("QWEN_AGENTIC_MODEL", "qwen-turbo-agentic")
    monkeypatch.setenv("QWEN_MULTIMODAL_MODEL", "qwen-omni-multimodal")
    assert get_active_model_id("agentic") == "qwen-turbo-agentic"
    assert get_active_model_id("multimodal") == "qwen-omni-multimodal"
    assert get_active_model_id("unknown") == "qwen-omni-multimodal"  # fallback conservador

    # Fallback a QWEN_PRIMARY_MODEL cuando no hay env por rol
    monkeypatch.delenv("QWEN_AGENTIC_MODEL", raising=False)
    monkeypatch.delenv("QWEN_MULTIMODAL_MODEL", raising=False)
    assert get_active_model_id("agentic") == "qwen-omni-turbo"  # QWEN_PRIMARY_MODEL

    # Flag Qwen apagado → Gemini sin importar rol
    monkeypatch.setattr("app.services.llm_client_service.is_qwen_enabled", lambda: False)
    assert get_active_model_id("agentic") == "gemini-2.5-flash"


# ---------------------------------------------------------------------------
# T22 — cache del facade por rol; backend Gemini compartido; payload model por rol
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t22_facade_cache_per_role_shared_gemini_backend(qwen_env, monkeypatch):
    """T22: dos facades por rol, un único cliente Gemini subyacente; payload model por rol."""
    monkeypatch.setattr("app.services.llm_client_service.is_qwen_enabled", lambda: True)
    monkeypatch.setenv("QWEN_AGENTIC_MODEL", "qwen-turbo")
    monkeypatch.setenv("QWEN_MULTIMODAL_MODEL", "qwen-omni-turbo")

    gemini_constructor_calls = []

    def _mock_client_constructor(*args, **kwargs):
        gemini_constructor_calls.append(1)
        m = MagicMock()
        m.aio.models.generate_content = AsyncMock(return_value=_gemini_response("gemini"))
        m.models.generate_content = MagicMock(return_value=_gemini_response("gemini"))
        return m

    captured = []

    async def _fake_post(*args, **kwargs):
        captured.append(kwargs["json"])
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = _openai_response_json(content="ok")
        resp.raise_for_status.return_value = None
        return resp

    with patch("app.services.genai_client_service.genai.Client", side_effect=_mock_client_constructor):
        with patch("httpx.AsyncClient.post", side_effect=_fake_post):
            facade_agentic = await get_shared_llm_client_async(role="agentic")
            facade_multi = await get_shared_llm_client_async(role="multimodal")
            assert facade_agentic is not facade_multi
            assert facade_agentic._role == "agentic"
            assert facade_multi._role == "multimodal"

            await facade_agentic.aio.models.generate_content(model="ignored", contents="hola")
            await facade_multi.aio.models.generate_content(model="ignored", contents="hola")

    assert sum(gemini_constructor_calls) == 1  # mismo backend Gemini subyacente compartido
    assert captured[0]["model"] == "qwen-turbo"
    assert captured[1]["model"] == "qwen-omni-turbo"


# ---------------------------------------------------------------------------
# T23 — DualProviderChat hereda el rol del facade
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t23_chat_inherits_facade_role(qwen_env, monkeypatch):
    """T23: chats creados sin model heredan el rol del facade en el payload."""
    monkeypatch.setattr("app.services.llm_client_service.is_qwen_enabled", lambda: True)
    monkeypatch.setenv("QWEN_AGENTIC_MODEL", "qwen-turbo")
    monkeypatch.setenv("QWEN_MULTIMODAL_MODEL", "qwen-omni-turbo")

    captured = []

    async def _fake_post(*args, **kwargs):
        captured.append(kwargs["json"])
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = _openai_response_json(content="ok")
        resp.raise_for_status.return_value = None
        return resp

    with patch("httpx.AsyncClient.post", side_effect=_fake_post):
        facade_agentic = await get_shared_llm_client_async(role="agentic")
        chat_a = facade_agentic.aio.chats.create()
        await chat_a.send_message("hola agentic")

        facade_multi = await get_shared_llm_client_async(role="multimodal")
        chat_m = facade_multi.aio.chats.create()
        await chat_m.send_message("hola multimodal")

    assert captured[0]["model"] == "qwen-turbo"
    assert captured[1]["model"] == "qwen-omni-turbo"


# ---------------------------------------------------------------------------
# T24 — Failover DUAL usa GEMINI_MODEL_ID independientemente del rol
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t24_failover_uses_gemini_model_id_regardless_of_role(qwen_env, monkeypatch):
    """T24: el failover a Gemini envía GEMINI_MODEL_ID aunque el facade tenga rol agentic."""
    monkeypatch.setenv("GEMINI_MODEL_ID", "gemini-2.5-flash-role")
    monkeypatch.setattr("app.services.llm_client_service.is_qwen_enabled", lambda: True)
    gemini_response = _gemini_response(text="fallback")

    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("timeout")):
        with patch("app.services.genai_client_service.genai.Client") as mock_client_class:
            mock_gemini = MagicMock()
            mock_gemini.aio.models.generate_content = AsyncMock(return_value=gemini_response)
            mock_client_class.return_value = mock_gemini

            facade = await get_shared_llm_client_async(role="agentic")
            await facade.aio.models.generate_content(model="qwen-turbo", contents="hola")
            _, kwargs = mock_gemini.aio.models.generate_content.call_args
            assert kwargs["model"] == "gemini-2.5-flash-role"


# ---------------------------------------------------------------------------
# T25 — Audio: por defecto va a Gemini; nunca llega a DashScope
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t25_audio_pinned_to_gemini_by_default(qwen_env, monkeypatch):
    """T25: contenido con audio + flag Qwen on + QWEN_AUDIO_ENABLED ausente → path Gemini."""
    monkeypatch.setattr("app.services.llm_client_service.is_qwen_enabled", lambda: True)
    monkeypatch.delenv("QWEN_AUDIO_ENABLED", raising=False)

    audio_part = types.Part.from_bytes(data=b"fake-audio", mime_type="audio/wav")
    gemini_response = _gemini_response(text="transcripción gemini")

    httpx_calls: List[Dict[str, Any]] = []

    async def _capture_post(*args, **kwargs):
        httpx_calls.append(kwargs["json"])
        m = MagicMock()
        m.status_code = 200
        m.json.return_value = _openai_response_json(content="ok")
        m.raise_for_status.return_value = None
        return m

    with patch("httpx.AsyncClient.post", side_effect=_capture_post):
        with patch("app.services.genai_client_service.genai.Client") as mock_client_class:
            mock_gemini = MagicMock()
            mock_gemini.aio.models.generate_content = AsyncMock(return_value=gemini_response)
            mock_client_class.return_value = mock_gemini

            facade = await get_shared_llm_client_async(role="multimodal")
            response = await facade.aio.models.generate_content(
                model="qwen-omni-turbo",
                contents=["transcribe este audio", audio_part],
            )

            assert response.text == "transcripción gemini"
            assert len(httpx_calls) == 0
            _, kwargs = mock_gemini.aio.models.generate_content.call_args
            assert kwargs["model"] == os.getenv("GEMINI_MODEL_ID", "gemini-2.5-flash")


# ---------------------------------------------------------------------------
# T26 — Audio opt-in a Qwen; fail-closed: flag off anula opt-in
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t26_audio_opt_in_and_fail_closed(qwen_env, monkeypatch):
    """T26: QWEN_AUDIO_ENABLED=true envía audio a Qwen; flag off fuerza Gemini."""
    monkeypatch.setattr("app.services.llm_client_service.is_qwen_enabled", lambda: True)
    monkeypatch.setenv("QWEN_AUDIO_ENABLED", "true")

    audio_part = types.Part.from_bytes(data=b"fake-audio", mime_type="audio/wav")

    httpx_calls: List[Dict[str, Any]] = []

    async def _capture_post(*args, **kwargs):
        httpx_calls.append(kwargs["json"])
        m = MagicMock()
        m.status_code = 200
        m.json.return_value = _openai_response_json(content="ok")
        m.raise_for_status.return_value = None
        return m

    with patch("httpx.AsyncClient.post", side_effect=_capture_post):
        facade = await get_shared_llm_client_async(role="multimodal")
        await facade.aio.models.generate_content(
            model="qwen-omni-turbo",
            contents=["transcribe", audio_part],
        )
        assert len(httpx_calls) == 1

    # Fase 2: flag apagado anula el opt-in → Gemini
    reset_shared_llm_clients()
    reset_shared_clients()
    monkeypatch.setenv("QWEN_AUDIO_ENABLED", "true")
    monkeypatch.setattr("app.services.llm_client_service.is_qwen_enabled", lambda: False)
    gemini_response = _gemini_response(text="gemini")

    httpx_calls.clear()
    with patch("httpx.AsyncClient.post", side_effect=_capture_post):
        with patch("app.services.genai_client_service.genai.Client") as mock_client_class:
            mock_gemini = MagicMock()
            mock_gemini.aio.models.generate_content = AsyncMock(return_value=gemini_response)
            mock_client_class.return_value = mock_gemini

            facade = await get_shared_llm_client_async(role="multimodal")
            await facade.aio.models.generate_content(
                model="qwen-omni-turbo",
                contents=["transcribe", audio_part],
            )
            assert len(httpx_calls) == 0


# ---------------------------------------------------------------------------
# T27 — FIELD-RULES annex derivado del schema; ausente sin schema
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t27_field_rules_annex(qwen_env, monkeypatch):
    """T27: FIELD-RULES presente en rama Qwen con response_schema; ausente sin schema."""
    monkeypatch.setattr("app.services.llm_client_service.is_qwen_enabled", lambda: True)

    schema = types.Schema(
        type="OBJECT",
        properties={
            "name": types.Schema(type="STRING", description="Nombre del usuario"),
            "active": types.Schema(type="BOOLEAN"),
        },
        required=["name"],
    )

    captured: List[Dict[str, Any]] = []

    async def _capture_post(*args, **kwargs):
        captured.append(kwargs["json"])
        m = MagicMock()
        m.status_code = 200
        m.json.return_value = _openai_response_json(content="ok")
        m.raise_for_status.return_value = None
        return m

    with patch("httpx.AsyncClient.post", side_effect=_capture_post):
        facade = await get_shared_llm_client_async()
        await facade.aio.models.generate_content(
            model="qwen-turbo",
            contents="extrae",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        content = captured[0]["messages"][0]["content"]
        assert "[TRANSPORT FIELD RULES]" in content
        assert "name: extrae el valor literal" in content
        assert "active: responde true o false" in content

    # Sin response_schema: no FIELD RULES
    captured.clear()
    with patch("httpx.AsyncClient.post", side_effect=_capture_post):
        facade = await get_shared_llm_client_async()
        await facade.aio.models.generate_content(
            model="qwen-turbo",
            contents="hola",
            config=types.GenerateContentConfig(temperature=0.2),
        )
        content = captured[0]["messages"][0]["content"]
        assert "[TRANSPORT FIELD RULES]" not in content


# ---------------------------------------------------------------------------
# T28 — TOOLCALL RULES annex solo con tools; ausente sin tools
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_t28_toolcall_rules_annex(qwen_env, monkeypatch):
    """T28: TOOLCALL RULES presente solo en rama Qwen con tools."""
    monkeypatch.setattr("app.services.llm_client_service.is_qwen_enabled", lambda: True)

    tool = types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="search_catalog",
                description="Busca motos",
                parameters={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            )
        ]
    )

    captured: List[Dict[str, Any]] = []

    async def _capture_post(*args, **kwargs):
        captured.append(kwargs["json"])
        m = MagicMock()
        m.status_code = 200
        m.json.return_value = _openai_response_json(content="ok")
        m.raise_for_status.return_value = None
        return m

    with patch("httpx.AsyncClient.post", side_effect=_capture_post):
        facade = await get_shared_llm_client_async()
        await facade.aio.models.generate_content(
            model="qwen-turbo",
            contents="busco Apache",
            config=types.GenerateContentConfig(tools=[tool]),
        )
        content = captured[0]["messages"][0]["content"]
        assert "[TRANSPORT TOOLCALL RULES]" in content
        assert "Extrae como argumentos ÚNICAMENTE" in content

    # Sin tools: no TOOLCALL RULES
    captured.clear()
    with patch("httpx.AsyncClient.post", side_effect=_capture_post):
        facade = await get_shared_llm_client_async()
        await facade.aio.models.generate_content(
            model="qwen-turbo",
            contents="hola",
        )
        content = captured[0]["messages"][0]["content"]
        assert "[TRANSPORT TOOLCALL RULES]" not in content


# ---------------------------------------------------------------------------
# T29 — ARG-PRUNE: poda arg opcional fuera del léxico permitido
# ---------------------------------------------------------------------------
def test_t29_prunes_ungrounded_optional_arg(caplog):
    """T29: Rama A Qwen poda ocupacion='trabajo' (opcional, fuera de léxico)."""
    tools = [
        {
            "function_declarations": [
                {
                    "name": "calculate_credit_score",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ingresos_mensuales": {"type": "string"},
                            "gastos_mensuales": {"type": "string"},
                            "ocupacion": {"type": "string"},
                        },
                        "required": ["ingresos_mensuales", "gastos_mensuales"],
                    },
                }
            ]
        }
    ]
    tool_calls = [
        {
            "id": "call_1",
            "type": "function",
            "function": {
                "name": "calculate_credit_score",
                "arguments": json.dumps(
                    {
                        "ingresos_mensuales": "2500000",
                        "gastos_mensuales": "1000000",
                        "ocupacion": "trabajo",
                    }
                ),
            },
        }
    ]
    with caplog.at_level(logging.INFO):
        shim = _parse_openai_response(
            _openai_response_json(tool_calls=tool_calls), tools=tools
        )
    assert len(shim.candidates[0].content.parts) == 1
    fc = shim.candidates[0].content.parts[0].function_call
    assert fc.name == "calculate_credit_score"
    assert set(fc.args.keys()) == {"ingresos_mensuales", "gastos_mensuales"}
    assert "ocupacion" not in fc.args
    assert any(
        "[ARG-PRUNE] tool=calculate_credit_score field=ocupacion" in rec.message
        and "trabajo" not in rec.message
        for rec in caplog.records
    )


# ---------------------------------------------------------------------------
# T30 — ARG-PRUNE: preserva arg opcional dentro del léxico
# ---------------------------------------------------------------------------
def test_t30_preserves_grounded_optional_arg():
    """T30: Rama A Qwen preserva ocupacion='independiente' (dentro de léxico)."""
    tools = [
        {
            "function_declarations": [
                {
                    "name": "calculate_credit_score",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ingresos_mensuales": {"type": "string"},
                            "gastos_mensuales": {"type": "string"},
                            "ocupacion": {"type": "string"},
                        },
                        "required": ["ingresos_mensuales", "gastos_mensuales"],
                    },
                }
            ]
        }
    ]
    tool_calls = [
        {
            "id": "call_1",
            "type": "function",
            "function": {
                "name": "calculate_credit_score",
                "arguments": json.dumps(
                    {
                        "ingresos_mensuales": "5000000",
                        "gastos_mensuales": "2000000",
                        "ocupacion": "independiente",
                    }
                ),
            },
        }
    ]
    shim = _parse_openai_response(
        _openai_response_json(tool_calls=tool_calls), tools=tools
    )
    fc = shim.candidates[0].content.parts[0].function_call
    assert fc.args.get("ocupacion") == "independiente"


# ---------------------------------------------------------------------------
# T31 — ARG-PRUNE: no poda propiedades requeridas; Rama B intacta
# ---------------------------------------------------------------------------
def test_t31_required_arg_and_rama_b_untouched():
    """T31: requerida con valor fuera de léxico NO se poda; Rama B sin pruning."""
    tools = [
        {
            "function_declarations": [
                {
                    "name": "calculate_credit_score",
                    "parameters": {
                        "type": "object",
                        "properties": {"ocupacion": {"type": "string"}},
                        "required": ["ocupacion"],
                    },
                }
            ]
        }
    ]
    tool_calls = [
        {
            "id": "call_1",
            "type": "function",
            "function": {
                "name": "calculate_credit_score",
                "arguments": json.dumps({"ocupacion": "trabajo"}),
            },
        }
    ]
    shim_native = _parse_openai_response(
        _openai_response_json(tool_calls=tool_calls), tools=tools
    )
    fc_native = shim_native.candidates[0].content.parts[0].function_call
    assert fc_native.args.get("ocupacion") == "trabajo"

    # Rama B emulada: sin pruning
    shim_emulated = _parse_openai_response(
        _openai_response_json(
            content=json.dumps(
                {"tool_call": {"name": "calculate_credit_score", "args": {"ocupacion": "trabajo"}}}
            )
        ),
        emulated_toolcall=True,
        tools=tools,
    )
    fc_emulated = shim_emulated.candidates[0].content.parts[0].function_call
    assert fc_emulated.args.get("ocupacion") == "trabajo"
