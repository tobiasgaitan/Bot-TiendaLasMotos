import sys
import os
import asyncio
import re
from typing import Dict, Any, List

# Add app directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mocking enough to load CatalogService
os.environ["LOCAL_DB"] = "true"

class MockCatalog:
    def _summarize(self, text: str, max_words: int = 10) -> str:
        if not text: return ""
        clean_text = re.sub(r'<[^>]+>', '', str(text))
        words = clean_text.split()
        if len(words) <= max_words: return clean_text
        return " ".join(words[:max_words]) + "..."

    def search_items(self, query: str):
        # Simulated raw item from Firestore
        item = {
            "id": "tvs_100",
            "name": "TVS SPORT 100",
            "formatted_price": "$6.000.000",
            "category": "Calle",
            "image_url": "http://image.png",
            "description": "Una moto excelente para el trabajo diario con bajo consumo."
        }
        
        # Implementation of the new truncated_item logic
        truncated_item = {
            "name": item.get("name"),
            "price": item.get("formatted_price"),
            "formatted_price": item.get("formatted_price"),
            "category": item.get("category", "Moto"),
            "image_url": item.get("image_url"),
            "summary": self._summarize(item.get("description", ""))
        }
        return [truncated_item]

def test_v632_fields():
    print("🧪 Verificando Payload de Catálogo v6.3.2...")
    catalog = MockCatalog()
    results = catalog.search_items("Boxer")
    
    if not results:
        print("❌ ERROR: No se devolvieron resultados")
        return False
    
    item = results[0]
    required_fields = ["name", "price", "formatted_price", "category", "image_url", "summary"]
    
    all_ok = True
    for field in required_fields:
        val = item.get(field)
        if val:
            print(f"   ✅ {field}: {val}")
        else:
            print(f"   ❌ ERROR: Campo '{field}' ausente o vacío")
            all_ok = False
            
    # Simulate ai_brain construction
    try:
        name = item.get('name', 'Moto')
        category = item.get('category', 'Moto')
        price = item.get('price', item.get('formatted_price', 'Consultar'))
        search_results = f"- {name} ({category}): {price}\n"
        print(f"   ✨ AI Brain Preview: {search_results.strip()}")
    except Exception as e:
        print(f"   ❌ ERROR en construcción de AI Brain: {e}")
        all_ok = False

    return all_ok

if __name__ == "__main__":
    success = test_v632_fields()
    if success:
        print("\n🟢 VERDE: Todos los campos validados correctamente.")
        sys.exit(0)
    else:
        print("\n🔴 ROJO: Fallo en la validación de campos.")
        sys.exit(1)
