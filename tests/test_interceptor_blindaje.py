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
        mock_part.text = "La Raider cuesta $6.000.000. ![Raider](https://img.url) Ficha Tecnica: Excelente moto."
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


@pytest.mark.asyncio
async def test_interceptor_bypass_synonyms(cerebro_mock, mock_prospect_data):
    """
    BOT-RESILIENCE-103:
    Escenario: El CRM tiene anclada la moto_interest "Scooter".
    El usuario realiza una consulta con el regionalismo "señoritera".
    Resultado Esperado: El bypass del Drift Interceptor debe permitir la búsqueda en el catálogo
    (no activa skip_catalog = True), a pesar de que difflib.SequenceMatcher de un ratio de 0.18 (< 0.30).
    """
    input_text = "precio señoritera"
    mock_prospect_data["moto_interest"] = "Scooter"
    
    # Mock de los alias de catálogo en config_service
    mock_aliases = {"Scooter": ["señoritera", "moped"]}
    
    from app.services.config_service import config_service
    with patch.object(config_service, 'get_catalog_aliases', return_value=mock_aliases), \
         patch.object(cerebro_mock, '_call_gemini_with_retry_async', new_callable=AsyncMock) as mocked_call:
        
        # Mock de respuesta Gemini (Inferencia inicial llamando a la herramienta search_catalog)
        mock_response_1 = MagicMock()
        mock_fc = MagicMock()
        mock_fc.name = "search_catalog"
        mock_fc.args = {"query": "señoritera"}
        mock_part_1 = MagicMock(function_call=mock_fc, text=None)
        mock_response_1.candidates = [MagicMock(content=MagicMock(parts=[mock_part_1]))]
        
        # Mock de respuesta Gemini (Segundo turno con los resultados del catálogo)
        mock_response_2 = MagicMock()
        mock_part_2 = MagicMock(function_call=None, text="La señoritera cuesta $7.000.000. ![Scooter](https://img.url) Ficha Tecnica: Excelente moto")
        mock_response_2.candidates = [MagicMock(content=MagicMock(parts=[mock_part_2]))]
        
        mocked_call.side_effect = [mock_response_1, mock_response_2]
        
        # Mock catalog service
        mock_catalog = MagicMock()
        mock_catalog.search_items.return_value = [
            {
                "name": "Scooter 125",
                "price": "$ 7.000.000",
                "category": "Scooter",
                "summary": "Excelente moto"
            }
        ]
        cerebro_mock._catalog_service = mock_catalog
        
        # Ejecutamos
        await cerebro_mock.pensar_respuesta(input_text, prospect_data=mock_prospect_data)
        
        # Verificación: Se debió llamar al catálogo y no lanzar la respuesta de bloqueo del interceptor
        assert mock_catalog.search_items.called, "FAILURE: catalog_service.search_items was not called (by-passed blocked)"
        assert mock_catalog.search_items.call_args[0][0] == "señoritera"
        print("\n✅ TEST BYPASS SINÓNIMOS REGIONALES EXITOSO: Interceptor omitió bloqueo para 'señoritera' ↔ 'Scooter'.")


@pytest.mark.asyncio
async def test_interceptor_bypass_partial_model(cerebro_mock, mock_prospect_data):
    """
    BOT-RESILIENCE-103:
    Escenario: El CRM tiene anclada la moto_interest "TVS Apache 160".
    El usuario busca "Apache" (coincidencia parcial de subcadena).
    Resultado Esperado: El bypass del Drift Interceptor debe permitir la búsqueda en el catálogo.
    """
    input_text = "precio Apache"
    mock_prospect_data["moto_interest"] = "TVS Apache 160"
    
    from app.services.config_service import config_service
    with patch.object(config_service, 'get_catalog_aliases', return_value={}), \
         patch.object(cerebro_mock, '_call_gemini_with_retry_async', new_callable=AsyncMock) as mocked_call:
        
        mock_response_1 = MagicMock()
        mock_fc = MagicMock()
        mock_fc.name = "search_catalog"
        mock_fc.args = {"query": "Apache"}
        mock_part_1 = MagicMock(function_call=mock_fc, text=None)
        mock_response_1.candidates = [MagicMock(content=MagicMock(parts=[mock_part_1]))]
        
        mock_response_2 = MagicMock()
        mock_part_2 = MagicMock(function_call=None, text="La Apache 160 cuesta $10.000.000. ![Apache](https://img.url) Ficha Tecnica: Excelente moto")
        mock_response_2.candidates = [MagicMock(content=MagicMock(parts=[mock_part_2]))]
        
        mocked_call.side_effect = [mock_response_1, mock_response_2]
        
        mock_catalog = MagicMock()
        mock_catalog.search_items.return_value = [
            {
                "name": "TVS Apache 160",
                "price": "$ 10.000.000",
                "category": "Deportiva",
                "summary": "Excelente moto"
            }
        ]
        cerebro_mock._catalog_service = mock_catalog
        
        await cerebro_mock.pensar_respuesta(input_text, prospect_data=mock_prospect_data)
        
        assert mock_catalog.search_items.called, "FAILURE: catalog_service.search_items was not called (by-passed blocked)"
        assert mock_catalog.search_items.call_args[0][0] == "Apache"
        print("\n✅ TEST BYPASS MODELOS PARCIALES EXITOSO: Interceptor omitió bloqueo para 'Apache' ↔ 'TVS Apache 160'.")

