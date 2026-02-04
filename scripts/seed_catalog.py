#!/usr/bin/env python3
"""
Catalog Seeding Script for Tienda Las Motos
Seeds the catalog_items collection in Firestore with motorcycle data.

Usage:
    python3 scripts/seed_catalog.py

Requirements:
    - firebase-admin installed
    - Application Default Credentials configured (gcloud auth application-default login)
    - Or running in Cloud Shell with appropriate permissions
"""

import sys
import os
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import firebase_admin
from firebase_admin import credentials, firestore


def initialize_firebase():
    """Initialize Firebase Admin SDK with Application Default Credentials."""
    try:
        # Use Application Default Credentials (works in Cloud Shell and local with gcloud auth)
        firebase_admin.initialize_app(credentials.ApplicationDefault(), {
            'projectId': 'tiendalasmotos',
        })
        print("✅ Firebase Admin initialized successfully")
        return firestore.client()
    except Exception as e:
        print(f"❌ Error initializing Firebase: {str(e)}")
        sys.exit(1)


def seed_catalog(db):
    """
    Seed the catalog_items collection with motorcycle data.
    
    Args:
        db: Firestore client instance
    """
    print("\n" + "=" * 60)
    print("🏍️  SEEDING MOTORCYCLE CATALOG")
    print("=" * 60)
    
    # Define the 4 main motorcycles
    motorcycles = [
        {
            "id": "nkd-125",
            "name": "NKD 125",
            "category": "urbana",
            "description": "Moto urbana económica, ideal para la ciudad y el trabajo diario",
            "highlights": [
                "Bajo consumo de combustible",
                "Perfecta para tráfico urbano",
                "Mantenimiento económico",
                "Diseño moderno y compacto"
            ],
            "price": 4500000,  # COP
            "engine": "125cc",
            "fuel_efficiency": "45 km/l",
            "active": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        },
        {
            "id": "sport-100",
            "name": "Sport 100",
            "category": "deportiva",
            "description": "Moto deportiva de entrada, perfecta para jóvenes que buscan estilo y velocidad",
            "highlights": [
                "Diseño deportivo agresivo",
                "Ideal para jóvenes",
                "Excelente relación precio-rendimiento",
                "Ágil y rápida en ciudad"
            ],
            "price": 5200000,  # COP
            "engine": "100cc",
            "fuel_efficiency": "40 km/l",
            "active": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        },
        {
            "id": "victory-black",
            "name": "Victory Black",
            "category": "ejecutiva",
            "description": "Moto ejecutiva elegante y potente, diseñada para profesionales exigentes",
            "highlights": [
                "Diseño elegante y sofisticado",
                "Motor potente y confiable",
                "Confort superior",
                "Tecnología avanzada"
            ],
            "price": 8500000,  # COP
            "engine": "200cc",
            "fuel_efficiency": "35 km/l",
            "active": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        },
        {
            "id": "mrx-150",
            "name": "MRX 150",
            "category": "todo-terreno",
            "description": "Moto aventurera todo terreno, resistente y versátil para cualquier camino",
            "highlights": [
                "Suspensión reforzada",
                "Perfecta para aventuras",
                "Resistente y durable",
                "Versatilidad campo-ciudad"
            ],
            "price": 7200000,  # COP
            "engine": "150cc",
            "fuel_efficiency": "38 km/l",
            "active": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
    ]
    
    # Seed each motorcycle
    collection_ref = db.collection("catalog_items")
    
    for moto in motorcycles:
        try:
            doc_id = moto["id"]
            doc_ref = collection_ref.document(doc_id)
            
            # Upsert (set with merge to update if exists)
            doc_ref.set(moto, merge=True)
            
            print(f"✅ Seeded: {moto['name']} ({moto['category']})")
            print(f"   Price: ${moto['price']:,} COP")
            print(f"   Engine: {moto['engine']}")
            print()
            
        except Exception as e:
            print(f"❌ Error seeding {moto['name']}: {str(e)}")
    
    print("=" * 60)
    print(f"✅ Catalog seeding complete! {len(motorcycles)} motorcycles added.")
    print("=" * 60)


def verify_catalog(db):
    """
    Verify the catalog was seeded correctly.
    
    Args:
        db: Firestore client instance
    """
    print("\n" + "=" * 60)
    print("🔍 VERIFYING CATALOG")
    print("=" * 60)
    
    collection_ref = db.collection("catalog_items")
    docs = collection_ref.stream()
    
    count = 0
    for doc in docs:
        data = doc.to_dict()
        print(f"✅ {doc.id}: {data.get('name')} - {data.get('category')}")
        count += 1
    
    print("=" * 60)
    print(f"Total motorcycles in catalog: {count}")
    print("=" * 60)


def main():
    """Main execution function."""
    print("\n🚀 Starting Catalog Seeding Script...")
    print(f"Project: tiendalasmotos")
    print(f"Collection: catalog_items")
    
    # Initialize Firebase
    db = initialize_firebase()
    
    # Seed catalog
    seed_catalog(db)
    
    # Verify catalog
    verify_catalog(db)
    
    print("\n✅ Script completed successfully!")


if __name__ == "__main__":
    main()
