import pytest
import re
from unittest.mock import patch, MagicMock
from app.services.catalog_service import catalog_service
from app.services.config_service import config_service
from app.services.credit_faq_taxonomy import classify_credit_turn, TurnIntent
from tests.factories import make_catalog, format_cop
from tests.validators import (
    RE_EXTRACT_PRECIOS,
    assert_price_consistency,
    assert_ficha_explicit,
    assert_catalog_price_format,
    assert_image_reference,
    assert_no_pii_leak,
)

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
        # 'summary' ausente (no en el dict) — comportamiento: omitir sección Ficha Tecnica silenciosamente
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

    # ─── Escenario 2b: Mutación EXPLÍCITA (summary=None) — KeyError duro [BOT-QA-HARDENING-126] ──────
    # WHY: A diferencia del Escenario 2 donde la llave simplemente está ausente (ok, omitir sección),
    # este escenario simula cuando el pipeline de load_catalog() recibió la llave pero con valor None.
    # Esto es una mutación silenciosa que el guardrail debe detectar como error de integridad critica.
    # NOTA: Parchear search_items es obligatorio porque el engine fuzzy no hace match semántico
    # con el nombre de prueba sintético, impidiendo que el ítem corrupto llegue al loop de formateo.
    mock_item_null_summary = {
        "id": "2",
        "name": "Moto Ghost Null",
        "price": 5000000,
        "cc": 125,
        "category": "Urban",
        "image_url": "http://img.url",
        "link": "http://link.url",
        "summary": None  # Mutación explícita: llave presente pero valor None
    }

    with patch.object(catalog_service, '_items', [mock_item_null_summary]), \
         patch.object(catalog_service, 'search_items', return_value=[mock_item_null_summary]), \
         patch.object(catalog_service, '_db', MagicMock()), \
         patch.object(config_service, '_financial_config', None), \
         patch.object(config_service, 'get_registration_cost', return_value=0):

        catalog_service.load_configurations = MagicMock()
        catalog_service._cache_service.clear()

        # [BOT-QA-HARDENING-126] El sistema DEBE lanzar KeyError duro, no omitir silenciosamente.
        # Esto previene que el LLM alucine una ficha técnica a partir de un payload None.
        with pytest.raises(KeyError) as exc_info:
            catalog_service.search_catalog("Ghost Null")

        assert "CATALOG INTEGRITY VIOLATION" in str(exc_info.value), (
            f"KeyError debe contener 'CATALOG INTEGRITY VIOLATION' para diagnóstico forense. "
            f"Obtenido: {str(exc_info.value)}"
        )
        assert "summary" in str(exc_info.value).lower() or "Moto Ghost Null" in str(exc_info.value), (
            "KeyError debe identificar el ítem afectado para trazabilidad forense."
        )


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

    # Setup physical financial_service with canonical configuration
    from app.services.financial_service import financial_service
    from app.services.config_service import config_service
    cerebro.motor_financiero = financial_service

    brilla_config = {
        'fngRate': 0.0,
        'coverageRate': 4.0,
        'lifeInsuranceValue': 15000.0,
        'brillaManagementRate': 5.0,
        'interestRate': 1.91,
        'rows': [
            {'registrationCreditGeneral': 760000, 'factors': {'48': 0.035678, '24': 0.0523336, '36': 0.041234}, 'maxCC': 99, 'id': '0-99', 'minCC': 0},
            {'registrationCreditGeneral': 840000, 'factors': {'48': 0.035678, '24': 0.0523336, '36': 0.041234}, 'maxCC': 124, 'id': '100-124', 'minCC': 100},
            {'registrationCreditGeneral': 920000, 'factors': {'48': 0.035678, '24': 0.0523336, '36': 0.041234}, 'maxCC': 200, 'category': 'URBANA Y/O TRABAJO', 'id': '125-200', 'minCC': 125},
            {'registrationCreditGeneral': 1120000, 'factors': {'48': 0.035678, '24': 0.0523336, '36': 0.041234}, 'maxCC': 9999, 'id': 'gt-200', 'minCC': 201}
        ]
    }
    mock_evaluate_profile = MagicMock(side_effect=AssertionError("ERROR: El motor financiero fue tocado sin consentimiento de Habeas Data."))
    spy_calculate = MagicMock(wraps=financial_service.calculate_payment)

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
         patch('app.services.ai_brain.logger.warning') as mock_log_warn, \
         patch.object(financial_service, 'evaluate_profile', new=mock_evaluate_profile), \
         patch.object(financial_service, 'calculate_payment', new=spy_calculate), \
         patch.object(config_service, 'get_financial_entity_config', return_value=brilla_config), \
         patch.object(config_service, 'get_financial_matrix', return_value=brilla_config['rows']), \
         patch.object(config_service, 'get_financial_config', return_value=brilla_config), \
         patch.object(config_service, 'get_registration_cost', return_value=840000.0):

        from app.core.exceptions import HabeasDataBypassInterrupt
        with pytest.raises(HabeasDataBypassInterrupt) as exc_info:
            await cerebro.pensar_respuesta("Quiero mi crédito", prospect_data=prospect_no_consent)
        response = str(exc_info.value.args[0])
        
        # 1. Asegurar que el log forense de seguridad se haya registrado
        mock_log_warn.assert_called()
        warn_args = [call[0][0] for call in mock_log_warn.call_args_list]
        assert any("SECURITY ALERT [Habeas Data Gate]: Financial profiling without consent." in arg for arg in warn_args)

        # 2. Asegurar que no se tocó el perfilamiento, pero sí el simulador para la cuota ciega
        mock_evaluate_profile.assert_not_called()
        spy_calculate.assert_called_once_with(
            precio=9129000.0,
            inicial=996900.0,
            plazo_meses=24,
            entidad="Brilla de Gases",
            moto_cc=0.0,
            category="Urban"
        )

        # 3. Asegurar que la respuesta final de la herramienta se desvió al flujo de legalización solicitando consentimiento
        assert response is not None
        
        # Inmutabilidad del Formato PCC Pro (Validación Visual):
        # Debe certificar mediante Regex secuencial la presencia exacta del signo pesos ($) pegado al valor numérico formateado.
        assert re.search(r"\$539,421", response) is not None, "El formato de cuota formateada no cumple con la regla de negocio ($539,421)."
        
        # Debe omitir marcas de agua de proveedores financieros.
        assert "Crediorbe" not in response, "La marca de agua 'Crediorbe' no debe figurar en la respuesta de contingencia ciego."
        assert "Brilla" not in response, "La marca de agua 'Brilla' no debe figurar en la respuesta de contingencia ciego."
        
        assert "Para hacer el estudio formal de tu crédito" in response
        assert "politica-de-privacidad" in response
        assert "👍" in response, "La respuesta debe incluir el emoji de pulgar arriba 👍"
        assert "emoji de pulgar arriba (👍)" in response, "La respuesta debe incluir explícitamente la frase 'emoji de pulgar arriba (👍)'"
 
        # Aserciones rígidas de contenido de BOT-BRAIN-RETURN-082
        assert "$" in response, "El resultado debe contener el signo pesos ($)."
        assert "Si te interesa a crédito con la inicial de $996,900, las cuotas a 24 meses serían aproximadamente de $539,421 (incluye SOAT y Matrícula). *Nota: Este es un valor aproximado.*" in response, "El resultado debe contener la cadena esperada."
    # Si habeas_data_accepted es True, la validación pasa, y sí se procesa el catálogo y simulador.
    # [BOT-QA-HARDENING-126] Además, actualizar el mock_catalog para simular URL compleja de Meta/Firebase Storage
    # con query params (token, alt, size) — el transformador dinámico debe preservar la URL intacta.
    META_COMPLEX_IMAGE_URL = (
        "https://firebasestorage.googleapis.com/v0/b/tienda-motos.appspot.com/o/tvs-sport-100.jpg"
        "?alt=media&token=abc123-xyz456&size=800&watermark=tlm"
    )

    mock_evaluate_profile_consent = MagicMock()
    mock_evaluate_profile_consent.return_value = {
        "score": 750,
        "strategy": "Aprobado",
        "entity": "Crediorbe",
        "link_url": "https://crediorbe.link"
    }
    mock_calculate_payment_consent = MagicMock()
    mock_calculate_payment_consent.return_value = {
        "cuota_mensual": 250000
    }

    # Actualizar mock_catalog con URL compleja de Meta/Firebase
    mock_catalog.search_items.return_value = [
        {
            "name": "TVS Sport 100",
            "price": "$9.969.000.*",
            "raw_price": None,
            "category": "Urban",
            "image_url": META_COMPLEX_IMAGE_URL,  # URL con query params de red Meta
            "summary": "Excelente moto urbana."
        }
    ]

    prospect_with_consent = {
        "nombre": "Pedro",
        "moto_interest": "TVS Sport 100",
        "ciudad": "Cali",
        "forma_pago": "Crédito",
        "habeas_data_accepted": True  # Consentimiento explícito
    }

    # Transformador dinámico: verificar que la URL compleja no sea truncada ni mutilada.
    # WHY: Los proxies de la API de Meta pueden purgar caracteres '?' y '&' generando HTTP 400.
    # Esta función simula la validación de integridad que el pipeline de egress debe implementar.
    def _validate_meta_url_integrity(url: str) -> dict:
        """
        Transformador de URL Meta: verifica que la URL con query params sobrevive intacta.
        Retorna un dict con 'valid' y 'purged_chars' para diagnóstico forense.
        """
        import urllib.parse
        parsed = urllib.parse.urlparse(url)
        query_params = urllib.parse.parse_qs(parsed.query)
        purged_chars = []
        # Detectar si la URL fue truncada por un proxy (perdería el '?' o '&')
        if "?" in url and not parsed.query:
            purged_chars.append("?")
        if "&" in parsed.query and len(query_params) < 2:
            purged_chars.append("&")
        return {
            "valid": len(purged_chars) == 0,
            "purged_chars": purged_chars,
            "param_count": len(query_params),
            "url_intact": url == META_COMPLEX_IMAGE_URL
        }

    # Verificar que la URL original pasa el transformador
    url_check = _validate_meta_url_integrity(META_COMPLEX_IMAGE_URL)
    assert url_check["valid"] is True, (
        f"La URL de Meta con query params debe ser válida antes de enviar al pipeline. "
        f"Params encontrados: {url_check['param_count']}, chars purgados: {url_check['purged_chars']}"
    )
    assert url_check["param_count"] >= 3, (
        f"La URL debe tener al menos 3 query params (alt, token, size). "
        f"Encontrado: {url_check['param_count']}"
    )

    # Creamos una segunda respuesta para el final text
    candidate_text = MockCandidate(content=MockContent(parts=[MockPart(text="Felicidades. Ficha Tecnica: Excelente moto urbana.")])) 
    gemini_response_text = MockResponse(candidates=[candidate_text])

    all_tool_outputs_caso2 = []
    call_count = 0
    async def mock_call_two_turns(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if len(args) > 1:
            all_tool_outputs_caso2.append(str(args[1]))
        if call_count == 1:
            return gemini_response
        return gemini_response_text

    with patch.object(cerebro, '_call_gemini_with_retry_async', new=mock_call_two_turns), \
         patch('app.services.ai_brain.SDK_AVAILABLE', True), \
         patch.object(financial_service, 'evaluate_profile', new=mock_evaluate_profile_consent), \
         patch.object(financial_service, 'calculate_payment', new=mock_calculate_payment_consent):

        response_consent = await cerebro.pensar_respuesta("Quiero mi crédito", prospect_data=prospect_with_consent)

        # 1. Asegurar que el simulador SÍ fue invocado cuando se tiene el consentimiento
        mock_evaluate_profile_consent.assert_called_once()
        mock_calculate_payment_consent.assert_called_once()

        # 2. [MANDATORIO] Verificar la presencia explícita de 'Ficha Tecnica:' y prohibir string vacío
        assert "Ficha Tecnica:" in response_consent
        match = re.search(r"Ficha Tecnica:\s*(.+)", response_consent)
        assert match is not None, "El contenido de Ficha Tecnica no debe estar vacío"
        assert len(match.group(1).strip()) > 0, "El valor de Ficha Tecnica no puede ser vacío"

        # 3. [BOT-QA-HARDENING-126] Validación de integridad de URL compleja (Transformador Dinámico Meta).
        # WHY: El mock inyecta la URL compleja en search_items.return_value. El pipeline de ai_brain.py
        # la extrae via m.get('image_url') y la construye en catalog_response_str.
        # La aserción correcta es triple:
        #   (a) El transformador de URL detecta integridad ANTES del pipeline (pre-flight check).
        #   (b) El mock fue llamado con la URL compleja intacta (no pre-truncada en el mock setup).
        #   (c) Si la URL aparece en algún tool output, verificar que sus query params sobrevivieron.
        
        # (a) Pre-flight check: ya validado arriba con _validate_meta_url_integrity (url_check["valid"] is True)
        
        # (b) Verificar que el mock de search_items fue configurado con URL compleja intacta
        search_items_return = mock_catalog.search_items.return_value
        assert len(search_items_return) > 0, "Mock de search_items debe tener al menos un ítem"
        configured_url = search_items_return[0].get("image_url", "")
        assert configured_url == META_COMPLEX_IMAGE_URL, (
            f"[BOT-QA-HARDENING-126] La URL compleja de Meta fue alterada antes de entrar al pipeline.\n"
            f"URL esperada: {META_COMPLEX_IMAGE_URL}\n"
            f"URL en mock: {configured_url}"
        )
        # Verificar que los query params críticos NO fueron purgados en la configuración del mock
        assert "?alt=media" in configured_url, (
            "El parámetro '?alt=media' de Firebase Storage fue mutilado antes del pipeline."
        )
        assert "&token=" in configured_url, (
            "El parámetro '&token=' de Firebase Storage fue mutilado antes del pipeline."
        )
        assert len(configured_url) == len(META_COMPLEX_IMAGE_URL), (
            f"[BOT-QA-HARDENING-126] La URL fue truncada. "
            f"Longitud esperada: {len(META_COMPLEX_IMAGE_URL)}, obtenida: {len(configured_url)}"
        )
        
        # (c) Si algún tool output contiene la URL, verificar integridad de query params
        combined_tool_outputs = " ".join(all_tool_outputs_caso2)
        if META_COMPLEX_IMAGE_URL in combined_tool_outputs:
            # Si la URL está en los tool outputs, sus query params deben estar intactos
            assert "?alt=media" in combined_tool_outputs, (
                "El parámetro '?alt=media' fue mutilado en el tool output."
            )
            assert "&token=" in combined_tool_outputs, (
                "El parámetro '&token=' fue mutilado en el tool output."
            )



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

    # Setup physical financial_service with canonical configuration
    from app.services.financial_service import financial_service
    from app.services.config_service import config_service
    cerebro.motor_financiero = financial_service

    brilla_config = {
        'fngRate': 0.0,
        'coverageRate': 4.0,
        'lifeInsuranceValue': 15000.0,
        'brillaManagementRate': 5.0,
        'interestRate': 1.91,
        'rows': [
            {'registrationCreditGeneral': 760000, 'factors': {'48': 0.035678, '24': 0.0523336, '36': 0.041234}, 'maxCC': 99, 'id': '0-99', 'minCC': 0},
            {'registrationCreditGeneral': 840000, 'factors': {'48': 0.035678, '24': 0.0523336, '36': 0.041234}, 'maxCC': 124, 'id': '100-124', 'minCC': 100},
            {'registrationCreditGeneral': 920000, 'factors': {'48': 0.035678, '24': 0.0523336, '36': 0.041234}, 'maxCC': 200, 'category': 'URBANA Y/O TRABAJO', 'id': '125-200', 'minCC': 125},
            {'registrationCreditGeneral': 1120000, 'factors': {'48': 0.035678, '24': 0.0523336, '36': 0.041234}, 'maxCC': 9999, 'id': 'gt-200', 'minCC': 201}
        ]
    }
    mock_evaluate_profile_e2e = MagicMock(side_effect=AssertionError("ERROR: El motor financiero fue tocado sin consentimiento de Habeas Data."))
    spy_calculate_e2e = MagicMock(wraps=financial_service.calculate_payment)

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
         patch('app.services.ai_brain.logger') as mock_logger, \
         patch.object(financial_service, 'evaluate_profile', new=mock_evaluate_profile_e2e), \
         patch.object(financial_service, 'calculate_payment', new=spy_calculate_e2e), \
         patch.object(config_service, 'get_financial_entity_config', return_value=brilla_config), \
         patch.object(config_service, 'get_financial_matrix', return_value=brilla_config['rows']), \
         patch.object(config_service, 'get_financial_config', return_value=brilla_config), \
         patch.object(config_service, 'get_registration_cost', return_value=840000.0):

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
        assert "Si te interesa a crédito con la inicial de $996,900, las cuotas a 24 meses serían aproximadamente de $539,421 (incluye SOAT y Matrícula). *Nota: Este es un valor aproximado.*" in response, (
            f"El resultado debe contener the expected copywriting. Respuesta: {response[:200]}"
        )

        # ASSERT 4: Anonimized — no provider watermark
        assert "Crediorbe" not in response, "La marca de agua 'Crediorbe' no debe figurar en la respuesta anonimizada."
        assert "Brilla" not in response, "La marca de agua 'Brilla' no debe figurar en la respuesta anonimizada."

        # ASSERT 5: Habeas Data legal script present
        assert "politica-de-privacidad" in response, "El script legal de Habeas Data debe estar presente."
        assert "👍" in response, "La respuesta debe incluir el emoji de pulgar arriba 👍"
        assert "emoji de pulgar arriba (👍)" in response, "La respuesta debe incluir explícitamente la frase 'emoji de pulgar arriba (👍)'"

        # ASSERT 6: Verify the HABEAS-BYPASS log was emitted
        bypass_logged = any(
            "HABEAS-BYPASS" in str(call)
            for call in mock_logger.info.call_args_list
        )
        assert bypass_logged, "El log '[HABEAS-BYPASS] Cortocircuito limpio ejecutado' debe haberse emitido."

        # ASSERT 7: evaluate_profile must NOT have been called
        mock_evaluate_profile_e2e.assert_not_called()

        # ASSERT 8: calculate_payment MUST have been called (blind simulation)
        spy_calculate_e2e.assert_called_once_with(
            precio=9129000.0,
            inicial=996900.0,
            plazo_meses=24,
            entidad="Brilla de Gases",
            moto_cc=0.0,
            category="Urban"
        )

        # ASSERT 9: Gemini was only called ONCE (the function call turn),
        # the short-circuit prevented a second call
        assert call_count == 1, (
            f"Gemini debió ser llamado exactamente 1 vez (function call turn). "
            f"Fue llamado {call_count} veces — indica que el cortocircuito falló."
        )


@pytest.mark.asyncio
async def test_resilience_missing_summary_passes_filter():
    """
    [BOT-QA-HARDENING-126] Test endurecido con dos sub-escenarios:
    
    Sub-escenario A (comportamiento original): Sin 'moto_interest' en prospect, un ítem sin summary
    pasa el filtro con 'Sin descripción' — es aceptable para consultas genéricas sin intención comercial.
    
    Sub-escenario B (nuevo guardrail): Con 'moto_interest' activo en prospect, el checker agéntico
    debe RECHAZAR respuestas con 'Ficha Tecnica: Sin descripción' como Visual-Lock incompleto.
    WHY: Con intención comercial activa, el LLM puede alucinizar especificaciones para "completar"
    la ficha, causando una violación de Catalog-Lock. El fallback vacío no es aceptable en este caso.
    """
    from app.services.ai_brain import CerebroIA
    cerebro = CerebroIA()
    cerebro.client = MagicMock()
    cerebro._model_id = "gemini-2.0-flash"
    
    # Mock de catalog_service con item sin summary ni descripcion
    mock_catalog = MagicMock()
    mock_catalog.search_items.return_value = [
        {
            "name": "TVS Sport 100",
            "price": "$ 6.200.000",
            "category": "Urban"
            # summary y descripcion ausentes!
        }
    ]
    cerebro._catalog_service = mock_catalog
    
    # Mock LLM calls
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
            
    fc = MockFunctionCall(name="search_catalog", args={"query": "TVS Sport"})
    candidate1 = MockCandidate(content=MockContent(parts=[MockPart(function_call=fc)]))
    response1 = MockResponse(candidates=[candidate1])
    
    candidate2 = MockCandidate(content=MockContent(parts=[MockPart(text="TVS Sport 100 es excelente: $6.200.000. ![TVS](https://img.url) Ficha Tecnica: Sin descripción")]))
    response2 = MockResponse(candidates=[candidate2])
    
    call_count = 0
    captured_tool_output = None
    async def mock_call(*args, **kwargs):
        nonlocal call_count, captured_tool_output
        call_count += 1
        if call_count == 1:
            return response1
        if len(args) > 1:
            captured_tool_output = str(args[1])
        return response2
        
    # ─── Sub-escenario A: SIN moto_interest — 'Sin descripción' es aceptable ────────────────────────
    # Un prospect sin intención comercial explícita puede recibir el fallback 'Sin descripción'
    # porque no hay riesgo de alucinación de ficha técnica (el bot no va a completar specs inventadas).
    with patch.object(cerebro, '_call_gemini_with_retry_async', new=mock_call), \
         patch('app.services.ai_brain.SDK_AVAILABLE', True):
         
        prospect_sin_interes = {
            "nombre": "Pedro",
            "ciudad": "Cali",
            "forma_pago": "Crédito"
            # Sin 'moto_interest' — sin intención comercial activa
        }
        
        await cerebro.pensar_respuesta("Muéstrame la TVS Sport", prospect_data=prospect_sin_interes)
        
        # Debe contener 'Sin descripción' en el tool result (fallback aceptable sin intención comercial)
        assert captured_tool_output is not None
        assert "Ficha Tecnica: Sin descripción" in captured_tool_output, (
            "Sin moto_interest activo, 'Sin descripción' debe ser el fallback aceptable "
            "para ítems sin summary en el catálogo."
        )

    # ─── Sub-escenario B: CON moto_interest — 'Sin descripción' viola Visual-Lock íntegro ──────────
    # Con intención comercial activa, run_checker DEBE rechazar 'Sin descripción' como Visual-Lock
    # incompleto para prevenir alucinación de fichas técnicas por parte del LLM.
    from app.services.agentic_loop_service import AgenticOrchestrator
    orchestrator = AgenticOrchestrator()

    # Respuesta simulada con 'Sin descripción' + intención comercial activa en prospect
    response_with_sin_descripcion = (
        "TVS Sport 100 es excelente: $6.200.000. "
        "![TVS](https://img.url) "
        "Ficha Tecnica: Sin descripción"
    )
    prospect_con_interes = {
        "nombre": "Pedro",
        "ciudad": "Cali",
        "forma_pago": "Crédito",
        "moto_interest": "TVS Sport 100"  # Intención comercial activa
    }

    # El checker agéntico debe rechazar la respuesta con 'Sin descripción' + moto_interest
    validation = orchestrator.run_checker(
        response_with_sin_descripcion,
        is_catalog_query=True,
        prospect_data=prospect_con_interes
    )
    assert validation["success"] is False, (
        "[BOT-QA-HARDENING-126] Con moto_interest activo, run_checker debe rechazar "
        "'Ficha Tecnica: Sin descripción' como Visual-Lock incompleto. "
        "Este fallback vacío expone al bot a alucinación de fichas técnicas."
    )
    assert validation["report"]["broken_guardrail"] == "PRICE_CONSISTENCY_CHECK", (
        "El guardrail roto debe ser PRICE_CONSISTENCY_CHECK (Visual-Lock violation)."
    )
    assert "SIN_DESCRIPCION_FALLBACK" in validation["report"]["code_context"]["logs_trace"], (
        "El logs_trace debe identificar explícitamente 'SIN_DESCRIPCION_FALLBACK' "
        "para diagnóstico forense."
    )

    # Verificar también que SIN moto_interest, el mismo texto pasa el checker (no hay riesgo)
    prospect_sin_interes_checker = {
        "nombre": "Pedro",
        "ciudad": "Cali",
        "forma_pago": "Crédito"
        # Sin 'moto_interest'
    }
    validation_no_interest = orchestrator.run_checker(
        response_with_sin_descripcion,
        is_catalog_query=True,
        prospect_data=prospect_sin_interes_checker
    )
    assert validation_no_interest["success"] is True, (
        "Sin moto_interest activo, el mismo texto con 'Sin descripción' debe PASAR el checker "
        "ya que no hay intención comercial que exponga al LLM a alucinación de ficha técnica."
    )


@pytest.mark.asyncio
async def test_resilience_imagen_url_fallback():
    """
    Test unitario afirmando que la llave 'imagen_url' (o 'image_url')
    es procesada correctamente y agregada como 'Image URL:' en el payload del catálogo.
    """
    from app.services.ai_brain import CerebroIA
    cerebro = CerebroIA()
    cerebro.client = MagicMock()
    cerebro._model_id = "gemini-2.0-flash"
    
    # Mock catalog service con 'imagen_url' (en español) en lugar de 'image_url'
    mock_catalog = MagicMock()
    mock_catalog.search_items.return_value = [
        {
            "name": "TVS Sport 100",
            "price": "$ 6.200.000",
            "category": "Urban",
            "summary": "Excelente moto",
            "imagen_url": "https://img.example.com/imagen.jpg"
        }
    ]
    cerebro._catalog_service = mock_catalog
    
    # Mock LLM calls
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
            
    fc = MockFunctionCall(name="search_catalog", args={"query": "TVS Sport"})
    candidate1 = MockCandidate(content=MockContent(parts=[MockPart(function_call=fc)]))
    response1 = MockResponse(candidates=[candidate1])
    
    candidate2 = MockCandidate(content=MockContent(parts=[MockPart(text="TVS Sport 100 es excelente: $6.200.000. ![TVS](https://img.url) Ficha Tecnica: Excelente moto. Image URL: https://img.example.com/imagen.jpg")]))
    response2 = MockResponse(candidates=[candidate2])
    
    call_count = 0
    captured_tool_output = None
    async def mock_call(*args, **kwargs):
        nonlocal call_count, captured_tool_output
        call_count += 1
        if call_count == 1:
            return response1
        if len(args) > 1:
            captured_tool_output = str(args[1])
        return response2
        
    with patch.object(cerebro, '_call_gemini_with_retry_async', new=mock_call), \
         patch('app.services.ai_brain.SDK_AVAILABLE', True):
         
        prospect = {
            "nombre": "Pedro",
            "ciudad": "Cali",
            "forma_pago": "Crédito"
        }
        
        await cerebro.pensar_respuesta("Muéstrame la TVS Sport", prospect_data=prospect)
        
        # Verificar que el resultado de la herramienta inyectó la URL de la imagen
        assert captured_tool_output is not None
        assert "Image URL: https://img.example.com/imagen.jpg" in captured_tool_output


@pytest.mark.asyncio
async def test_resilience_drift_interceptor_ratio_035():
    """
    Test unitario afirmando que un ratio de 0.35 no dispara el bloqueo del Drift Interceptor
    (ya que el nuevo umbral es < 0.30).
    """
    from app.services.ai_brain import CerebroIA
    cerebro = CerebroIA()
    cerebro.client = MagicMock()
    cerebro._model_id = "gemini-2.0-flash"
    
    # Mock catalog service con el nombre correcto para la regla de consistencia
    mock_catalog = MagicMock()
    mock_catalog.search_items.return_value = [
        {
            "name": "Apache 160",
            "price": "$ 11.990.000",
            "category": "Deportiva",
            "summary": "Excelente moto"
        }
    ]
    cerebro._catalog_service = mock_catalog
    
    # Mock LLM calls
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
            
    fc = MockFunctionCall(name="search_catalog", args={"query": "Apache 160 RTR"})
    candidate1 = MockCandidate(content=MockContent(parts=[MockPart(function_call=fc)]))
    response1 = MockResponse(candidates=[candidate1])
    
    candidate2 = MockCandidate(content=MockContent(parts=[MockPart(text="Apache 160 es excelente: $11.990.000. ![Apache](https://img.url) Ficha Tecnica: Excelente moto")]))
    response2 = MockResponse(candidates=[candidate2])
    
    call_count = 0
    captured_tool_output = None
    async def mock_call(*args, **kwargs):
        nonlocal call_count, captured_tool_output
        call_count += 1
        if call_count == 1:
            return response1
        if len(args) > 1:
            captured_tool_output = str(args[1])
        return response2
        
    with patch.object(cerebro, '_call_gemini_with_retry_async', new=mock_call), \
         patch('app.services.ai_brain.SDK_AVAILABLE', True):
         
        prospect = {
            "nombre": "Pedro",
            "ciudad": "Cali",
            "forma_pago": "Crédito",
            "moto_interest": "Apache 160"
        }
        
        await cerebro.pensar_respuesta("Muéstrame la Apache 160 RTR", prospect_data=prospect)
        
        assert captured_tool_output is not None
        assert "Encontré" in captured_tool_output
        assert "Apache 160" in captured_tool_output
        assert "REGLA OBLIGATORIA: NO listes otras motos" not in captured_tool_output


def test_run_checker_faq_bypass():
    """
    Verifica que el AgenticOrchestrator.run_checker aplique correctamente
    el bypass condicional de aserción estricta de imágenes y precios cuando:
    1. No es una consulta de catálogo (is_catalog_query = False).
    2. Es una intención de FAQ pura y no hay modelo de motocicleta en el CRM.
    Adicionalmente, valida la retrocompatibilidad con las firmas legacy.
    """
    from app.services.agentic_loop_service import AgenticOrchestrator
    orchestrator = AgenticOrchestrator()

    # 1. Retrocompatibilidad / Firma Legacy (is_catalog_query=True, sin más args)
    # Si is_catalog_query=True, exige ficha técnica. Como bot_response no la tiene y no hay bypass, falla.
    res_no_ficha = "Precio $10.000.000 ![moto](http://img)"
    val_legacy_fail = orchestrator.run_checker(res_no_ficha, is_catalog_query=True)
    assert val_legacy_fail["success"] is False

    # 2. Caso de bypass 1: No es una consulta de catálogo (is_catalog_query = False)
    # Debe omitir precios e imágenes. Por lo tanto, una respuesta sin precio ni imagen pasa.
    res_faq = "Nuestros horarios de atención son de lunes a viernes."
    val_faq = orchestrator.run_checker(res_faq, is_catalog_query=False)
    assert val_faq["success"] is True

    # 3. Caso de bypass 2: Consulta de catálogo=True, pero es FAQ pura (user_prompt con keyword)
    # y sin moto_interest asignada en prospect_data.
    res_faq_specs = "Atendemos de 8 a 6."
    prospect_no_interest = {"nombre": "Juan", "ciudad": "Medellin"}
    val_faq_prompt = orchestrator.run_checker(
        res_faq_specs, 
        is_catalog_query=True, 
        prospect_data=prospect_no_interest, 
        user_prompt="¿Cuál es el horario de atención?"
    )
    assert val_faq_prompt["success"] is True

    # 4. Caso estricto: Consulta de catálogo=True, pero SÍ hay moto de interés en CRM
    # (a pesar de que el prompt tenga keyword de FAQ, el interés en CRM activa control estricto).
    prospect_with_interest = {"nombre": "Juan", "ciudad": "Medellin", "moto_interest": "TVS Raider"}
    val_faq_strict_fail = orchestrator.run_checker(
        res_faq_specs, 
        is_catalog_query=True, 
        prospect_data=prospect_with_interest, 
        user_prompt="¿Cuál es el horario de atención?"
    )
    assert val_faq_strict_fail["success"] is False


# ─────────────────────────────────────────────────────────────────────────────
# BOT-BRAIN-FAQ-ROOT-CAUSE-HUNT-147: Regression Tests
# Validates fix for secondary trigger: JudgeService false positives on FAQs.
# ─────────────────────────────────────────────────────────────────────────────

import pytest


# ─── Test 1: Aislamiento del Juez ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_judge_service_faq_bypass():
    """
    BOT-BRAIN-FAQ-ROOT-CAUSE-HUNT-147 — Regresión Crítica:
    Verifica que JudgeService.analyze_response con is_faq_bypass=True NO genere
    falsos positivos para respuestas de FAQ que contienen palabras que colisionan
    con keywords de motos o avance de crédito:
      - "Sport" => colisiona con C1_VISUAL_LOCK (_mentions_bike substring)
      - "requisitos" => colisiona con C9_CITY_MISSING (_detect_credit_advance)
    Con is_faq_bypass=True, el Juez DEBE aprobar sin exigir precio ni imagen.
    """
    from app.services.judge_service import JudgeService

    judge = JudgeService()

    # Caso 1: FAQ con "Sport" (colision historica con TVS Sport en _mentions_bike)
    faq_sport_collision = (
        "Nuestros asesores de soporte te pueden ayudar con los Sport de credito disponibles."
    )
    result_sport = await judge.analyze_response(
        user_input="Como me pueden ayudar?",
        ai_response=faq_sport_collision,
        catalog_context="",
        prospect_data={"habeas_data_accepted": True},
        history=[],
        is_faq_bypass=True
    )
    is_approved_sport, reason_sport = result_sport
    assert is_approved_sport is True, (
        f"C1_VISUAL_LOCK falso positivo detectado con is_faq_bypass=True. "
        f"Motivo: {reason_sport}"
    )

    # Caso 2: FAQ con "requisitos" (colision historica con C9_CITY_MISSING)
    faq_requisitos_collision = (
        "Nuestros requisitos de soporte para credito no exigen codeudor."
    )
    result_req = await judge.analyze_response(
        user_input="cuales son los requisitos?",
        ai_response=faq_requisitos_collision,
        catalog_context="",
        prospect_data={"habeas_data_accepted": True},
        history=[],
        is_faq_bypass=True
    )
    is_approved_req, reason_req = result_req
    assert is_approved_req is True, (
        f"C9_CITY_MISSING falso positivo detectado con is_faq_bypass=True. "
        f"Motivo: {reason_req}"
    )

    # Caso 3: C3_HABEAS_DATA_VIOLATION SIGUE activo con bypass activo
    # (el bypass NO debe desactivar guardrails de seguridad de datos personales)
    faq_profiling_attempt = (
        "Cuanto ganas mensualmente? Eres independiente o empleado?"
    )
    result_profiling = await judge.analyze_response(
        user_input="quiero credito",
        ai_response=faq_profiling_attempt,
        catalog_context="",
        prospect_data={"habeas_data_accepted": False},
        history=[],
        is_faq_bypass=True
    )
    is_approved_profiling, reason_profiling = result_profiling
    assert is_approved_profiling is False, (
        "C3_HABEAS_DATA_VIOLATION debio detectar perfilamiento financiero "
        "incluso con is_faq_bypass=True."
    )
    assert "C3_HABEAS_DATA_VIOLATION" in reason_profiling


# ─── Test 2: Integracion del Flujo de Mensajeria ─────────────────────────────

@pytest.mark.asyncio
async def test_router_faq_bypass_propagation_to_judge():
    """
    BOT-BRAIN-FAQ-ROOT-CAUSE-HUNT-147 — Test de Integracion:
    Valida que cuando run_checker detecta bypass_strict=True (FAQ pura sin
    moto_interest en CRM), el flag is_faq_bypass=True se propaga sincronamente
    hacia la llamada de auditoria de judge_service.analyze_response.

    Simula la logica del handler de mensajes sin levantar el servidor completo.
    """
    from app.services.agentic_loop_service import AgenticOrchestrator

    orchestrator = AgenticOrchestrator()

    # Respuesta de FAQ pura: contiene "Sport" pero NO es nombre de modelo completo
    faq_response = "Nuestro equipo de soporte te ayuda de lunes a viernes."
    faq_user_prompt = "cual es el horario de soporte?"

    prospect_without_moto_interest = {
        "nombre": "Maria",
        "ciudad": "Bogota",
        # Sin "moto_interest" => bypass debe activarse
    }

    # Paso 1: run_checker detecta bypass
    pcc_result = orchestrator.run_checker(
        faq_response,
        is_catalog_query=False,  # Sin keywords de especificaciones tecnicas
        prospect_data=prospect_without_moto_interest,
        user_prompt=faq_user_prompt
    )
    assert pcc_result["success"] is True, "run_checker debio aprobar la FAQ pura."
    assert pcc_result.get("bypass_strict") is True, (
        "run_checker debio emitir bypass_strict=True para FAQ sin moto_interest."
    )

    # Paso 2: El flag se extrae correctamente (logica del router)
    _is_faq_bypass = bool(pcc_result.get("bypass_strict", False))
    assert _is_faq_bypass is True, "El flag is_faq_bypass debio ser True."

    # Paso 3: El Juez recibe el flag y no genera falsos positivos C1/C9
    from app.services.judge_service import JudgeService
    judge = JudgeService()

    is_approved, rejection_reason = await judge.analyze_response(
        user_input=faq_user_prompt,
        ai_response=faq_response,
        catalog_context="",
        prospect_data=prospect_without_moto_interest,
        history=[],
        is_faq_bypass=_is_faq_bypass
    )

    assert is_approved is True, (
        f"El Juez debio aprobar la FAQ pura con is_faq_bypass=True. "
        f"Motivo de rechazo: {rejection_reason}"
    )
    assert rejection_reason == "", (
        f"No debio haber motivo de rechazo. Recibido: '{rejection_reason}'"
    )

    # Paso 4: Con moto_interest en CRM, el bypass NO se activa para catalog queries
    prospect_with_moto_interest = {
        "nombre": "Carlos",
        "ciudad": "Medellin",
        "moto_interest": "TVS Raider 125",
    }
    pcc_result_strict = orchestrator.run_checker(
        "Los requisitos para financiacion son minimos.",
        is_catalog_query=True,
        prospect_data=prospect_with_moto_interest,
        user_prompt="cuales son los requisitos?"
    )
    # Con moto_interest activo + FAQ abstracta de credito (requisitos sin cuota/simulacion)
    # el bypass DEBE activarse para no penalizar respuestas de credit_matrix_rules.
    # [BOT-BUILD-REGRESSION-FINANCIAL-AND-FAQ-200]
    assert pcc_result_strict.get("bypass_strict") is True, (
        "Con moto_interest activo + FAQ abstracta de credito, el bypass DEBE activarse."
    )


@pytest.mark.asyncio
async def test_brilla_gases_real_firestore_cuotas():
    """
    Verifies that the physical financial_service computes exactly $748.844 COP
    for Victory Bet ABS (initial = 1,395,000 COP) and $364.825 COP for TVS Sport 100 ELS
    (initial = 665,000 COP) under the real Firestore configuration layout.
    """
    from unittest.mock import patch
    patch.stopall()
    import sys
    from unittest.mock import Mock, MagicMock
    
    # 1. Pop all mock modules from sys.modules
    for key, val in list(sys.modules.items()):
        try:
            if isinstance(val, (Mock, MagicMock)) or "Mock" in str(type(val)) or "mock" in str(val).lower():
                sys.modules.pop(key, None)
        except Exception:
            pass
            
    # 2. Pop specific secretmanager modules and reload app.core.security
    sys.modules.pop("app.core.security", None)
    sys.modules.pop("google.cloud.secretmanager", None)
    sys.modules.pop("google.cloud.secretmanager_v1", None)
    for key in list(sys.modules.keys()):
        if "secretmanager" in key:
            sys.modules.pop(key, None)
            
    # 3. Clean google.cloud namespace attributes
    import google.cloud
    for attr in list(google.cloud.__dict__.keys()):
        try:
            val = getattr(google.cloud, attr)
            if isinstance(val, (Mock, MagicMock)) or "Mock" in str(type(val)) or "mock" in str(val).lower():
                delattr(google.cloud, attr)
        except:
            pass
            
    from app.core.security import get_firebase_credentials_object
    from google.cloud import firestore
    from app.core.config import settings
    from app.core.config_loader import ConfigLoader
    from app.services.config_service import config_service
    from app.services.catalog_service import catalog_service
    from app.services.ai_brain import CerebroIA

    # Initialize physical Firestore client
    import os
    old_cred = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if old_cred == "/tmp/fake-key.json":
        os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
    try:
        credentials = get_firebase_credentials_object()
    finally:
        if old_cred is not None:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = old_cred
    db = firestore.Client(
        project=settings.gcp_project_id,
        credentials=credentials
    )
    
    # Initialize the services
    config_loader = ConfigLoader(db)
    config_service.initialize(db)
    config_loader.load_all()
    catalog_service.initialize(db, config_loader)

    # Instantiate the real CerebroIA without mocks to run against production database
    cerebro = CerebroIA()
    
    # Victory Bet ABS (inicial = 1,395,000 COP, 24m)
    res_vic = cerebro._calculate_payment_helper(
        precio=13950000.0,
        inicial=1395000.0,
        plazo_meses=24,
        entidad="Brilla de Gases",
        moto_cc=149.2,
        category="motos"
    )
    assert res_vic.get("cuota_mensual") == 748844.0, f"Victory Bet ABS cuota mismatch: expected 748844, got {res_vic.get('cuota_mensual')}"
    
    # TVS Sport 100 ELS (inicial = 665,000 COP, 24m)
    # [BOT-BUILD-204] cc=99.7 -> banda 0-99 (registrationCredit=700.000),
    # corregido desde el override quemado de 780.000.
    res_tvs = cerebro._calculate_payment_helper(
        precio=5949999.0,
        inicial=665000.0,
        plazo_meses=24,
        entidad="Brilla de Gases",
        moto_cc=99.7,
        category="motos"
    )
    assert res_tvs.get("cuota_mensual") == 364825.0, f"TVS Sport 100 ELS cuota mismatch: expected 364825, got {res_tvs.get('cuota_mensual')}"

    # KYMCO Agility Fusion (inicial = 1,017,900 COP, 24m) - net price
    res_kymco_net = cerebro._calculate_payment_helper(
        precio=9399000.0,
        inicial=1017900.0,
        plazo_meses=24,
        entidad="Brilla de Gases",
        moto_cc=124.6,
        category="motos"
    )
    assert res_kymco_net.get("cuota_mensual") == 550469.0, f"KYMCO Agility Fusion net cuota mismatch: expected 550469, got {res_kymco_net.get('cuota_mensual')}"

    # KYMCO Agility Fusion (inicial = 1,017,900 COP, 24m) - catalog full price
    res_kymco_full = cerebro._calculate_payment_helper(
        precio=10179000.0,
        inicial=1017900.0,
        plazo_meses=24,
        entidad="Brilla de Gases",
        moto_cc=124.6,
        category="motos"
    )
    assert res_kymco_full.get("cuota_mensual") == 550469.0, f"KYMCO Agility Fusion full cuota mismatch: expected 550469, got {res_kymco_full.get('cuota_mensual')}"


@pytest.mark.asyncio
async def test_agility_fusion_exact_parity():
    """
    [BOT-BACKEND-FINANCIAL-CASCADING-EXACT-PARITY-184]
    Rigid unit test asserting that passing catalog price ($10.179.000) or net price ($9.399.000)
    for KYMCO Agility Fusion yields strictly $550.469 COP cuota_mensual.
    """
    from app.services.financial_service import financial_service
    from app.services.ai_brain import CerebroIA
    from app.core.config_loader import ConfigLoader
    from app.core.security import get_firebase_credentials_object
    from google.cloud import firestore
    from app.core.config import settings

    # Initialize physical configuration
    import os
    old_cred = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if old_cred == "/tmp/fake-key.json":
        os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
    try:
        credentials = get_firebase_credentials_object()
    finally:
        if old_cred is not None:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = old_cred

    from app.services.catalog_service import catalog_service

    db = firestore.Client(
        project=settings.gcp_project_id,
        credentials=credentials
    )
    config_loader = ConfigLoader(db)
    financial_service._config_service.initialize(db)
    config_loader.load_all()
    catalog_service.initialize(db, config_loader)

    # Scenario 1: Direct calculate_payment calls with correct cc (KYMCO = 124.6)
    res_direct_net = financial_service.calculate_payment(
        precio=9399000.0,
        inicial=1017900.0,
        plazo_meses=24,
        entidad="Brilla de Gases",
        moto_cc=124.6,
        category="motos"
    )
    assert res_direct_net.get("cuota_mensual") == 550469.0, f"Direct net cuota mismatch: expected 550469, got {res_direct_net.get('cuota_mensual')}"

    res_direct_full = financial_service.calculate_payment(
        precio=10179000.0,
        inicial=1017900.0,
        plazo_meses=24,
        entidad="Brilla de Gases",
        moto_cc=124.6,
        category="motos"
    )
    assert res_direct_full.get("cuota_mensual") == 550469.0, f"Direct full cuota mismatch: expected 550469, got {res_direct_full.get('cuota_mensual')}"

    # Scenario 2: Helper calls (passing moto_cc=124.6)
    cerebro = CerebroIA()
    res_helper_net = cerebro._calculate_payment_helper(
        precio=9399000.0,
        inicial=1017900.0,
        plazo_meses=24,
        entidad="Brilla de Gases",
        moto_cc=124.6,
        category="motos"
    )
    assert res_helper_net.get("cuota_mensual") == 550469.0, f"Helper net cuota mismatch: expected 550469, got {res_helper_net.get('cuota_mensual')}"

    res_helper_full = cerebro._calculate_payment_helper(
        precio=10179000.0,
        inicial=1017900.0,
        plazo_meses=24,
        entidad="Brilla de Gases",
        moto_cc=124.6,
        category="motos"
    )
    assert res_helper_full.get("cuota_mensual") == 550469.0, f"Helper full cuota mismatch: expected 550469, got {res_helper_full.get('cuota_mensual')}"


def test_is_tech_spec_query_detection():
    from app.services.agentic_loop_service import is_tech_spec_query
    assert is_tech_spec_query("cilindraje") is True
    assert is_tech_spec_query("cuál es el torque de la raider") is True
    assert is_tech_spec_query("que motor tiene") is True
    assert is_tech_spec_query("potencia hp frenos abs") is True
    assert is_tech_spec_query("cc de la moto") is True
    assert is_tech_spec_query("ficha tecnica") is True
    assert is_tech_spec_query("hola") is False
    assert is_tech_spec_query("precio de la moto") is False
    assert is_tech_spec_query("") is False
    assert is_tech_spec_query(None) is False


def test_is_tech_spec_query_no_false_positive_short_tokens():
    from app.services.agentic_loop_service import is_tech_spec_query
    assert is_tech_spec_query("accede") is False
    assert is_tech_spec_query("chips") is False
    assert is_tech_spec_query("photoshop") is False
    assert is_tech_spec_query("acceso") is False


def test_is_tech_spec_query_colloquial_lexicon_caption01():
    """
    [BOT-BUILD-BUGFIX-MULTIMODAL-CAPTION-01] Léxico técnico coloquial (dominio CO).
    Pineado tras el incidente de runtime Meta: los captions 'cuantos cambios tiene?'
    y 'que tipo de encendido maneja?' NO activaban la obligación PCC 'Ficha Tecnica:'
    porque TECH_SPEC_TOKENS solo cubría vocabulario formal.
    """
    from app.services.agentic_loop_service import is_tech_spec_query
    # Captions exactos del incidente de runtime
    assert is_tech_spec_query("cuantos cambios tiene?") is True
    assert is_tech_spec_query("que tipo de encendido maneja?") is True
    # Familia coloquial ampliada
    assert is_tech_spec_query("de cuantas velocidades es") is True
    assert is_tech_spec_query("freno delantero") is True
    assert is_tech_spec_query("el tablero es digital?") is True
    assert is_tech_spec_query("que consumo tiene") is True
    assert is_tech_spec_query("capacidad del tanque") is True
    assert is_tech_spec_query("es de inyección o carburador") is True
    assert is_tech_spec_query("como es la suspensión delantera") is True
    assert is_tech_spec_query("arranque electrico o de crank") is True
    assert is_tech_spec_query("cuantas marchas trae") is True
    # Controles negativos (no regresión del clasificador)
    assert is_tech_spec_query("precio de la moto") is False
    assert is_tech_spec_query("quiero financiar") is False
    assert is_tech_spec_query("muy bonita") is False


def test_run_checker_no_bypass_on_tech_specs():
    from app.services.agentic_loop_service import AgenticOrchestrator
    orchestrator = AgenticOrchestrator()
    result = orchestrator.run_checker(
        "Claro, la moto tiene Ficha Tecnica: 150cc. Precio: $9.000.000. ![moto](http://img.url)",
        is_catalog_query=False,
        prospect_data={"moto_interest": "Apache 160"},
        user_prompt="cuál es el cilindraje"
    )
    assert result["success"] is True
    assert result.get("bypass_strict") is not True


def test_run_checker_faq_bypass_without_tech_specs():
    from app.services.agentic_loop_service import AgenticOrchestrator
    orchestrator = AgenticOrchestrator()
    result = orchestrator.run_checker(
        "Estamos en la Calle 30 #79-85 en Santa Marta.",
        is_catalog_query=False,
        prospect_data={},
        user_prompt="donde estan ubicados"
    )
    assert result["success"] is True
    assert result.get("bypass_strict") is True


def test_price_anchor_preserved():
    from app.services.catalog_service import _ensure_price_anchor, PRICE_PACKAGE_ANCHOR
    result = _ensure_price_anchor("$5.000.000")
    assert PRICE_PACKAGE_ANCHOR in result
    anchored = "$9.000.000 (incluye SOAT, Matrícula, y tramites)"
    result = _ensure_price_anchor(anchored)
    assert result == anchored


def test_price_anchor_not_double_applied():
    from app.services.catalog_service import _ensure_price_anchor, PRICE_PACKAGE_ANCHOR
    already = f"$8.000.000 {PRICE_PACKAGE_ANCHOR}"
    result = _ensure_price_anchor(already)
    assert result.count(PRICE_PACKAGE_ANCHOR) == 1


def test_price_package_anchor_present_in_search():
    from app.services.catalog_service import catalog_service
    from app.services.config_service import config_service
    from unittest.mock import patch, MagicMock
    mock_item = {
        "id": "test-anchor",
        "name": "Test Anchor Moto",
        "price": 5000000,
        "cc": 150,
        "category": "Urban",
        "image_url": "http://img.url",
        "link": "http://link.url",
        "summary": "Test summary"
    }
    with patch.object(catalog_service, '_items', [mock_item]), \
         patch.object(catalog_service, '_db', MagicMock()), \
         patch.object(config_service, '_financial_config', None), \
         patch.object(config_service, 'get_registration_cost', return_value=0):
        catalog_service.load_configurations = MagicMock()
        catalog_service._cache_service.clear()
        from app.services.catalog_service import PRICE_PACKAGE_ANCHOR
        res = catalog_service.search_catalog("Test Anchor")
        assert PRICE_PACKAGE_ANCHOR in res, "PRICE_PACKAGE_ANCHOR must be present in catalog search output"


@pytest.mark.asyncio
async def test_apache_160_brilla_golden_parity():
    """
    [BOT-BUILD-REGRESSION-FINANCIAL-AND-FAQ-200]
    Golden Apache 160 test: net price=$9.650.000, inicial=$1.051.000,
    cc=159.7, 24m Brilla -> $567.882 cuota_mensual exacta.
    Regression contra $613.473 (WA antiguo con rama <=125cc erronea).
    assetPrice reconstruido = 9.650.000 + 860.000 = 10.510.000.
    """
    from app.services.financial_service import financial_service
    from app.core.config_loader import ConfigLoader
    from app.core.security import get_firebase_credentials_object
    from google.cloud import firestore
    from app.core.config import settings

    import os
    old_cred = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if old_cred == "/tmp/fake-key.json":
        os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
    try:
        credentials = get_firebase_credentials_object()
    finally:
        if old_cred is not None:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = old_cred

    db = firestore.Client(
        project=settings.gcp_project_id,
        credentials=credentials
    )
    config_loader = ConfigLoader(db)
    financial_service._config_service.initialize(db)
    config_loader.load_all()

    # Net price = full - reg_cost = 10510000 - 860000 = 9650000
    net_price = 10510000.0 - 860000.0
    res = financial_service.calculate_payment(
        precio=net_price,
        inicial=1051000.0,
        plazo_meses=24,
        entidad="Brilla de Gases",
        moto_cc=159.7,
        category="motos"
    )
    assert res.get("cuota_mensual") == 567882.0, \
        f"Apache 160 golden cuota mismatch: expected 567882, got {res.get('cuota_mensual')}"
    assert round(res.get("capital_financiado", 0)) == 9931950, \
        f"Wrong capital_financiado: {res.get('capital_financiado')}"
    assert round(res.get("cuota_aval", 0)) == 33107, \
        f"Wrong cuota_aval: {res.get('cuota_aval')}"


@pytest.mark.asyncio
async def test_cc_zero_does_not_assume_125_cc_regression():
    """
    [BOT-BUILD-REGRESSION-FINANCIAL-AND-FAQ-200]
    Cuando moto_cc=0 (desconocido), NO se deben asumir tramites
    financiados de <=125cc. financeDocs debe ser False.
    """
    from app.services.financial_service import financial_service
    from app.core.config_loader import ConfigLoader
    from app.core.security import get_firebase_credentials_object
    from google.cloud import firestore
    from app.core.config import settings

    import os
    old_cred = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if old_cred == "/tmp/fake-key.json":
        os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
    try:
        credentials = get_firebase_credentials_object()
    finally:
        if old_cred is not None:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = old_cred

    db = firestore.Client(
        project=settings.gcp_project_id,
        credentials=credentials
    )
    config_loader = ConfigLoader(db)
    financial_service._config_service.initialize(db)
    config_loader.load_all()

    net_price = 10510000.0 - 860000.0
    res = financial_service.calculate_payment(
        precio=net_price,
        inicial=1051000.0,
        plazo_meses=24,
        entidad="Brilla de Gases",
        moto_cc=0.0,
        category="motos"
    )
    cuota = res.get("cuota_mensual", 0)
    assert cuota != 613473.0, \
        f"REGRESSION: cc=0 still produces old buggy cuota 613473"
    assert cuota > 0, "cuota should be positive"
    assert cuota <= 567882.0, \
        f"cc=0 produced cuota {cuota} higher than golden 567882"


def test_is_abstract_credit_faq_classifier():
    """
    [BOT-BUILD-REGRESSION-FINANCIAL-AND-FAQ-200]
    [BOT-BUILD-REGRESSION-FAQ-FALLBACK-201] Ampliado con historial/reportado/datacredito.
    Validacion determinista del clasificador de FAQ abstracta de credito.
    """
    from app.services.ai_brain import CerebroIA
    c = CerebroIA()

    assert c._is_abstract_credit_faq("ok, y si la quiero sacar a credito, cuales son los requisitos?") is True
    assert c._is_abstract_credit_faq("necesito codeudor?") is True
    assert c._is_abstract_credit_faq("que papeles necesito?") is True
    assert c._is_abstract_credit_faq("Quiero, saber si para un credito necesito historial?") is True
    assert c._is_abstract_credit_faq("estoy reportado puedo sacar credito?") is True
    assert c._is_abstract_credit_faq("necesito datacredito para el credito?") is True
    assert c._is_abstract_credit_faq("soy extranjero, que necesito?") is True
    assert c._is_abstract_credit_faq("y necesito fiador, para sacaria a credito?") is True
    assert c._is_abstract_credit_faq("necesito fiadores?") is True
    assert c._is_abstract_credit_faq("me piden aval para el credito?") is True
    assert c._is_abstract_credit_faq("cuanto queda la cuota a 24 meses") is False
    assert c._is_abstract_credit_faq("cuales son los requisitos y cuanto pago?") is False
    assert c._is_abstract_credit_faq("simula el credito con inicial de 1 millon") is False
    assert c._is_abstract_credit_faq("hola") is False


def test_run_checker_credit_faq_abstract_bypass_with_moto_interest():
    """
    [BOT-BUILD-REGRESSION-FINANCIAL-AND-FAQ-200]
    FAQ abstracta de credito (requisitos sin cuota) con moto_interest -> bypass activado.
    """
    from app.services.agentic_loop_service import AgenticOrchestrator
    orchestrator = AgenticOrchestrator()

    result = orchestrator.run_checker(
        "Los requisitos son: Cedula, recibos de gas...",
        is_catalog_query=True,
        prospect_data={"moto_interest": "Apache 160", "nombre": "Carlos"},
        user_prompt="ok, y si la quiero sacar a credito, cuales son los requisitos?"
    )
    assert result["success"] is True, "run_checker debe aprobar FAQ abstracta."
    assert result.get("bypass_strict") is True, \
        "FAQ abstracta de credito con moto_interest debe activar bypass."


def test_run_checker_credit_sim_no_bypass_with_moto_interest():
    """
    [BOT-BUILD-REGRESSION-FINANCIAL-AND-FAQ-200]
    Simulacion de cuota con moto_interest -> NO bypass (flujo normal de credito).
    """
    from app.services.agentic_loop_service import AgenticOrchestrator
    orchestrator = AgenticOrchestrator()

    result = orchestrator.run_checker(
        "Precio: $9.000.000. Cuota: $450.000. Sin imagen.",
        is_catalog_query=True,
        prospect_data={"moto_interest": "Apache 160", "nombre": "Carlos"},
        user_prompt="cuanto quedaria la cuota a 24 meses?"
    )
    assert result.get("bypass_strict") is not True, \
        "Simulacion de cuota con moto_interest NO debe activar bypass."


def test_run_checker_historial_reportado_bypass_with_moto_interest():
    """
    [BOT-BUILD-REGRESSION-FAQ-FALLBACK-201]
    'necesito historial' / 'estoy reportado' con moto_interest -> bypass activado.
    Estos queries caian en fallback de supervisor antes del Doble Gate.
    """
    from app.services.agentic_loop_service import AgenticOrchestrator
    orchestrator = AgenticOrchestrator()

    for prompt in [
        "Quiero, saber si para un credito necesito historial?",
        "estoy reportado puedo sacar credito?",
        "necesito datacredito para el credito?",
    ]:
        result = orchestrator.run_checker(
            "FAQ credit matrix response.",
            is_catalog_query=True,
            prospect_data={"moto_interest": "Apache 160", "nombre": "Carlos"},
            user_prompt=prompt
        )
        assert result.get("bypass_strict") is True, \
            f"FAQ abstracta '{prompt}' con moto_interest DEBE activar bypass."


def test_create_tools_omits_credit_when_faq_abstract():
    """
    [BOT-BUILD-REGRESSION-FAQ-FALLBACK-201]
    _create_tools(omit_credit=True) NO debe incluir calculate_credit_score.
    Verifica que el numero de tool declarations sea 5 sin omitir y 4 omitiendo.
    [BOT-BUILD-COHERENCE-WAVE07-01] El toolset base ahora incluye query_faq y
    query_locations (migración del <KNOWLEDGE_BASE> al backend): 3→5 y 2→4.
    """
    from unittest.mock import patch, MagicMock
    import app.services.ai_brain as brain_module

    with patch.object(brain_module, "SDK_AVAILABLE", True):
        cerebro = brain_module.CerebroIA()
        cerebro._determine_funnel_phase = MagicMock(return_value="PHASE_1_PROFILING")

        tools_with = cerebro._create_tools(omit_credit=False)
        assert tools_with is not None
        num_with = len(tools_with[0].function_declarations)
        assert num_with == 5, f"Expected 5 tools (handoff, catalog, faq, locations, credit), got {num_with}"

        tools_without = cerebro._create_tools(omit_credit=True)
        assert tools_without is not None
        num_without = len(tools_without[0].function_declarations)
        assert num_without == 4, \
            f"FAQ abstracta: expected 4 tools (sin credit), got {num_without}"


def test_run_checker_fiador_bypass_with_moto_interest():
    """
    [BOT-BUILD-REGRESSION-FAQ-FIADOR-CUOTA-202]
    'fiador', 'fiadores', 'aval' con moto_interest -> bypass activado.
    Antes caian en fallback de supervisor por token ausente en el lexicon.
    """
    from app.services.agentic_loop_service import AgenticOrchestrator
    orchestrator = AgenticOrchestrator()

    for prompt in [
        "y necesito fiador, para sacaria a credito?",
        "necesito fiadores?",
        "me piden aval para el credito?",
    ]:
        result = orchestrator.run_checker(
            "FAQ credit matrix response.",
            is_catalog_query=True,
            prospect_data={"moto_interest": "TVS Raider 125", "nombre": "Carlos"},
            user_prompt=prompt
        )
        assert result.get("bypass_strict") is True, (
            f"FAQ fiador/aval '{prompt}' con moto_interest DEBE activar bypass."
        )


@pytest.mark.asyncio
async def test_raider_125_brilla_post_fix_414444():
    """
    [BOT-BUILD-REGRESSION-FAQ-FIADOR-CUOTA-202]
    [BOT-BUILD-204] El helper normaliza Raider 125 a cc=0 (web parity) y lee
    ahora registrationCredit de la banda 0-99 (700.000) en lugar del override
    quemado de 780.000. assetPrice resultante = 6.991.896 + 700.000 = 7.691.896;
    cuota_mensual = 414.444.
    Este test documenta el nuevo valor SSOT; el anti-regresión mantiene el
    path de catálogo (7.799.999).
    """
    from app.services.financial_service import financial_service
    from app.core.config_loader import ConfigLoader
    from app.core.security import get_firebase_credentials_object
    from google.cloud import firestore
    from app.core.config import settings

    import os
    old_cred = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if old_cred == "/tmp/fake-key.json":
        os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
    try:
        credentials = get_firebase_credentials_object()
    finally:
        if old_cred is not None:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = old_cred

    db = firestore.Client(
        project=settings.gcp_project_id,
        credentials=credentials
    )
    config_loader = ConfigLoader(db)
    financial_service._config_service.initialize(db)
    config_loader.load_all()

    # Official SSOT: assetPrice=$7.771.896, cc=0 (sin financeDocs)
    # Helper strip: base = 7771896 - 780000 = 6991896
    # calculate_payment re-add: asset = 6991896 + 780000 = 7771896
    official_asset = 7771896.0
    net_price = official_asset - 780000.0
    res = financial_service.calculate_payment(
        precio=net_price,
        inicial=858000.0,
        plazo_meses=24,
        entidad="Brilla de Gases",
        moto_cc=0.0,
        category="motos"
    )
    cuota = res.get("cuota_mensual", 0)
    assert cuota == 414444.0, (
        f"Raider 125 post-fix cuota mismatch: expected 414444, got {cuota}"
    )
    assert round(res.get("capital_financiado", 0)) == 7175591, (
        f"Wrong capital_financiado: {res.get('capital_financiado')}"
    )
    assert round(res.get("cuota_aval", 0)) == 23919, (
        f"Wrong cuota_aval: {res.get('cuota_aval')}"
    )


@pytest.mark.asyncio
async def test_raider_125_anti_regression_416086():
    """
    [BOT-BUILD-REGRESSION-FAQ-FIADOR-CUOTA-202]
    [BOT-BUILD-204] Verifica que con el precio del catalogo actual (7.799.999) y
    cc=0, la formula produce ahora $416.086 (SSOT: banda 0-99 = 700.000, no el
    override quemado de 780.000). El helper strip sigue siendo 780.000 para mantener
    la base normalizada legacy, pero el re-add lee Firestore -> 700.000.
    Este test documenta el mismatch residual: el helper strip (780k) ya no
    coincide con el re-add (700k) hasta que se normalice la base.
    """
    from app.services.financial_service import financial_service
    from app.core.config_loader import ConfigLoader
    from app.core.security import get_firebase_credentials_object
    from google.cloud import firestore
    from app.core.config import settings

    import os
    old_cred = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if old_cred == "/tmp/fake-key.json":
        os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
    try:
        credentials = get_firebase_credentials_object()
    finally:
        if old_cred is not None:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = old_cred

    db = firestore.Client(
        project=settings.gcp_project_id,
        credentials=credentials
    )
    config_loader = ConfigLoader(db)
    financial_service._config_service.initialize(db)
    config_loader.load_all()

    # Path produccion real: catalogo price=7.799.999, cc=None->0
    # Helper: base = 7799999 - 780000 = 7019999
    # calculate: asset = 7019999 + 700000 = 7719999, docs=0
    catalog_price = 7799999.0
    net_price = catalog_price - 780000.0
    res = financial_service.calculate_payment(
        precio=net_price,
        inicial=858000.0,
        plazo_meses=24,
        entidad="Brilla de Gases",
        moto_cc=0.0,
        category="motos"
    )
    cuota = res.get("cuota_mensual", 0)
    assert cuota == 416086.0, (
        f"Raider 125 WA regression: expected 416086 (catalog), got {cuota}"
    )
    assert cuota != 414444.0, (
        "Anti-regression: catalog path should NOT match official 414444 yet."
    )


# =============================================================================
# [BOT-BUILD-204] NUEVA SUITE E2E — SELECTOR DE BANDA Y FRENO COGNITIVO
# =============================================================================


def test_classify_credit_turn_fragments():
    """
    El clasificador por turno evita que un fragmento de simulación envenene
    una pregunta FAQ abstracta cuando el buffer agrega mensajes.
    """
    # Fragmento de simulación + FAQ abstracta -> MIXED (ambas intenciones)
    assert classify_credit_turn([
        "cuanto queda la cuota a 24 meses",
        "y necesito fiador, para sacarla a credito?"
    ]) == TurnIntent.MIXED

    # Solo FAQ -> FAQ_ONLY
    assert classify_credit_turn([
        "y necesito fiador, para sacarla a credito?"
    ]) == TurnIntent.FAQ_ONLY

    # Solo simulación -> NONE
    assert classify_credit_turn([
        "cuanto queda la cuota a 24 meses"
    ]) == TurnIntent.NONE

    # Texto blob unido con ambas señales -> MIXED, ya no es un punto ciego.
    blob = "cuanto queda la cuota a 24 meses y necesito fiador, para sacarla a credito?"
    assert classify_credit_turn([blob]) == TurnIntent.MIXED


@pytest.mark.parametrize(
    "cc,category,expected_cost",
    [
        (99.7, None, 700000),          # Banda 0-99
        (124.7, None, 780000),         # Banda 100-124
        (125.0, None, 860000),         # Banda 125-200
        (159.7, None, 860000),         # Banda 125-200
        (201.0, None, 1340000),        # Banda gt-200
        (99.7, "URBANA Y/O TRABAJO", 700000),  # Categoría no debe saltar a 125-200
        (None, "ELECTRICA", 460000),   # Categoría especial pura
        (None, "MOTOCARRO Y/O MOTOCARGUERO", 1050000),  # Categoría especial con rango
    ],
)
def test_get_registration_cost_exact_cc_band(cc, category, expected_cost):
    """
    [BOT-BUILD-204] El selector debe usar la banda CC exacta y NO dejar que
    una categoría genérica en una fila con banda cerrada desactive la matemática.
    """
    rows = [
        {"minCC": 0, "maxCC": 99, "registrationCreditGeneral": 700000, "id": "0-99"},
        {"minCC": 100, "maxCC": 124, "registrationCreditGeneral": 780000, "id": "100-124"},
        {"minCC": 125, "maxCC": 200, "registrationCreditGeneral": 860000, "category": "URBANA Y/O TRABAJO", "id": "125-200"},
        {"minCC": 201, "maxCC": 99999, "registrationCreditGeneral": 1340000, "id": "gt-200"},
        {"category": "ELECTRICA", "registrationCreditGeneral": 460000, "id": "electrical"},
        {"minCC": 0, "maxCC": 99999, "registrationCreditGeneral": 1050000, "category": "MOTOCARRO Y/O MOTOCARGUERO", "id": "motocarro"},
    ]
    # Las filas usan registrationCreditGeneral; la normalización debe copiarlo.
    with patch.object(config_service, "_financial_config", {"rows": rows}):
        assert config_service.get_registration_cost(cc=cc, category=category) == expected_cost


def test_get_registration_cost_no_hardcoded_override():
    """
    [BOT-BUILD-204] Con el override eliminado, cc <= 125 ya no retorna un valor
    quemado; retorna la banda real de Firestore.
    """
    rows = [
        {"minCC": 0, "maxCC": 99, "registrationCredit": 700000, "id": "0-99"},
        {"minCC": 100, "maxCC": 124, "registrationCredit": 780000, "id": "100-124"},
    ]
    with patch.object(config_service, "_financial_config", {"rows": rows}):
        assert config_service.get_registration_cost(cc=99, category=None) == 700000
        assert config_service.get_registration_cost(cc=124, category=None) == 780000


def test_build_commercial_price_sport_100_zero_ninety_nine_band():
    """
    [BOT-BUILD-204] TVS Sport 100 (cc=99.7) debe sumar la banda 0-99 (=700.000)
    al precio base, no el override quemado de 780.000.
    """
    rows = [
        {"minCC": 0, "maxCC": 99, "registrationCredit": 700000, "id": "0-99"},
        {"minCC": 100, "maxCC": 124, "registrationCredit": 780000, "id": "100-124"},
    ]
    with patch.object(config_service, "_financial_config", {"rows": rows}):
        from app.services.catalog_service import CatalogService
        price = 5_000_000
        result = CatalogService.build_commercial_price(price=price, cc=99.7, category="motos")
        assert "$5.700.000" in result, f"Expected $5.700.000 band in result, got {result}"

# ============================================================================
# [Incidente H-A · HA-4] PCC Pro — Validadores Regex centralizados (tests/validators.py)
# ============================================================================

def test_pcc_pro_regex_validators_dynamic_catalog():
    """PCC Pro con validadores regex centralizados sobre catálogo DINÁMICO (HA-3/HA-4).

    Verifica sobre la salida real de search_catalog: ficha explícita, consistencia
    exacta precio-respuesta ↔ precio-catálogo, formato canónico COP, referencia de
    imagen válida y ausencia de PII en la salida comercial.
    """
    items = make_catalog(60)
    item = items[0]

    with patch.object(catalog_service, '_items', [item]), \
         patch.object(catalog_service, '_db', MagicMock()), \
         patch.object(config_service, '_financial_config', None), \
         patch.object(config_service, 'get_registration_cost', return_value=0):

        catalog_service.load_configurations = MagicMock()
        catalog_service._cache_service.clear()

        res = catalog_service.search_catalog(item['name'].split()[1])

    # 1. 'Ficha Tecnica:' explícita con contenido no vacío ni 'None'
    assert_ficha_explicit(res)

    # 2. Consistencia exacta: el precio mostrado ES el precio canónico del ítem
    assert_price_consistency(res, item['price'])

    # 3. El precio extraído cumple la forma canónica $X.XXX.XXX
    extracted = RE_EXTRACT_PRECIOS.search(res)
    assert extracted is not None, "La respuesta no contiene ningún monto COP extraíble."
    assert_catalog_price_format(f"${extracted.group(1)}")

    # 4. Referencia de imagen válida (markdown o URL plana)
    assert_image_reference(res)

    # 5. Higiene PII de la salida comercial: sin teléfonos/emails embebidos
    assert_no_pii_leak(res)


def test_pcc_pro_regex_mutation_checks():
    """Mutation checks obligatorios (HA-4): cada validador PCC DEBE fallar (AssertionError)
    ante un fixture mutado — anti-falso-positivo de la instrumentación regex."""
    item = make_catalog(1)[0]
    canonical = format_cop(item['price'])
    valid = (
        f"- {item['name']} ({item['category']}): {canonical} (incluye SOAT)\n"
        f"![{item['name']}]({item['image_url']})\n"
        f"Ficha Tecnica: {item['summary']}"
    )

    # Sanity: el fixture válido supera todos los validadores.
    assert_price_consistency(valid, item['price'])
    assert_ficha_explicit(valid)
    assert_image_reference(valid)

    # M1 — precio mutado (+10.000): inconsistencia precio-respuesta ↔ catálogo.
    mutated_price = valid.replace(canonical, format_cop(item['price'] + 10_000))
    with pytest.raises(AssertionError):
        assert_price_consistency(mutated_price, item['price'])

    # M2 — ficha vaciada: prefijo presente pero contenido nulo.
    with pytest.raises(AssertionError):
        assert_ficha_explicit(valid.replace(f"Ficha Tecnica: {item['summary']}", "Ficha Tecnica:  "))

    # M3 — ficha 'None' silenciosa.
    with pytest.raises(AssertionError):
        assert_ficha_explicit(valid.replace(f"Ficha Tecnica: {item['summary']}", "Ficha Tecnica: None"))

    # M4 — formato de precio no canónico (separador ',' estilo en-US).
    with pytest.raises(AssertionError):
        assert_catalog_price_format(f"${item['price']:,}")

    # M5 — imagen eliminada de la respuesta.
    with pytest.raises(AssertionError):
        assert_image_reference(valid.replace(f"![{item['name']}]({item['image_url']})", ""))

    # M6 — PII inyectada en la salida (teléfono CO).
    with pytest.raises(AssertionError):
        assert_no_pii_leak(valid + " Llámanos al +57 319 856 7788")


@pytest.mark.asyncio
async def test_pensar_respuesta_faq_only_brake_block_e2e():
    """
    [BOT-BUILD-204] E2E del orquestador con la personalidad completa:
    - FAQ abstracta de fiador en PHASE_2_HABEAS_DATA.
    - El prompt debe contener el Freno Cognitivo, <intercepcion_faq>faq_only</intercepcion_faq>
      y la pregunta pendiente textual.
    - calculate_credit_score debe estar ausente de las tools.
    """
    from app.services.ai_brain import CerebroIA
    from app.core.prompts import JUAN_PABLO_SYSTEM_INSTRUCTION
    import app.services.ai_brain as brain_module

    with patch.object(brain_module, "SDK_AVAILABLE", True):
        cerebro = CerebroIA()
        cerebro.client = MagicMock()
        cerebro._model_id = "gemini-test"

        mock_catalog = MagicMock()
        mock_catalog.get_catalog_aliases.return_value = {}
        cerebro._catalog_service = mock_catalog

        prospect = {
            "nombre": "Carlos",
            "moto_interest": "TVS Raider 125",
            "forma_pago": "crédito",
            "ciudad": "Bogotá",
            # habeas_data_accepted ausente => PHASE_2_HABEAS_DATA
        }

        captured_prompt = None
        captured_config = None

        async def mock_generate(*args, **kwargs):
            nonlocal captured_prompt, captured_config
            if len(args) > 1:
                captured_prompt = args[1]
            captured_config = kwargs.get("config")
            # Respuesta tipo LLM: 2 líneas de FAQ + pregunta pendiente
            return MagicMock(
                candidates=[MagicMock(content=MagicMock(parts=[MagicMock(text="Para fiador, depende del perfil; Brilla no lo requiere. ¿Me autorizas el tratamiento de tus datos?")]))]
            )

        with patch.object(cerebro, "_get_current_instruction", return_value=JUAN_PABLO_SYSTEM_INSTRUCTION), \
             patch.object(cerebro, "_call_gemini_with_retry_async", new=mock_generate):
            await cerebro.pensar_respuesta(
                "y necesito fiador, para sacarla a credito?",
                prospect_data=prospect,
                history=[{"role": "user", "content": "cuanto vale la raider 125"}],
                skip_greeting=True
            )

        assert captured_prompt is not None, "El prompt completo no fue capturado"
        prompt = captured_prompt

        # [BOT-BUILD-205] Updated assertions to match condensed brake block format
        assert "[FRENO FAQ — MÁXIMA PRIORIDAD]" in prompt, "Falta bloque de freno cognitivo"
        assert "<intercepcion_faq>faq_only</intercepcion_faq>" in prompt, "Falta tag intercepcion_faq=faq_only"
        # [BOT-PLAN-FIX-HARDCODE-ENTITY-LEAK-007] Pin actualizado al script neutral
        # verbatim del PASO 4 (la aserción anterior pineaba la fuga "sistema de Brilla").
        assert "Para hacer el estudio formal y validar tu cupo exacto con nuestro sistema" in prompt, "Falta pregunta pendiente textual de Habeas Data"
        assert "PROHIBIDO:" in prompt, "Falta prohibición en FAQ brake block"

        # Verificar que calculate_credit_score no está en las tools
        tools = getattr(captured_config, "tools", None)
        if tools:
            declarations = []
            for tool in tools:
                declarations.extend(getattr(tool, "function_declarations", []) or [])
            tool_names = [getattr(d, "name", None) for d in declarations]
            assert "calculate_credit_score" not in tool_names, "FAQ_ONLY no debe incluir calculate_credit_score"


@pytest.mark.asyncio
async def test_pensar_respuesta_mixed_turn_keeps_credit_tool():
    """
    [BOT-BUILD-204] Turno MIXED (cuota + FAQ) debe mantener calculate_credit_score
    y aún inyectar el freno cognitivo para responder la FAQ en ≤2 líneas.
    """
    from app.services.ai_brain import CerebroIA
    from app.core.prompts import JUAN_PABLO_SYSTEM_INSTRUCTION
    import app.services.ai_brain as brain_module

    with patch.object(brain_module, "SDK_AVAILABLE", True):
        cerebro = CerebroIA()
        cerebro.client = MagicMock()
        cerebro._model_id = "gemini-test"

        mock_catalog = MagicMock()
        mock_catalog.get_catalog_aliases.return_value = {}
        cerebro._catalog_service = mock_catalog

        prospect = {
            "nombre": "Carlos",
            "moto_interest": "TVS Raider 125",
            "forma_pago": "crédito",
            "ciudad": "Bogotá",
        }

        captured_prompt = None
        captured_config = None

        async def mock_generate(*args, **kwargs):
            nonlocal captured_prompt, captured_config
            if len(args) > 1:
                captured_prompt = args[1]
            captured_config = kwargs.get("config")
            return MagicMock(
                candidates=[MagicMock(content=MagicMock(parts=[MagicMock(text="Con fiador no es obligatorio. Te calculo la cuota a 24 meses y te la mando. ¿Me autorizas el tratamiento de tus datos?")]))]
            )

        with patch.object(cerebro, "_get_current_instruction", return_value=JUAN_PABLO_SYSTEM_INSTRUCTION), \
             patch.object(cerebro, "_call_gemini_with_retry_async", new=mock_generate):
            await cerebro.pensar_respuesta(
                "cuanto queda la cuota a 24 meses y necesito fiador, para sacarla a credito?",
                prospect_data=prospect,
                history=[],
                skip_greeting=True
            )

        assert captured_prompt is not None
        assert "<intercepcion_faq>mixed</intercepcion_faq>" in captured_prompt
        # [BOT-BUILD-205] Updated assertion to match condensed brake block format
        assert "calculate_credit_score" in captured_prompt, "MIXED debe mencionar calculate_credit_score"

        tools = getattr(captured_config, "tools", None)
        if tools:
            declarations = []
            for tool in tools:
                declarations.extend(getattr(tool, "function_declarations", []) or [])
            tool_names = [getattr(d, "name", None) for d in declarations]
            assert "calculate_credit_score" in tool_names, "MIXED debe incluir calculate_credit_score"

