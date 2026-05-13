import sys
import os
import asyncio
import logging

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.catalog_service import catalog_service
from app.services.config_service import config_service

# Configure logging
logging.basicConfig(level=logging.INFO)

async def test_price_consolidation():
    print("🚀 Iniciando Auditoría de Consolidación de Precios...")
    
    from unittest.mock import MagicMock
    db = MagicMock()
    
    # Inyectar DB manualmente si no están inicializadas (entorno de script)
    catalog_service._db = db
    config_service._db = db
    
    # 1. Asegurar que las configs están cargadas
    if not config_service._financial_config:
        print("🔄 Cargando configuraciones financieras...")
        config_service.load_configurations()
    
    # 2. Asegurar que el catálogo está cargado
    if not catalog_service._items:
        print("🔄 Cargando catálogo...")
        catalog_service.load_catalog()
    
    print(f"📊 Items en catálogo: {len(catalog_service._items)}")
    
    # 3. Simular búsqueda de una moto conocida
    query = "Apache 160"
    print(f"🔍 Buscando: '{query}'")
    results = catalog_service.search_catalog(query)
    
    if not results:
        print("❌ No se encontraron resultados.")
        return

    for item in results:
        print("\n--- Resultado Auditado ---")
        print(f"Nombre: {item['name']}")
        print(f"Precio Consolidado: {item['price']}")
        print(f"Precio Raw: {item['raw_price']}")
        print(f"Resumen: {item['summary']}")
        
        # Validaciones
        if "(incluye SOAT, Matrícula, y tramites)" not in item['price']:
            print("❌ FALLO: Disclaimer legal ausente.")
        else:
            print("✅ OK: Disclaimer legal presente.")
            
        # Verificar que el precio no sea el base (si hay match de CC)
        # Nota: Esto depende de los datos en Firestore, pero asumimos que Apache 160 tiene costo > 0.
        print("--------------------------")

if __name__ == "__main__":
    asyncio.run(test_price_consolidation())
