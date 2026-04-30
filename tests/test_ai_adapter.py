import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from app.services.ai_brain import CerebroIA

@pytest.mark.asyncio
async def test_case_1_large_message_no_anchor(cerebro_mock, mock_prospect_data):
    """TEST CASE 1: Mensaje largo (>60 caracteres) no debe disparar el anclaje CRM."""
    large_text = "Me gustaría saber si tienen disponibilidad inmediata de la TVS APACHE 160 en color rojo y cuáles son los requisitos para un crédito en la ciudad de Bogotá."
    
    # Mocking _call_gemini_with_retry_async to inspect full_prompt
    with patch.object(cerebro_mock, '_call_gemini_with_retry_async', new_callable=AsyncMock) as mocked_call:
        # Mock successful response
        mocked_call.return_value.candidates = [] # This will trigger fallback or fail after turn, but we only care about the input
        
        try:
            await cerebro_mock.pensar_respuesta(large_text, prospect_data=mock_prospect_data)
        except: pass
        
        # Obtener el full_prompt enviado a Gemini
        args, kwargs = mocked_call.call_args
        full_prompt = args[1]
        
        # Aserto: No debe contener el [CRM ANCHOR]
        assert "[CRM ANCHOR:" not in full_prompt
        assert f"Usuario: {large_text}" in full_prompt

@pytest.mark.asyncio
async def test_case_2_short_message_with_anchor(cerebro_mock, mock_prospect_data):
    """TEST CASE 2: Mensaje corto debe inyectar el anclaje CRM."""
    short_text = "santa marta"
    
    with patch.object(cerebro_mock, '_call_gemini_with_retry_async', new_callable=AsyncMock) as mocked_call:
        mock_response = MagicMock()
        mock_part = MagicMock()
        mock_part.text = "Resultados de búsqueda"
        mock_part.function_call = None
        mock_response.candidates = [MagicMock(content=MagicMock(parts=[mock_part]))]
        mocked_call.return_value = mock_response
        
        try:
            await cerebro_mock.pensar_respuesta(short_text, prospect_data=mock_prospect_data)
        except Exception: pass
        
        args, kwargs = mocked_call.call_args
        full_prompt = args[1]
        
        # Aserto: Debe contener el anclaje inyectado internamente
        assert "[CRM ANCHOR: El usuario está interesado en la TVS APACHE 160. Mantén el contexto sobre este modelo a menos que el usuario pida conocer otra motocicleta.]" in full_prompt
        assert f"Usuario: {short_text}" in full_prompt

@pytest.mark.asyncio
async def test_case_3_raw_text_for_interceptor(cerebro_mock, mock_prospect_data):
    """TEST CASE 3: Validar que el interceptor use el texto crudo (sin anchor)."""
    short_text = "santa marta"
    
    with patch.object(cerebro_mock, '_call_gemini_with_retry_async', new_callable=AsyncMock) as mocked_call:
        # Mock a candidate that DOES NOT call tools
        from google.genai import types
        mock_response = MagicMock()
        mock_response.candidates = [MagicMock(content=MagicMock(parts=[MagicMock(function_call=None)]))]
        mocked_call.return_value = mock_response
        
        await cerebro_mock.pensar_respuesta(short_text, prospect_data=mock_prospect_data)
        
        # Si el test llega aquí sin que mock_call se haya llamado una segunda vez 
        # (Forced turn validation), significa que el interceptor NO detectó la moto.
        # En 'santa marta' no hay palabras clave de motos.
        assert mocked_call.call_count == 1 # 1 turn only
