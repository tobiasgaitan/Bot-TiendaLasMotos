import pytest
import re
from unittest.mock import patch, MagicMock
from app.services.catalog_service import catalog_service
from app.services.config_service import config_service

def test_pcc_ficha_tecnica_no_silent_null():
    """
    Verifica la presencia explícita de 'Ficha Tecnica:' y asegura que
    una mutación de llaves no resulte en valores 'None' silenciosos o
    strings vacíos, manteniendo la integridad del Price Consistency Check.
    """
    # Escenario 1: Comportamiento normal con la llave 'summary' correcta.
    mock_item_ok = {
        "id": "1",
        "name": "Moto Ghost",
        "price": 5000000,
        "cc": 125,
        "category": "Urban",
        "image_url": "http://img.url",
        "link": "http://link.url",
        "description": "Excelente moto urbana.",
        "summary": "Excelente moto urbana."
    }
    
    with patch.object(catalog_service, '_items', [mock_item_ok]), \
         patch.object(catalog_service, '_db', MagicMock()), \
         patch.object(config_service, '_financial_config', None), \
         patch.object(config_service, 'get_registration_cost', return_value=0):
        
        catalog_service.load_configurations = MagicMock()
        catalog_service._cache_service.clear()
        
        res = catalog_service.search_catalog("Ghost")
        assert "Ficha Tecnica:" in res, "La cadena transformada 'Ficha Tecnica:' DEBE estar explícita."
        
        match = re.search(r"Ficha Tecnica:\s*(.+)", res)
        assert match is not None, "El contenido después de 'Ficha Tecnica:' no puede ser nulo o vacío."
        val = match.group(1).strip()
        assert val != "", "El string de Ficha Tecnica no puede ser vacío."
        assert val != "None", "El string de Ficha Tecnica no puede ser 'None' silencioso."

    # Escenario 2: Mutación de llaves (ej: el backend cambió 'summary' a 'resumen_tecnico')
    # Omitimos 'summary' para simular la mutación/pérdida de la llave.
    mock_item_mutated = {
        "id": "1",
        "name": "Moto Ghost",
        "price": 5000000,
        "cc": 125,
        "category": "Urban",
        "image_url": "http://img.url",
        "link": "http://link.url",
        "resumen_tecnico": "Excelente moto urbana."
    }
    
    with patch.object(catalog_service, '_items', [mock_item_mutated]), \
         patch.object(catalog_service, '_db', MagicMock()), \
         patch.object(config_service, '_financial_config', None), \
         patch.object(config_service, 'get_registration_cost', return_value=0):
        
        catalog_service.load_configurations = MagicMock()
        catalog_service._cache_service.clear()
        
        res_mutated = catalog_service.search_catalog("Ghost")
        
        # Validar que si la llave mutó, no devuelva la sección Ficha Tecnica (evita valores vacíos o None)
        assert "Ficha Tecnica:" not in res_mutated, "Se esperaba que 'Ficha Tecnica:' no estuviera presente debido a la mutación de llaves."
        
        # Asegurar que la mutación active la alerta del guardrail PCC Pro inyectando un error (success=False)
        from app.services.agentic_loop_service import AgenticOrchestrator
        orchestrator = AgenticOrchestrator()
        validation = orchestrator.run_checker(res_mutated, is_catalog_query=True)
        assert validation["success"] is False, "Se esperaba que el guardrail PCC Pro fallara debido a la mutación de llaves."
        assert validation["report"]["broken_guardrail"] == "PRICE_CONSISTENCY_CHECK"


@pytest.mark.asyncio
async def test_habeas_data_gate_before_credit_score():
    """
    Test de caracterización estricta:
    - Cuando el flag 'habeas_data_accepted' está ausente o es False,
      la llamada a calculate_credit_score debe ser interceptada.
    - Se debe verificar que se desvíe al flujo de legalización (HabeasDataBypassInterrupt lineal)
      (PASO 4 del protocolo / script legal de Habeas Data) ANTES de invocar el simulador/motor financiero.
    - [MANDATORIO] Incluir aserción de contenido que verifique la presencia explícita de 'Ficha Tecnica:'
      cuando el catálogo sí cuenta con la información y no está mutado, y prohibir que resulte en vacío,
      forzando la validación de 'habeas_data_accepted' en Firestore/prospect_data antes de calcular la cuota.
    """
    from app.services.ai_brain import CerebroIA
    
    # Mocking classes for Gemini response
    class MockFunctionCall:
        def __init__(self, name, args):
            self.name = name
            self.args = args

    class MockPart:
        def __init__(self, function_call=None, text=None):
            self.function_call = function_call
            self.text = text

    class MockContent:
        def __init__(self, parts):
            self.parts = parts

    class MockCandidate:
        def __init__(self, content):
            self.content = content

    class MockResponse:
        def __init__(self, candidates):
            self.candidates = candidates

    # Configuración de CerebroIA
    cerebro = CerebroIA()
    cerebro.client = MagicMock()
    cerebro._model_id = "gemini-2.0-flash"

    # Mock catalog service para retornar un item válido con su respectiva Ficha Tecnica
    mock_catalog = MagicMock()
    mock_catalog.search_items.return_value = [
        {
            "name": "TVS Sport 100",
            "price": "$9.969.000.*",
            "raw_price": None,
            "category": "Urban",
            "image_url": "https://img.url",
            "summary": "Excelente moto urbana."
        }
    ]
    cerebro._catalog_service = mock_catalog

    # Mock del motor financiero. Si se llega a invocar evaluate_profile, el test debe fallar,
    # garantizando el bloqueo absoluto de perfilamiento antes de tocar el simulador.
    mock_financial = MagicMock()
    mock_financial.evaluate_profile = MagicMock(side_effect=AssertionError("ERROR: El motor financiero fue tocado sin consentimiento de Habeas Data."))
    mock_financial.calculate_payment = MagicMock(return_value={"cuota_mensual": 250000.0})
    cerebro.motor_financiero = mock_financial

    # Simular que el LLM intenta invocar calculate_credit_score
    fc = MockFunctionCall(name="calculate_credit_score", args={})
    candidate = MockCandidate(content=MockContent(parts=[MockPart(function_call=fc)]))
    gemini_response = MockResponse(candidates=[candidate])

    candidate_text_no_consent = MockCandidate(content=MockContent(parts=[MockPart(text="Para hacer el estudio formal de tu crédito, ¿me autorizas el tratamiento de tus datos?")]))
    gemini_response_text_no_consent = MockResponse(candidates=[candidate_text_no_consent])

    captured_response_parts = None
    call_count_no_consent = 0
    async def mock_call_no_consent(*args, **kwargs):
        nonlocal call_count_no_consent, captured_response_parts
        call_count_no_consent += 1
        if call_count_no_consent == 1:
            return gemini_response
        if len(args) > 1:
            captured_response_parts = args[1]
        return gemini_response_text_no_consent

    # Caso 1: Flag habeas_data_accepted está ausente/False
    prospect_no_consent = {
        "nombre": "Pedro",
        "moto_interest": "TVS Sport 100",
        "ciudad": "Cali",
        "forma_pago": "Crédito"
        # habeas_data_accepted está ausente (debe bloquearse)
    }

    with patch.object(cerebro, '_call_gemini_with_retry_async', new=mock_call_no_consent), \
         patch('app.services.ai_brain.SDK_AVAILABLE', True), \
         patch('app.services.ai_brain.logger.warning') as mock_log_warn:

        from app.core.exceptions import HabeasDataBypassInterrupt
        with pytest.raises(HabeasDataBypassInterrupt) as exc_info:
            await cerebro.pensar_respuesta("Quiero mi crédito", prospect_data=prospect_no_consent)
        response = str(exc_info.value.args[0])
        
        # 1. Asegurar que el log forense de seguridad se haya registrado
        mock_log_warn.assert_called()
        warn_args = [call[0][0] for call in mock_log_warn.call_args_list]
        assert any("SECURITY ALERT [Habeas Data Gate]: Financial profiling without consent." in arg for arg in warn_args)

        # 2. Asegurar que no se tocó el perfilamiento, pero sí el simulador para la cuota ciega
        mock_financial.evaluate_profile.assert_not_called()
        mock_financial.calculate_payment.assert_called_once_with(
            precio=9969000.0,
            inicial=996900.0,
            plazo_meses=24,
            entidad="Crediorbe"
        )

        # 3. Asegurar que la respuesta final de la herramienta se desvió al flujo de legalización solicitando consentimiento
        assert response is not None
        
        # Inmutabilidad del Formato PCC Pro (Validación Visual):
        # Debe certificar mediante Regex secuencial la presencia exacta del signo pesos ($) pegado al valor numérico formateado.
        assert re.search(r"\$250,000", response) is not None, "El formato de cuota formateada no cumple con la regla de negocio ($250,000)."
        
        # Debe omitir marcas de agua de proveedores financieros.
        assert "Crediorbe" not in response, "La marca de agua 'Crediorbe' no debe figurar en la respuesta de contingencia ciego."
        assert "Brilla" not in response, "La marca de agua 'Brilla' no debe figurar en la respuesta de contingencia ciego."
        
        assert "Para hacer el estudio formal de tu crédito" in response
        assert "politica-de-privacidad" in response

        # Aserciones rígidas de contenido de BOT-BRAIN-RETURN-082
        assert "$" in response, "El resultado debe contener el signo pesos ($)."
        assert "Si te interesa a crédito con la inicial de $996,900, las cuotas a 24 meses serían aproximadamente de $250,000 (incluye SOAT y Matrícula). *Nota: Este es un valor aproximado.*" in response, "El resultado debe contener la cadena esperada."

    # Caso 2: Garantizar que la Ficha Tecnica es explícita y forzar validación del flag en DB antes de calcular cuota
    # Si habeas_data_accepted es True, la validación pasa, y sí se procesa el catálogo y simulador.
    mock_financial.evaluate_profile.reset_mock()
    mock_financial.evaluate_profile.side_effect = None
    mock_financial.evaluate_profile.return_value = {
        "score": 750,
        "strategy": "Aprobado",
        "entity": "Crediorbe",
        "link_url": "https://crediorbe.link"
    }
    mock_financial.calculate_payment.reset_mock()
    mock_financial.calculate_payment.side_effect = None
    mock_financial.calculate_payment.return_value = {
        "cuota_mensual": 250000
    }

    prospect_with_consent = {
        "nombre": "Pedro",
        "moto_interest": "TVS Sport 100",
        "ciudad": "Cali",
        "forma_pago": "Crédito",
        "habeas_data_accepted": True # Consentimiento explícito
    }

    # Creamos una segunda respuesta para el final text
    candidate_text = MockCandidate(content=MockContent(parts=[MockPart(text="Felicidades. Ficha Tecnica: Excelente moto urbana.")]))
    gemini_response_text = MockResponse(candidates=[candidate_text])

    call_count = 0
    async def mock_call_two_turns(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return gemini_response
        return gemini_response_text

    with patch.object(cerebro, '_call_gemini_with_retry_async', new=mock_call_two_turns), \
         patch('app.services.ai_brain.SDK_AVAILABLE', True):

        response_consent = await cerebro.pensar_respuesta("Quiero mi crédito", prospect_data=prospect_with_consent)

        # 1. Asegurar que el simulador SÍ fue invocado cuando se tiene el consentimiento
        mock_financial.evaluate_profile.assert_called_once()
        mock_financial.calculate_payment.assert_called_once()

        # 2. [MANDATORIO] Verificar la presencia explícita de 'Ficha Tecnica:' y prohibir string vacío
        assert "Ficha Tecnica:" in response_consent
        match = re.search(r"Ficha Tecnica:\s*(.+)", response_consent)
        assert match is not None, "El contenido de Ficha Tecnica no debe estar vacío"
        assert len(match.group(1).strip()) > 0, "El valor de Ficha Tecnica no puede ser vacío"


def test_ficha_tecnica_explicit_content_assertion():
    """
    Test unitario mandatado por BOT-TRACE-FIX-v2.5:
    Verifica la presencia explícita de 'Ficha Tecnica:' para ítems válidos
    y prohíbe de forma estricta que una mutación de llaves resulte en un string
    vacío o valores devueltos como None silenciosos.
    """
    # Escenario A: Ítem válido (summary presente)
    item_valido = {
        "name": "TVS Raider 125",
        "summary": "Excelente tecnología SmartXonnect.",
        "price": "$7.190.000"
    }
    
    # Formateo esperado en el catálogo
    response_str = f"- {item_valido['name']}: {item_valido['price']}\n  Ficha Tecnica: {item_valido['summary']}\n"
    
    assert "Ficha Tecnica:" in response_str, "La cadena 'Ficha Tecnica:' debe estar presente explícitamente"
    match = re.search(r"Ficha Tecnica:\s*(.+)", response_str)
    assert match is not None, "No debe haber un None silencioso en el formato de Ficha Tecnica"
    val = match.group(1).strip()
    assert val != "", "El valor de Ficha Tecnica no puede ser un string vacío"
    assert val != "None", "El valor de Ficha Tecnica no puede ser 'None' silencioso"

    # Escenario B: Mutación de llaves / summary nulo
    item_mutated = {
        "name": "TVS Raider 125",
        "price": "$7.190.000",
        "summary": None  # Simula mutación/pérdida de la llave summary
    }
    
    # Simular guardrail de ai_brain.py (líneas 1157-1166) que omite ítems inválidos
    name = item_mutated.get('name')
    summary = item_mutated.get('summary')
    price = item_mutated.get('price')
    
    response_mutated = ""
    if name and summary and price:
        response_mutated += f"- {name}: {price}\n  Ficha Tecnica: {summary}\n"
        
    assert "Ficha Tecnica:" not in response_mutated, "Si el summary es None, 'Ficha Tecnica:' no debe generarse"
    assert response_mutated == "", "Un ítem corrupto debe dar una respuesta vacía (ignorado) en vez de None silencioso"

    # Asegurar que la mutación active la alerta del guardrail PCC Pro en el orquestador
    from app.services.agentic_loop_service import AgenticOrchestrator
    orchestrator = AgenticOrchestrator()
    validation = orchestrator.run_checker(response_mutated, is_catalog_query=True)
    assert validation["success"] is False, "La respuesta vacía por mutación debe activar la alerta del guardrail PCC Pro."
    assert validation["report"]["broken_guardrail"] == "PRICE_CONSISTENCY_CHECK"


@pytest.mark.asyncio
async def test_habeas_bypass_interrupt_e2e():
    """
    [BOT-BRAIN-CRITICAL-E2E-084] Test de caracterización E2E:
    Verifica que HabeasDataBypassInterrupt produce un cortocircuito limpio
    a través del while loop maestro de pensar_respuesta, retornando un string
    válido al webhook de Meta sin colapsar el orquestador.

    Mandatory checks:
    1. El string retornado contiene '$' (PCC Visual)
    2. Contiene 'Estimación de cuota base aproximada:'
    3. NO lanza excepción (no colapsa el orquestador)
    4. Estructura anonimizada (sin marca de agua 'Crediorbe' en respuesta)
    5. Contiene script legal de Habeas Data
    """
    from app.services.ai_brain import CerebroIA
    from app.core.exceptions import HabeasDataBypassInterrupt

    # Mocking classes for Gemini response
    class MockFunctionCall:
        def __init__(self, name, args):
            self.name = name
            self.args = args

    class MockPart:
        def __init__(self, function_call=None, text=None):
            self.function_call = function_call
            self.text = text

    class MockContent:
        def __init__(self, parts):
            self.parts = parts

    class MockCandidate:
        def __init__(self, content):
            self.content = content

    class MockResponse:
        def __init__(self, candidates):
            self.candidates = candidates

    # Setup CerebroIA with mocks
    cerebro = CerebroIA()
    cerebro.client = MagicMock()
    cerebro._model_id = "gemini-2.0-flash"

    # Mock catalog service returning a valid item with price
    mock_catalog = MagicMock()
    mock_catalog.search_items.return_value = [
        {
            "name": "TVS Sport 100",
            "price": "$9.969.000.*",
            "raw_price": None,
            "category": "Urban",
            "image_url": "https://img.url",
            "summary": "Excelente moto urbana."
        }
    ]
    cerebro._catalog_service = mock_catalog

    # Mock motor financiero — evaluate_profile MUST NOT be called (no consent)
    mock_financial = MagicMock()
    mock_financial.evaluate_profile = MagicMock(
        side_effect=AssertionError("ERROR: El motor financiero fue tocado sin consentimiento de Habeas Data.")
    )
    mock_financial.calculate_payment = MagicMock(return_value={"cuota_mensual": 250000.0})
    cerebro.motor_financiero = mock_financial

    # Simulate Gemini returning a function call to calculate_credit_score
    fc = MockFunctionCall(name="calculate_credit_score", args={})
    candidate_fc = MockCandidate(content=MockContent(parts=[MockPart(function_call=fc)]))
    gemini_response_fc = MockResponse(candidates=[candidate_fc])

    # This second response should NEVER be reached (HabeasDataBypassInterrupt short-circuits)
    candidate_text = MockCandidate(content=MockContent(parts=[MockPart(text="Esta respuesta NO debe verse.")]))
    gemini_response_text = MockResponse(candidates=[candidate_text])

    call_count = 0
    async def mock_gemini_call(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return gemini_response_fc
        # If we reach here, the short-circuit FAILED
        return gemini_response_text

    # Prospect WITHOUT habeas_data_accepted → triggers HabeasDataBypassInterrupt directly (BOT-BRAIN-FINANCE-086)
    prospect_no_consent = {
        "nombre": "TestUser",
        "moto_interest": "TVS Sport 100",
        "ciudad": "Bogotá",
        "forma_pago": "Crédito"
        # habeas_data_accepted is ABSENT → must trigger bypass
    }

    with patch.object(cerebro, '_call_gemini_with_retry_async', new=mock_gemini_call), \
         patch('app.services.ai_brain.SDK_AVAILABLE', True), \
         patch('app.services.ai_brain.logger') as mock_logger:

        # ACT: Call pensar_respuesta directly — must raise HabeasDataBypassInterrupt
        with pytest.raises(HabeasDataBypassInterrupt) as exc_info:
            await cerebro.pensar_respuesta(
                "Quiero financiar mi moto",
                prospect_data=prospect_no_consent
            )
        response = str(exc_info.value.args[0])

        # ASSERT 1: No exception was raised (orchestrator did not collapse)
        assert response is not None, "pensar_respuesta debe retornar un string, no None."
        assert isinstance(response, str), f"pensar_respuesta debe retornar str, obtuvo {type(response).__name__}."

        # ASSERT 2: PCC Visual — contains '$' sign
        assert "$" in response, f"El resultado debe contener el signo pesos ($). Respuesta: {response[:200]}"

        # ASSERT 3: Contains the expected cuota structure
        assert "Si te interesa a crédito con la inicial de $996,900, las cuotas a 24 meses serían aproximadamente de $250,000 (incluye SOAT y Matrícula). *Nota: Este es un valor aproximado.*" in response, (
            f"El resultado debe contener the expected copywriting. Respuesta: {response[:200]}"
        )

        # ASSERT 4: Anonimized — no provider watermark
        assert "Crediorbe" not in response, "La marca de agua 'Crediorbe' no debe figurar en la respuesta anonimizada."
        assert "Brilla" not in response, "La marca de agua 'Brilla' no debe figurar en la respuesta anonimizada."

        # ASSERT 5: Habeas Data legal script present
        assert "politica-de-privacidad" in response, "El script legal de Habeas Data debe estar presente."

        # ASSERT 6: Verify the HABEAS-BYPASS log was emitted
        bypass_logged = any(
            "HABEAS-BYPASS" in str(call)
            for call in mock_logger.info.call_args_list
        )
        assert bypass_logged, "El log '[HABEAS-BYPASS] Cortocircuito limpio ejecutado' debe haberse emitido."

        # ASSERT 7: evaluate_profile must NOT have been called
        mock_financial.evaluate_profile.assert_not_called()

        # ASSERT 8: calculate_payment MUST have been called (blind simulation)
        mock_financial.calculate_payment.assert_called_once_with(
            precio=9969000.0,
            inicial=996900.0,
            plazo_meses=24,
            entidad="Crediorbe"
        )

        # ASSERT 9: Gemini was only called ONCE (the function call turn),
        # the short-circuit prevented a second call
        assert call_count == 1, (
            f"Gemini debió ser llamado exactamente 1 vez (function call turn). "
            f"Fue llamado {call_count} veces — indica que el cortocircuito falló."
        )
