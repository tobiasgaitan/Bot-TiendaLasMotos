import sys
import os
import asyncio
from unittest.mock import MagicMock, AsyncMock

# Add app directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mocking external dependencies
sys.modules['app.services.notification_service'] = MagicMock()
sys.modules['app.utils.security'] = MagicMock()

async def test_dynamic_injection():
    print("🧪 Verificando Lógica de Inyección Dinámica v6.3.1...")
    
    # Mock Objects
    user_phone = "573001234567"
    response_text = "PHASE_GATE_TRIGGERED: ¿En qué trabajas?"
    
    class MockCatalog:
        def search_items(self, query):
            if "TVS Sport 100" in query:
                return [{"name": "TVS Sport 100", "image_url": "http://tvs_sport_url"}]
            if "RAIDER 125" in query:
                return [{"name": "RAIDER 125 RACING", "image_url": "http://raider_url"}]
            return []

    mock_catalog = MockCatalog()
    
    # Scenarios to test
    scenarios = [
        {"name": "Symmetric Interest (TVS Sport 100)", "prospect": {"moto_interest": "TVS Sport 100"}, "expected_moto": "TVS Sport 100"},
        {"name": "Competitor/Invalid Interest", "prospect": {"moto_interest": "Yamaha FZ"}, "expected_moto": "RAIDER 125 RACING"},
        {"name": "Null Interest", "prospect": {}, "expected_moto": "RAIDER 125 RACING"}
    ]

    for s in scenarios:
        print(f"\n🔹 Escenario: {s['name']}")
        prospect_data = s['prospect']
        
        # Local variables inside _handle_message_background (simplified)
        moto_interest = prospect_data.get("moto_interest")
        moto_to_search = moto_interest if moto_interest else "RAIDER 125"
        
        print(f"   Moto inicial a buscar: {moto_to_search}")
        
        moto_results = mock_catalog.search_items(moto_to_search)
        
        if not moto_results and moto_interest:
            print(f"   🔄 Triggered Fallback for '{moto_interest}'")
            moto_results = mock_catalog.search_items("RAIDER 125")
            
        if moto_results:
            moto = moto_results[0]
            m_name = moto.get("name")
            print(f"   ✅ Resultado final: {m_name}")
            print(f"   ✅ Caption: Mira esta {m_name}")
            
            if m_name != s['expected_moto']:
                print(f"   ❌ ERROR: Se esperaba {s['expected_moto']} pero se obtuvo {m_name}")
            else:
                print("   ✨ OK")
        else:
            print("   ❌ ERROR: No se encontraron resultados")

if __name__ == "__main__":
    asyncio.run(test_dynamic_injection())
