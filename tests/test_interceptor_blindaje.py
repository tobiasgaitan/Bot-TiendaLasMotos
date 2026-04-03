import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.services.ai_brain import CerebroIA

@pytest.mark.asyncio
async def test_interceptor_ref_004_fix_verification(cerebro_mock, mock_prospect_data):
    """
    VERIFICACIÓN REF-004: 
    Escenario: Usuario dice "santa marta" (sin marcas de moto), pero el CRM tiene 
    anclada la "TVS APACHE 160".
    Resultado Esperado: El interceptor NO debe forzar un turno de validación.
    """
    input_text = "santa marta"
    
    # Mock de respuesta Gemini (Candidato sin llamadas a herramientas)
    with patch.object(cerebro_mock, '_call_gemini_with_retry_async', new_callable=AsyncMock) as mocked_call:
        mock_response = MagicMock()
        # candidate part without function call
        mock_part = MagicMock()
        mock_part.function_call = None
        mock_response.candidates = [MagicMock(content=MagicMock(parts=[mock_part]))]
        mocked_call.return_value = mock_response

        # Ejecución
        await cerebro_mock.pensar_respuesta(input_text, prospect_data=mock_prospect_data)

        # Verificación: El conteo de llamadas debe ser exactamente 1.
        # Si fuera 2, el interceptor habría forzado un turno de validación.
        assert mocked_call.call_count == 1, "FAILURE: Interceptor forced a tool turn incorrectly for 'santa marta'."
        print("\n✅ VALIDACIÓN REF-004 EXITOSA: Interceptor blindado contra contexto CRM.")

@pytest.mark.asyncio
async def test_interceptor_true_positive(cerebro_mock, mock_prospect_data):
    """
    VALIDACIÓN DE INTEGRIDAD:
    Escenario: Usuario dice "precio raider" (explícitamente una moto).
    Resultado Esperado: El interceptor DEBE seguir funcionando y forzar turno si no hay herramienta.
    """
    input_text = "precio raider" # 'raider' está en keywords
    
    with patch.object(cerebro_mock, '_call_gemini_with_retry_async', new_callable=AsyncMock) as mocked_call:
        # Mock de respuesta Gemini (Sin herramientas)
        mock_response = MagicMock()
        mock_part = MagicMock()
        mock_part.function_call = None
        mock_response.candidates = [MagicMock(content=MagicMock(parts=[mock_part]))]
        mocked_call.return_value = mock_response

        # Intentamos ejecutar (fallará al intentar el segundo turno si no mockeamos bien el retorno, pero call_count subirá)
        try:
            await cerebro_mock.pensar_respuesta(input_text, prospect_data=mock_prospect_data)
        except Exception:
            pass

        # Verificación: El conteo de llamadas debe ser 2 (Inferencia + Forced Turn)
        assert mocked_call.call_count == 2, "FAILURE: Interceptor missed a real motorcycle keyword."
        print("\n✅ TEST DE INTEGRIDAD EXITOSO: Interceptor sigue activo para intenciones reales.")
