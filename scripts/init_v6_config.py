#!/usr/bin/env python3
"""
V6.0 Configuration Initialization Script

This script populates Firestore with the initial V6.0 configuration documents.
Run this ONCE from Cloud Shell or locally with proper credentials.

Usage:
    python scripts/init_v6_config.py
"""

import sys
from datetime import datetime
from google.cloud import firestore


def init_sebas_personality(db: firestore.Client) -> None:
    """
    Initialize Sebas AI personality configuration.
    
    Creates configuracion/sebas_personality document with:
    - Personality traits and tone
    - System instruction prompt
    - Model version
    - Catalog knowledge base
    """
    print("📝 Initializing Sebas personality configuration...")
    
    personality_config = {
        "name": "Sebas",
        "role": "Vendedor paisa experto de Tienda Las Motos",
        "tone": "amable, profesional y orientado a resultados",
        "model_version": "gemini-2.0-flash",
        "system_instruction": """
Eres 'Sebas', vendedor paisa experto de Tienda Las Motos.

IDENTIDAD:
- Nombre: Sebas
- Rol: Asesor comercial especializado en motocicletas
- Personalidad: Amable, profesional, conocedor del producto
- Objetivo: Ayudar al cliente a encontrar su moto ideal y cerrar la venta

CONOCIMIENTO DEL CATÁLOGO:
Tienes acceso a nuestro catálogo completo de motocicletas:
- NKD 125: Moto urbana, ideal para ciudad, económica
- Sport 100: Deportiva de entrada, perfecta para jóvenes
- Victory Black: Elegante y potente, para ejecutivos
- MRX 150: Todo terreno, aventurera

REGLAS DE CONVERSACIÓN:
1. Tono amable pero directo - no chatear por chatear
2. Siempre orientar hacia la venta o simulación de crédito
3. Si preguntan por precio, ofrecer simulación inmediata
4. Mencionar beneficios clave: financiación flexible, garantía, servicio técnico
5. Cerrar cada mensaje con llamado a la acción claro

FLUJO DE VENTA:
1. Identificar necesidad del cliente
2. Recomendar moto específica del catálogo
3. Ofrecer simulación de crédito
4. Agendar visita a sede o cerrar venta

NO HACER:
- No inventar información técnica que no conoces
- No prometer descuentos sin autorización
- No desviar la conversación a temas no relacionados con motos
- No ser insistente si el cliente no está interesado

EJEMPLO DE RESPUESTA:
"¡Hola! Soy Sebas de Tienda Las Motos 🏍️. La NKD 125 es perfecta para ciudad, 
consume muy poco y la puedes financiar desde $15.000/día. ¿Te gustaría que te 
haga una simulación personalizada con tu inicial?"
        """.strip(),
        "catalog_knowledge": [
            {
                "name": "NKD 125",
                "type": "Urbana",
                "highlights": "Económica, ideal ciudad, bajo consumo"
            },
            {
                "name": "Sport 100",
                "type": "Deportiva",
                "highlights": "Deportiva de entrada, perfecta para jóvenes"
            },
            {
                "name": "Victory Black",
                "type": "Ejecutiva",
                "highlights": "Elegante, potente, para ejecutivos"
            },
            {
                "name": "MRX 150",
                "type": "Todo Terreno",
                "highlights": "Aventurera, resistente, versátil"
            }
        ],
        "created_at": datetime.now(),
        "version": "6.0.0"
    }
    
    doc_ref = db.collection("configuracion").document("sebas_personality")
    doc_ref.set(personality_config)
    
    print("✅ Sebas personality configuration created")


def init_routing_rules(db: firestore.Client) -> None:
    """
    Initialize message routing rules.
    
    Creates configuracion/routing_rules document with:
    - Financial keywords (route to MotorFinanciero)
    - Sales keywords (route to MotorVentas)
    - Default handler configuration
    """
    print("📝 Initializing routing rules...")
    
    routing_config = {
        "financial_keywords": [
            "simular",
            "simulación",
            "simulacion",
            "cuota",
            "cuotas",
            "crédito",
            "credito",
            "financiar",
            "financiación",
            "financiacion",
            "inicial",
            "mensual",
            "plazo",
            "interés",
            "interes",
            "banco",
            "prestamo",
            "préstamo"
        ],
        "sales_keywords": [
            "precio",
            "precios",
            "busco",
            "nkd",
            "sport",
            "victory",
            "mrx",
            "comprar",
            "vender",
            "disponible",
            "disponibilidad",
            "catálogo",
            "catalogo",
            "motos",
            "moto",
            "modelo",
            "modelos",
            "características",
            "caracteristicas",
            "especificaciones"
        ],
        "default_handler": "cerebro_ia",
        "routing_priority": [
            "financial",  # Check financial keywords first
            "sales",      # Then sales keywords
            "default"     # Finally default to Sebas (CerebroIA)
        ],
        "created_at": datetime.now(),
        "version": "6.0.0"
    }
    
    doc_ref = db.collection("configuracion").document("routing_rules")
    doc_ref.set(routing_config)
    
    print("✅ Routing rules configuration created")


def init_financial_config(db: firestore.Client) -> None:
    """
    Initialize financial configuration.
    
    Creates configuracion/financiera document with:
    - Bank interest rates (Banco de Bogotá)
    - Fintech interest rates (CrediOrbe)
    - Credit scoring thresholds
    - Payment calculation parameters
    """
    print("📝 Initializing financial configuration...")
    
    financial_config = {
        "tasas": {
            "banco": {
                "nombre": "Banco de Bogotá",
                "tasa_mensual": 1.87,
                "tasa_anual": 22.44,
                "descripcion": "Tasa preferencial para perfiles bancarios (score >= 750)"
            },
            "fintech": {
                "nombre": "CrediOrbe",
                "tasa_mensual": 2.20,
                "tasa_anual": 26.40,
                "descripcion": "Tasa flexible para perfiles intermedios (500-749)"
            },
            "brilla": {
                "nombre": "Crédito Brilla",
                "tasa_mensual": 1.95,
                "tasa_anual": 23.40,
                "descripcion": "Opción alternativa para usuarios con servicio de gas natural"
            }
        },
        "perfilamiento": {
            "umbral_bancario": 750,
            "umbral_fintech": 500,
            "umbral_rechazo": 499,
            "pesos": {
                "riesgo_laboral": 0.3,
                "habito_pago": 0.4,
                "capacidad_endeudamiento": 0.2,
                "validacion_identidad": 0.1
            }
        },
        "parametros_calculo": {
            "plazo_minimo_meses": 12,
            "plazo_maximo_meses": 48,
            "inicial_minimo_porcentaje": 10,
            "inicial_recomendado_porcentaje": 20,
            "ratio_endeudamiento_maximo": 0.40,
            "ratio_endeudamiento_optimo": 0.30
        },
        "costos_adicionales": {
            "seguro_vida_mensual": 15000,
            "seguro_todo_riesgo_mensual": 45000,
            "matricula_base": 350000,
            "tramites_base": 250000
        },
        "created_at": datetime.now(),
        "version": "6.0.0",
        "last_updated": datetime.now()
    }
    
    doc_ref = db.collection("configuracion").document("financiera")
    doc_ref.set(financial_config)
    
    print("✅ Financial configuration created")


def init_catalog_config(db: firestore.Client) -> None:
    """
    Initialize catalog configuration.
    
    Creates configuracion/catalog_config document with:
    - Catalog items metadata
    - Sync settings
    - Display preferences
    """
    print("📝 Initializing catalog configuration...")
    
    catalog_config = {
        "items": [
            {
                "id": "nkd-125",
                "name": "NKD 125",
                "category": "urbana",
                "active": True,
                "priority": 1
            },
            {
                "id": "sport-100",
                "name": "Sport 100",
                "category": "deportiva",
                "active": True,
                "priority": 2
            },
            {
                "id": "victory-black",
                "name": "Victory Black",
                "category": "ejecutiva",
                "active": True,
                "priority": 3
            },
            {
                "id": "mrx-150",
                "name": "MRX 150",
                "category": "todo-terreno",
                "active": True,
                "priority": 4
            }
        ],
        "auto_sync_enabled": False,
        "sync_interval_hours": 24,
        "last_updated": datetime.now(),
        "created_at": datetime.now(),
        "version": "6.0.0"
    }
    
    doc_ref = db.collection("configuracion").document("catalog_config")
    doc_ref.set(catalog_config)
    
    print("✅ Catalog configuration created")


def verify_configuration(db: firestore.Client) -> None:
    """
    Verify that all V6.0 configuration documents were created successfully.
    """
    print("\n🔍 Verifying configuration...")
    
    docs_to_check = [
        "sebas_personality",
        "routing_rules",
        "financiera",
        "catalog_config"
    ]
    
    all_exist = True
    
    for doc_name in docs_to_check:
        doc_ref = db.collection("configuracion").document(doc_name)
        doc = doc_ref.get()
        
        if doc.exists:
            print(f"  ✅ {doc_name}: OK")
        else:
            print(f"  ❌ {doc_name}: NOT FOUND")
            all_exist = False
    
    if all_exist:
        print("\n✅ All V6.0 configuration documents created successfully!")
        print("\n📋 Next steps:")
        print("  1. Update main.py to integrate ConfigLoader")
        print("  2. Deploy updated code to Cloud Run")
        print("  3. Test with WhatsApp messages")
    else:
        print("\n❌ Some configuration documents are missing. Please check errors above.")
        sys.exit(1)


def main():
    """Main execution function."""
    print("=" * 60)
    print("V6.0 Configuration Initialization")
    print("Tienda Las Motos - WhatsApp Bot")
    print("=" * 60)
    print()
    
    try:
        # Initialize Firestore client
        print("🔥 Connecting to Firestore...")
        db = firestore.Client(project="tiendalasmotos")
        print("✅ Connected to Firestore\n")
        
        # Initialize all configurations
        init_sebas_personality(db)
        init_routing_rules(db)
        init_financial_config(db)
        init_catalog_config(db)
        
        # Verify everything was created
        verify_configuration(db)
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
