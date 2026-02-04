"""
Tienda Las Motos - FastAPI Application
Main application entry point with startup/shutdown lifecycle management.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from google.cloud import firestore

from app.core.config import settings
from app.core.config_loader import ConfigLoader
from app.core.security import get_firebase_credentials_object
from app.services.config_service import config_service
from app.services.catalog_service import catalog_service
from app.services.storage_service import storage_service
from app.routers import whatsapp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("🚀 Starting Tienda Las Motos Backend...")
    
    try:
        # 1. Get Firebase credentials from Secret Manager
        logger.info("🔐 Retrieving credentials from Secret Manager...")
        credentials = get_firebase_credentials_object()
        
        # 2. Initialize Firestore client
        logger.info("🔥 Initializing Firestore client...")
        db = firestore.Client(
            project=settings.gcp_project_id,
            credentials=credentials
        )
        
        # 3. Load configuration into memory
        logger.info("📋 Loading configuration...")
        config_service.initialize(db)
        
        # 4. Load catalog into memory
        logger.info("🏍️  Loading catalog...")
        catalog_service.initialize(db)
        
        # 4.5. Load V6.0 dynamic configuration
        logger.info("🧠 Loading V6.0 dynamic configuration...")
        config_loader = ConfigLoader(db)
        config_loader.load_all()
        
        # Store in app state for access in routes
        app.state.config_loader = config_loader
        app.state.db = db
        
        # 5. Initialize Cloud Storage
        logger.info("☁️  Initializing Cloud Storage...")
        storage_service.initialize(credentials)
        
        logger.info("✅ Application startup complete!")
        logger.info(f"📊 Loaded {len(catalog_service.get_all_items())} catalog items")
        logger.info(f"📦 Storage bucket: {storage_service.get_bucket_name()}")
        logger.info(f"🧠 V6.0 Config: Sebas personality loaded (model: {config_loader.get_sebas_personality().get('model_version')})")
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {str(e)}")
        raise
    
    yield
    
    # Shutdown
    logger.info("👋 Shutting down Tienda Las Motos Backend...")


# Create FastAPI application
app = FastAPI(
    title="Tienda Las Motos - WhatsApp Bot API",
    description="Backend API for motorcycle sales automation via WhatsApp",
    version="1.0.0",
    lifespan=lifespan
)


# Include routers
app.include_router(whatsapp.router)


@app.get("/health")
async def health_check():
    """
    Health check endpoint for Cloud Run.
    
    Returns:
        Status information about the application including V6.0 config status
    """
    # Access config_loader from app state
    config_loader = app.state.config_loader
    
    return {
        "status": "healthy",
        "service": "Tienda Las Motos Backend",
        "version": "6.0.0",
        "catalog_items": len(catalog_service.get_all_items()),
        "storage_bucket": storage_service.get_bucket_name(),
        "v6_config": {
            "sebas_model": config_loader.get_sebas_personality().get("model_version"),
            "routing_keywords_loaded": len(config_loader.get_routing_rules().get("financial_keywords", [])),
            "catalog_config_items": len(config_loader.get_catalog_config().get("items", []))
        }
    }


@app.get("/")
async def root():
    """
    Root endpoint.
    
    Returns:
        Welcome message
    """
    return {
        "message": "Tienda Las Motos - WhatsApp Bot API",
        "version": "6.0.0",
        "docs": "/docs"
    }
