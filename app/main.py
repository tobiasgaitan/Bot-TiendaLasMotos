"""
Tienda Las Motos - FastAPI Application
Main application entry point with startup/shutdown lifecycle management.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import firestore

from app.core.config import settings
from app.core.config_loader import ConfigLoader
from app.core.security import get_firebase_credentials_object
from app.services.config_service import config_service
from app.services.config_loader import ConfigLoader as FinanceConfigLoader
from app.services.catalog_service import catalog_service
from app.services.storage_service import storage_service
from app.services.memory_service import init_memory_service
from app.routers import whatsapp, admin

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
    logger.info("🚀 Starting Auteco Las Motos Backend...")
    
    try:
        # 1. Get Firebase credentials from Secret Manager
        logger.info("🔐 Retrieving credentials from Secret Manager...")
        credentials = get_firebase_credentials_object()
        
        # 2. Initialize Firestore clients (Dual-Client Adapter v6.9.7)
        logger.info("🔥 Initializing Firestore clients (Dual-Mode)...")
        db = firestore.Client(
            project=settings.gcp_project_id,
            credentials=credentials
        )
        db_async = firestore.AsyncClient(
            project=settings.gcp_project_id,
            credentials=credentials
        )
        
        # 3. Load configurations and services
        logger.info("⚡ Initializing config loader singleton...")
        config_loader = ConfigLoader(db)
        
        import concurrent.futures
        logger.info("⚡ Loading configurations in parallel (Stage 1)...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_config = executor.submit(config_service.initialize, db)
            future_loader = executor.submit(config_loader.load_all)
            concurrent.futures.wait([future_config, future_loader])
            
            # Propagate exceptions if any occurred during loading
            future_config.result()
            future_loader.result()
            
        # 4. Servicios dependientes (🏍️ Catalog)
        logger.info("🏍️  Loading catalog service...")
        catalog_service.initialize(db)
        
        # 4.6 Load Financial Config (Fase 1)
        logger.info("💰 Loading Financial Configuration...")
        finance_config_loader = FinanceConfigLoader(db)
        
        # Store in app state for access in routes
        app.state.config_loader = config_loader
        app.state.finance_config_loader = finance_config_loader
        app.state.db = db
        app.state.db_async = db_async
        
        # 5. Initialize Cloud Storage
        logger.info("☁️  Initializing Cloud Storage...")
        storage_service.initialize(credentials)
        
        # 6. Initialize Memory Service for CRM Integration (ASYNC ONLY)
        logger.info("🧠 Initializing Memory Service (Async)...")
        try:
            init_memory_service(db_async)
            logger.info("✅ Memory Service initialized successfully with AsyncClient")
        except Exception as mem_error:
            logger.error(f"❌ Failed to initialize Memory Service: {str(mem_error)}", exc_info=True)
            logger.warning("⚠️  Bot will continue without CRM memory integration")
        
        
        logger.info("✅ Application startup complete!")
        # logger.info(f"📊 Loaded {len(catalog_service.get_all_items())} catalog items")
        logger.info(f"🧠 V6.0 Config: {config_loader.get_juan_pablo_personality().get('name')} personality loaded (model: {config_loader.get_juan_pablo_personality().get('model_version')})")
        logger.info("🚀 STARTUP CHECK: v10.8.0 - API Boundary Protection")
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {str(e)}")
        import os
        if os.getenv("TEST_MODE") == "true":
            logger.warning("🧪 TEST_MODE: Ignoring startup failure to allow mock integration testing")
            from unittest.mock import MagicMock
            class DummyConfigLoader:
                def get_juan_pablo_personality(self): return {"name": "Juan Pablo Mock", "model_version": "gemini-2.0-flash"}
                def get_routing_rules(self): return {"financial_keywords": []}
                def get_catalog_config(self): return {"items": []}
            class DummyFinanceConfigLoader:
                pass
            app.state.config_loader = DummyConfigLoader()
            app.state.finance_config_loader = DummyFinanceConfigLoader()
            app.state.db = MagicMock()
            app.state.db_async = MagicMock()
        else:
            raise
    
    yield
    
    # Shutdown
    logger.info("👋 Shutting down Auteco Las Motos Backend...")
    from app.services.memory_service import memory_service
    if memory_service:
        await memory_service.shutdown()
    else:
        logger.warning("⚠️ MemoryService not initialized, skipping shutdown flush.")


# Create FastAPI application
app = FastAPI(
    title="Auteco Las Motos - WhatsApp Bot API",
    description="Backend API for motorcycle sales automation via WhatsApp",
    version="1.0.0",
    lifespan=lifespan
)


# ============================================================================
# CORS CONFIGURATION (BOT-FIX-902)
# ============================================================================
# Explicit origin whitelist for Admin Panel and local development.
# WHY NOT "*": CORS spec prohibits wildcard origins with allow_credentials=True.
# Using "*" with credentials causes browsers to block the response with 403.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://tiendalasmotos-beta.web.app",
        "https://tiendalasmotos.com",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# ROUTER INCLUSION
# ============================================================================
# Include routers
app.include_router(whatsapp.router)
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])


@app.get("/health")
async def health_check():
    """
    Health check endpoint for Cloud Run.
    
    Returns:
        Status information about the application including V6.0 config status
    """
    # Access config_loader from app state safely without raising AttributeError
    config_loader = getattr(app.state, "config_loader", None)
    
    v6_config = None
    if config_loader is not None:
        try:
            v6_config = {
                "juan_pablo_model": config_loader.get_juan_pablo_personality().get("model_version"),
                "routing_keywords_loaded": len(config_loader.get_routing_rules().get("financial_keywords", [])),
                "catalog_config_items": len(config_loader.get_catalog_config().get("items", []))
            }
        except Exception as e:
            logger.exception("❌ Error retrieving v6_config from config_loader in health check: %s", e)
    else:
        logger.warning("⚠️ app.state.config_loader is not initialized yet in health_check")

    catalog_items_count = 0
    try:
        catalog_items_count = len(catalog_service.get_all_items())
    except Exception as e:
        logger.exception("❌ Error retrieving catalog items in health check: %s", e)

    storage_bucket_name = None
    try:
        storage_bucket_name = storage_service.get_bucket_name()
    except Exception as e:
        logger.exception("❌ Error retrieving storage bucket name in health check: %s", e)

    return {
        "status": "healthy",
        "service": "Auteco Las Motos Backend",
        "version": "6.0.0",
        "catalog_items": catalog_items_count,
        "storage_bucket": storage_bucket_name,
        "v6_config": v6_config
    }


@app.get("/")
async def root():
    """
    Root endpoint.
    
    Returns:
        Welcome message
    """
    return {
        "message": "Auteco Las Motos - WhatsApp Bot API",
        "version": "6.0.0",
        "docs": "/docs"
    }
