import asyncio
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Asegurar que el path del proyecto esté disponible antes de los imports de tests
sys.path.append(os.getcwd())

# Import tests manually since pytest-asyncio is missing
from tests.test_ai_adapter import (
    test_case_1_large_message_no_anchor,
    test_case_2_short_message_with_anchor,
    test_case_3_raw_text_for_interceptor
)
from tests.test_interceptor_blindaje import (
    test_interceptor_ref_004_fix_verification,
    test_interceptor_true_positive
)

async def run_all_tests():
    print("\n🚀 INICIANDO RUNNER MANUAL DE VALIDACIÓN REF-004/REF-005\n")
    
    # Simulación de Fixtures
    from tests.conftest import mock_prospect_data, cerebro_mock
    
    # Datos de prueba
    data = {
        "exists": True,
        "nombre": "Juan Perez",
        "moto_interest": "TVS APACHE 160",
        "ciudad": "Bogotá"
    }
    
    # Mocking CerebroIA
    with patch('app.services.ai_brain.SDK_AVAILABLE', False):
        from app.services.ai_brain import CerebroIA
        cerebro = CerebroIA()
        # Inyectar atributos requeridos por la lógica interna
        cerebro.client = MagicMock()
        cerebro._model_id = "gemini-2.0-flash"
        cerebro.privacy_policy_url = "https://tiendalasmotos.com/politica-de-privacidad"
        
        # Patching methods to avoid file system/network access
        cerebro._get_current_instruction = MagicMock(return_value="Eres Juan Pablo.")
        
        # Ejecución secuencial
        tests = [
            ("Test Case 1: Large Message", test_case_1_large_message_no_anchor),
            ("Test Case 2: Short Message (Anchor)", test_case_2_short_message_with_anchor),
            ("Test Case 3: Raw Text Interceptor", test_case_3_raw_text_for_interceptor),
            ("Test Case 4: Interceptor Ref-004 Fix", test_interceptor_ref_004_fix_verification),
            ("Test Case 5: Interceptor True Positive", test_interceptor_true_positive)
        ]

        passed = 0
        for name, test_func in tests:
            try:
                print(f"Running {name}...", end=" ")
                await test_func(cerebro, data)
                print("✅ PASSED")
                passed += 1
            except Exception as e:
                print(f"❌ FAILED: {e}")

        print(f"\n📊 RESULTADOS: {passed}/{len(tests)} pruebas pasaron exitosamente.")
        if passed == len(tests):
            sys.exit(0)
        else:
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_all_tests())
