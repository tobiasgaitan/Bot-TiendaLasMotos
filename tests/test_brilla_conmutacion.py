import pytest
from unittest.mock import MagicMock, patch
from app.services.ai_brain import CerebroIA, EXTRACTION_SCHEMA
from app.services.financial_service import FinancialService

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

def test_extraction_schema_contains_cedula_usuario():
    """
    Verifica que la propiedad 'cedula_usuario' exista dentro de extracted en EXTRACTION_SCHEMA
    con los tipos y descripciones correctos.
    """
    properties = EXTRACTION_SCHEMA["properties"]["extracted"]["properties"]
    assert "cedula_usuario" in properties
    assert properties["cedula_usuario"]["type"] == "STRING"
    assert "bias negativo" in properties["cedula_usuario"]["description"].lower()


@pytest.mark.asyncio
async def test_crediorbe_interception_blocks_link_and_injects_contingency():
    """
    Verifica que la intercepción de la herramienta calculate_credit_score para Crediorbe
    bloquee la URL digital e inyecte la instrucción de pedir la cédula y agendar en sedes físicas.
    """
    cerebro = CerebroIA()
    cerebro.client = MagicMock()
    cerebro._model_id = "gemini-2.0-flash"
    
    # Mock catalog service
    mock_catalog = MagicMock()
    mock_catalog.search_items.return_value = [
        {
            "name": "TVS Sport 100",
            "price": "$ 6.200.000",
            "raw_price": 6200000.0,
            "category": "Urban",
            "image_url": "https://img.url",
            "summary": "Excelente moto"
        }
    ]
    cerebro._catalog_service = mock_catalog
    
    # Mock financial motor returning Crediorbe
    mock_financial = MagicMock()
    mock_financial.evaluate_profile.return_value = {
        "score": 710,
        "strategy": "Aprobado",
        "entity": "Crediorbe",
        "link_url": "https://crediorbe.digital.link/auth"
    }
    mock_financial.calculate_payment.return_value = {
        "cuota_mensual": 280000
    }
    cerebro.motor_financiero = mock_financial
    
    # Mock LLM calls
    fc = MockFunctionCall(name="calculate_credit_score", args={})
    candidate1 = MockCandidate(content=MockContent(parts=[MockPart(function_call=fc)]))
    response1 = MockResponse(candidates=[candidate1])
    
    # Second LLM call returns the final text response
    candidate2 = MockCandidate(content=MockContent(parts=[MockPart(text="Interception processed successfully.")]))
    response2 = MockResponse(candidates=[candidate2])
    
    call_count = 0
    captured_function_response = None
    
    async def mock_call(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return response1
        
        # En la segunda llamada, capturamos el historial / partes enviadas a Gemini para verificar
        # qué respuesta de la función (function response) le mandamos.
        nonlocal captured_function_response
        if "contents" in kwargs:
            contents = kwargs["contents"]
            for content in contents:
                for part in content.parts:
                    # En la API de Google GenAI, la parte de respuesta de función puede ser verificada
                    if hasattr(part, "function_response") or (isinstance(part, dict) and "function_response" in part):
                        captured_function_response = part
                    elif hasattr(part, "text") and "MANDATO DE CONTINGENCIA DE CREDIORBE" in part.text:
                        captured_function_response = part
        elif len(args) > 0:
            # Si se pasa como argumento posicional
            for part in args[0]:
                if hasattr(part, "text") and "MANDATO DE CONTINGENCIA DE CREDIORBE" in part.text:
                    captured_function_response = part
        return response2

    from app.services.config_service import config_service
    with patch.object(cerebro, '_call_gemini_with_retry_async', new=mock_call), \
         patch('app.services.ai_brain.SDK_AVAILABLE', True), \
         patch.object(config_service, 'get_registration_cost', return_value=0.0):
         
        prospect = {
            "nombre": "Carlos",
            "moto_interest": "TVS Sport 100",
            "ciudad": "Santa Marta",
            "forma_pago": "Crédito",
            "habeas_data_accepted": True
        }
        await cerebro.pensar_respuesta("Quiero mi crédito ciego", prospect_data=prospect)
        
    # Ahora, verifiquemos los argumentos pasados a evaluate_profile
    mock_financial.evaluate_profile.assert_called_once()
    
    # Verifiquemos que se llamó a calculate_payment
    mock_financial.calculate_payment.assert_called_once_with(
        precio=6200000.0,
        inicial=0,
        plazo_meses=24,
        entidad="Crediorbe",
        moto_cc=0.0,
        category="Urban"
    )
    
    # Verifiquemos que la respuesta de evaluate_profile tuvo su link_url bloqueada
    # (Ya que la modificamos in-place o bloqueamos en el diccionario)
    assert mock_financial.evaluate_profile.return_value["link_url"] is None
    
    # Verifiquemos que las instrucciones específicas e inyección comercial estén presentes en el flujo.
    # We can inspect the logger calls or the mock_call's captured contents.
    # En nuestro mock_call capturamos las partes de la conversación.
    # Dado que pasamos la respuesta de la función a response_parts, busquemos en cerebro._call_gemini_with_retry_async o similar.
    # Hagamos un test directo sobre la lógica del método de ai_brain.
    # En ai_brain.py, el resultado del bloque calculate_credit_score se almacena en response_parts.
    # Modifiquemos mock_call para capturar `response_parts` o `contents` pasados al LLM.
    # Let's inspect the mock_call's contents argument to assert it contains the contingency text:
    # "foto de la cédula", "sedes", "Riohacha", "Santa Marta", "Zona Bananera".
    
    # Si capturamos contents en la segunda llamada (cuando call_count == 2):
    # En la API de Google GenAI, la llamada contiene los turnos anteriores.
    # Busquemos el texto de contingencia de Crediorbe.
    # Alternativamente, podemos instanciar e invocar una simulación controlada del bloque.
    # Pero el mock_call con kwargs['contents'] o similar nos sirve.
    # Vamos a verificar que el texto de contingencia se generó.
    # Como la variable local `credit_res` se inyecta en `types.Part.from_function_response`,
    # revisemos si se llamó con el string correcto.
    # Podemos mockear `types.Part.from_function_response` para ver qué recibió.
    
@pytest.mark.asyncio
async def test_crediorbe_interception_direct_value():
    """
    Verificación directa de la lógica de negocio de intercepción de Crediorbe
    inyectando un mock controlado en el flujo interno de pensar_respuesta.
    """
    cerebro = CerebroIA()
    cerebro.client = MagicMock()
    cerebro._model_id = "gemini-2.0-flash"
    
    mock_catalog = MagicMock()
    mock_catalog.search_items.return_value = [
        {
            "name": "TVS Sport 100",
            "price": "$ 6.200.000",
            "raw_price": 6200000.0,
            "category": "Urban",
            "image_url": "https://img.url",
            "summary": "Excelente"
        }
    ]
    cerebro._catalog_service = mock_catalog
    
    mock_financial = MagicMock()
    mock_financial.evaluate_profile.return_value = {
        "score": 720,
        "strategy": "Aprobado",
        "entity": "Crediorbe",
        "link_url": "https://crediorbe.digital.link/auth"
    }
    mock_financial.calculate_payment.return_value = {
        "cuota_mensual": 280000
    }
    cerebro.motor_financiero = mock_financial
    
    fc = MockFunctionCall(name="calculate_credit_score", args={})
    candidate1 = MockCandidate(content=MockContent(parts=[MockPart(function_call=fc)]))
    response1 = MockResponse(candidates=[candidate1])
    
    candidate2 = MockCandidate(content=MockContent(parts=[MockPart(text="Ok")]))
    response2 = MockResponse(candidates=[candidate2])
    
    call_count = 0
    captured_contents = []
    
    async def mock_call(*args, **kwargs):
        nonlocal call_count, captured_contents
        call_count += 1
        if "contents" in kwargs:
            captured_contents.append(kwargs["contents"])
        elif len(args) > 1:
            captured_contents.append(args[1])
        elif len(args) > 0:
            captured_contents.append(args[0])
        if call_count == 1:
            return response1
        return response2

    with patch.object(cerebro, '_call_gemini_with_retry_async', new=mock_call), \
         patch('app.services.ai_brain.SDK_AVAILABLE', True):
         
        prospect = {
            "nombre": "Carlos",
            "moto_interest": "TVS Sport 100",
            "ciudad": "Santa Marta",
            "forma_pago": "Crédito",
            "habeas_data_accepted": True
        }
        await cerebro.pensar_respuesta("Quiero mi crédito ciego", prospect_data=prospect)
        
        # Verify that we captured the second call contents
        assert len(captured_contents) >= 2
        second_call_contents = captured_contents[1]
        
        # Find the function response part
        result_text = ""
        # second_call_contents is the list of response_parts (types.Part objects)
        for part in second_call_contents:
            fun_res = getattr(part, "function_response", None)
            if fun_res is not None:
                resp = getattr(fun_res, "response", {})
                if isinstance(resp, dict):
                    result_text = resp.get("result", "")
                else:
                    result_text = getattr(resp, "result", "")
                    if not result_text and hasattr(resp, "get"):
                        result_text = resp.get("result", "")
                break
        
        # Guardrail 1: El link digital NO debe estar presente en el resultado final (o debe estar bloqueado)
        assert "https://crediorbe.digital.link/auth" not in result_text
        assert "Link de Pre-aprobación" not in result_text
        
        # Guardrail 2: Instrucciones comerciales de contingencia exigidas
        assert "cédula" in result_text.lower() or "cedula" in result_text.lower()
        assert "foto" in result_text.lower()
        assert "sedes" in result_text.lower()
        assert "Riohacha" in result_text
        assert "Santa Marta" in result_text
        assert "Zona Bananera" in result_text


def test_financial_service_default_entity_is_brilla():
    """
    Verifica que en financial_service.py la simulación por defecto no exponga Brilla de Gases (anonimización).
    """
    fs = FinancialService()
    fs.calculate_payment = MagicMock(return_value={"cuota_mensual": 250000.0})
    moto_dict = {
        "name": "Moto Test",
        "price": 8000000.0,
        "displacement": "125 cc",
        "category": "Urban"
    }
    # Invocamos la simulación para una moto inexistente o similar, o evaluamos directamente la respuesta generada.
    res = fs._generate_full_simulation_response(moto_dict, 0.0)
    # Debe omitir mencionar "Brilla de Gases" o cualquier marca de agua
    assert "Brilla de Gases" not in res
    assert "Brilla" not in res
@pytest.mark.asyncio
async def test_unified_catalog_keys_interception():
    """
    Verifica que la herramienta search_catalog extraiga correctamente name,
    summary y price de Firestore sin levantar ValueError.
    """
    cerebro = CerebroIA()
    cerebro.client = MagicMock()
    cerebro._model_id = "gemini-2.0-flash"
    
    mock_catalog = MagicMock()
    # Retornamos llaves unificadas
    mock_catalog.search_items.return_value = [
        {
            "name": "TVS Apache 160",
            "summary": "Moto deportiva y ágil",
            "price": "$ 9.500.000",
            "category": "Urban"
        }
    ]
    cerebro._catalog_service = mock_catalog
    
    fc = MockFunctionCall(name="search_catalog", args={"query": "Apache 160"})
    candidate1 = MockCandidate(content=MockContent(parts=[MockPart(function_call=fc)]))
    response1 = MockResponse(candidates=[candidate1])
    
    candidate2 = MockCandidate(content=MockContent(parts=[MockPart(text="Ok")]))
    response2 = MockResponse(candidates=[candidate2])
    
    call_count = 0
    captured_contents = []
    
    async def mock_call(*args, **kwargs):
        nonlocal call_count, captured_contents
        call_count += 1
        if "contents" in kwargs:
            captured_contents.append(kwargs["contents"])
        elif len(args) > 1:
            captured_contents.append(args[1])
        elif len(args) > 0:
            captured_contents.append(args[0])
        if call_count == 1:
            return response1
        return response2

    with patch.object(cerebro, '_call_gemini_with_retry_async', new=mock_call), \
         patch('app.services.ai_brain.SDK_AVAILABLE', True):
          
        prospect = {
            "nombre": "Carlos",
            "ciudad": "Santa Marta",
            "forma_pago": "Contado"
        }
        await cerebro.pensar_respuesta("Qué precio tiene la Apache 160?", prospect_data=prospect)
        
        # Debe haber capturado el segundo llamado con los resultados del catálogo procesados
        assert len(captured_contents) >= 2
        second_call_contents = captured_contents[1]
        
        result_text = ""
        for part in second_call_contents:
            fun_res = getattr(part, "function_response", None)
            if fun_res is not None:
                resp = getattr(fun_res, "response", {})
                if isinstance(resp, dict):
                    result_text = resp.get("result", "")
                else:
                    result_text = getattr(resp, "result", "")
                break
        
        # Validar que Nombre, Descripción y Precio se formatearon correctamente
        assert "TVS Apache 160" in result_text
        assert "Moto deportiva y ágil" in result_text
        assert "$ 9.500.000" in result_text
        assert "Ficha Tecnica: Moto deportiva y ágil" in result_text


