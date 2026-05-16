import asyncio
import sys
import logging
from google.cloud import firestore
from app.services.ai_brain import CerebroIA
from app.services.catalog_service import catalog_service
from app.core.config_loader import ConfigLoader

logging.basicConfig(level=logging.ERROR, stream=sys.stdout)

async def run_simulation():
    print("🔄 Inicializando base de datos y catálogo...")
    db = firestore.Client(project="tiendalasmotos")
    catalog_service.initialize(db)
    config_loader = ConfigLoader(db)
    
    print("🧠 Inicializando CerebroIA...")
    cerebro = CerebroIA(config_loader, catalog_service)
    
    pregunta = "¿Tienen la Boxer?"
    print(f"\n💬 Simulando pregunta de usuario: '{pregunta}'")
    
    try:
        # CORRECCIÓN: El mensaje se pasa como parámetro posicional directo
        respuesta = await cerebro.pensar_respuesta(
            pregunta,
            context="",
            prospect_data={"name": "Tobias Prueba", "phone": "57000000000"},
            history=[],
            skip_greeting=True
        )
        print("\n========================================")
        print("✅ RESPUESTA GENERADA POR LA IA:")
        print("========================================")
        print(respuesta)
    except Exception as e:
        print("\n❌ FALLO CRÍTICO EN LA INFERENCIA DE LA IA:")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_simulation())
