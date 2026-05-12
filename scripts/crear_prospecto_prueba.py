#!/usr/bin/env python3
"""
Prospect Seeding Script - Create Test Prospects in Firestore
Creates prospect documents in the 'prospectos' collection for testing CRM integration.

Usage:
    python scripts/crear_prospecto_prueba.py --celular 3227303760 --nombre "Carlos" --moto "Viva R"
    python scripts/crear_prospecto_prueba.py  # Interactive mode
"""

import sys
import os
import argparse
import logging
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from google.cloud import firestore
from app.core.security import get_firebase_credentials_object
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_prospect(
    db: firestore.Client,
    celular: str,
    nombre: str,
    moto_interest: str,
    ai_summary: str = None,
    chatbot_status: str = "PENDING",
    merge: bool = True
) -> None:
    """
    Create or update a prospect in Firestore.
    
    Args:
        db: Firestore client instance
        celular: Phone number (without country code, e.g., "3227303760")
        nombre: Prospect name
        moto_interest: Motorcycle of interest
        ai_summary: Optional conversation summary
        chatbot_status: Status (PENDING or ACTIVE)
        merge: If True, merge with existing data; if False, overwrite
    """
    try:
        # Clean phone number (remove any +57 or spaces)
        clean_celular = celular.replace("+", "").replace("57", "", 1).replace(" ", "")
        
        logger.info(f"🔍 Checking if prospect exists: {clean_celular}")
        
        # Check if prospect already exists
        prospectos_ref = db.collection("prospectos")
        query = prospectos_ref.where("celular", "==", clean_celular).limit(1)
        existing_docs = query.get()
        
        if existing_docs:
            doc_ref = existing_docs[0].reference
            existing_data = existing_docs[0].to_dict()
            logger.warning(f"⚠️  Prospect already exists: {existing_data.get('nombre')}")
            
            if not merge:
                logger.error("❌ Prospect exists and merge=False. Aborting.")
                return
            
            logger.info("🔄 Updating existing prospect with merge=True")
        else:
            # Create new document with auto-generated ID
            doc_ref = prospectos_ref.document()
            logger.info(f"✨ Creating new prospect document")
        
        # Prepare prospect data
        prospect_data = {
            "celular": clean_celular,
            "nombre": nombre,
            "moto_interest": moto_interest,
            "origen": "SCRIPT",
            "chatbot_status": chatbot_status,
            "updated_at": firestore.SERVER_TIMESTAMP
        }
        
        # Add optional fields
        if ai_summary:
            prospect_data["ai_summary"] = ai_summary
        
        # Add created_at only for new documents
        if not existing_docs:
            prospect_data["created_at"] = firestore.SERVER_TIMESTAMP
        
        # Write to Firestore
        doc_ref.set(prospect_data, merge=merge)
        
        logger.info("✅ Prospect created/updated successfully!")
        logger.info(f"📋 Details:")
        logger.info(f"   - Celular: {clean_celular}")
        logger.info(f"   - Nombre: {nombre}")
        logger.info(f"   - moto_interest: {moto_interest}")
        logger.info(f"   - Chatbot Status: {chatbot_status}")
        logger.info(f"   - AI Summary: {ai_summary or '(empty)'}")
        logger.info(f"   - Document ID: {doc_ref.id}")
        
    except Exception as e:
        logger.error(f"❌ Error creating prospect: {str(e)}", exc_info=True)
        raise


def interactive_mode(db: firestore.Client) -> None:
    """
    Interactive mode - prompt user for prospect details.
    
    Args:
        db: Firestore client instance
    """
    print("\n" + "="*60)
    print("🏍️  CREAR PROSPECTO DE PRUEBA - Modo Interactivo")
    print("="*60 + "\n")
    
    # Get prospect details
    celular = input("📱 Celular (ej: 3227303760): ").strip()
    nombre = input("👤 Nombre (ej: Carlos): ").strip()
    moto_interest = input("🏍️  Moto de Interés (ej: Viva R): ").strip()
    
    # Optional fields
    ai_summary_input = input("📝 Resumen AI (opcional, Enter para omitir): ").strip()
    ai_summary = ai_summary_input if ai_summary_input else None
    
    chatbot_status = input("🤖 Chatbot Status (PENDING/ACTIVE) [PENDING]: ").strip().upper()
    if chatbot_status not in ["PENDING", "ACTIVE"]:
        chatbot_status = "PENDING"
    
    # Confirmation
    print("\n" + "-"*60)
    print("📋 Resumen:")
    print(f"   Celular: {celular}")
    print(f"   Nombre: {nombre}")
    print(f"   Moto: {moto_interest}")
    print(f"   Status: {chatbot_status}")
    print(f"   Summary: {ai_summary or '(vacío)'}")
    print("-"*60)
    
    confirm = input("\n¿Crear este prospecto? (s/n): ").strip().lower()
    
    if confirm == 's':
        create_prospect(db, celular, nombre, moto_interest, ai_summary, chatbot_status)
    else:
        logger.info("❌ Operación cancelada por el usuario")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Crear prospecto de prueba en Firestore",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Modo interactivo
  python scripts/crear_prospecto_prueba.py
  
  # Modo CLI con argumentos
  python scripts/crear_prospecto_prueba.py --celular 3227303760 --nombre "Carlos" --moto "Viva R"
  
  # Con resumen AI
  python scripts/crear_prospecto_prueba.py --celular 3001234567 --nombre "Juan" --moto "NKD 125" --summary "Cliente interesado en financiación"
  
  # Con status ACTIVE
  python scripts/crear_prospecto_prueba.py --celular 3227303760 --nombre "Carlos" --moto "Viva R" --status ACTIVE
        """
    )
    
    parser.add_argument(
        "--celular",
        type=str,
        help="Número de celular (ej: 3227303760)"
    )
    parser.add_argument(
        "--nombre",
        type=str,
        help="Nombre del prospecto (ej: Carlos)"
    )
    parser.add_argument(
        "--moto",
        type=str,
        help="Moto de interés (ej: Viva R, NKD 125)"
    )
    parser.add_argument(
        "--summary",
        type=str,
        default=None,
        help="Resumen de conversación AI (opcional)"
    )
    parser.add_argument(
        "--status",
        type=str,
        choices=["PENDING", "ACTIVE"],
        default="PENDING",
        help="Estado del chatbot (default: PENDING)"
    )
    parser.add_argument(
        "--no-merge",
        action="store_true",
        help="No fusionar con datos existentes (sobrescribir)"
    )
    
    args = parser.parse_args()
    
    try:
        # Initialize Firestore
        logger.info("🔐 Retrieving Firebase credentials...")
        credentials = get_firebase_credentials_object()
        
        logger.info("🔥 Initializing Firestore client...")
        db = firestore.Client(
            project=settings.gcp_project_id,
            credentials=credentials
        )
        
        # Check if CLI mode or interactive mode
        if args.celular and args.nombre and args.moto:
            # CLI mode
            logger.info("🚀 Modo CLI - Creando prospecto...")
            create_prospect(
                db,
                celular=args.celular,
                nombre=args.nombre,
                moto_interest=args.moto,
                ai_summary=args.summary,
                chatbot_status=args.status,
                merge=not args.no_merge
            )
        else:
            # Interactive mode
            if args.celular or args.nombre or args.moto:
                logger.warning("⚠️  Argumentos incompletos. Usando modo interactivo.")
            interactive_mode(db)
        
        logger.info("\n✅ Script completado exitosamente!")
        
    except Exception as e:
        logger.error(f"\n❌ Error fatal: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
