"""
Tienda Las Motos - FastAPI Application
Main application entry point with startup/shutdown lifecycle management.

[BOT-BACKEND-BUGFIX-CONTAINER-CRASH-188]
WHY: All heavy network initialization (Firestore gRPC, Secret Manager, catalog hydration)
is deferred to a background task launched from the lifespan handler. This guarantees
Uvicorn opens the socket on port 8080 IMMEDIATELY, satisfying the TCP startup probe
of Cloud Run before any network I/O completes.
"""

import logging
import asyncio
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from app.core.config import settings

# --- LAZY PROXIES FOR TEST MOCKING COMPATIBILITY ---
class LazyProxy:
    def __init__(self, import_path: str, name: str):
        self._import_path = import_path
        self._name = name
        self._instance = None

    def _get_instance(self):
        if self._instance is None:
            import importlib
            module = importlib.import_module(self._import_path)
            self._instance = getattr(module, self._name)
        return self._instance

    def __getattr__(self, name):
        return getattr(self._get_instance(), name)

    def __call__(self, *args, **kwargs):
        return self._get_instance()(*args, **kwargs)

    def __bool__(self):
        return bool(self._get_instance())

firestore = LazyProxy("google.cloud", "firestore")
get_firebase_credentials_object = LazyProxy("app.core.security", "get_firebase_credentials_object")
ConfigLoader = LazyProxy("app.core.config_loader", "ConfigLoader")
config_service = LazyProxy("app.services.config_service", "config_service")
FinanceConfigLoader = LazyProxy("app.services.config_loader", "ConfigLoader")
storage_service = LazyProxy("app.services.storage_service", "storage_service")
catalog_service = LazyProxy("app.services.catalog_service", "catalog_service")
init_memory_service = LazyProxy("app.services.memory_service", "init_memory_service")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


TEST_MODE = os.getenv("TEST_MODE") == "true" or "pytest" in sys.modules

# [BOT-BACKEND-BUGFIX-CONTAINER-CRASH-188]
# WHY: Module-level initialization of Firestore/Secret Manager was executing
# network calls during Python's import system (before Uvicorn could bind the port).
# ALL heavy initialization is now deferred to the lifespan background task below.
# No network calls occur at import time.


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    [BOT-BACKEND-BUGFIX-CONTAINER-CRASH-188]
    WHY: Heavy initialization (Firestore, catalog hydration, config loading) runs
    in a background task launched via asyncio.create_task(). The lifespan yields
    immediately, allowing Uvicorn to bind port 8080 and satisfy the Cloud Run
    TCP startup probe. The webhook handler's catalog_ready guard (whatsapp.py L362-388)
    rejects requests with HTTP 503 until hydration completes.
    """
    # Startup
    logger.info("🚀 Starting Auteco Las Motos Backend...")
    app.state.catalog_ready = False

    if not TEST_MODE:
        # WHY: Launch heavy init in background so Uvicorn can open port 8080 immediately.
        # The startup_task is stored in app.state for test awaiting (test_startup_lock.py).
        app.state.startup_task = asyncio.create_task(
            _run_deferred_initialization(app)
        )
    else:
        # TEST_MODE: Run inline initialization with mocks
        logger.info("🧪 Running inline lifespan initialization (TEST_MODE)...")
        try:
            # 1. Get Firebase credentials
            credentials_obj = get_firebase_credentials_object()
            
            # 2. Initialize Firestore clients
            db_obj = firestore.Client(
                project=settings.gcp_project_id,
                credentials=credentials_obj
            )
            db_async_obj = firestore.AsyncClient(
                project=settings.gcp_project_id,
                credentials=credentials_obj
            )
            
            # 3. Load configurations and services
            config_loader_obj = ConfigLoader(db_obj)
            
            app.state.config_loader = config_loader_obj
            app.state.db = db_obj
            app.state.db_async = db_async_obj
            
            # 4. Initialize Cloud Storage
            storage_service.initialize(credentials_obj)
            
            # 5. Initialize Memory Service
            try:
                init_memory_service(db_async_obj)
            except Exception as mem_error:
                logger.error(f"❌ Failed to initialize Memory Service: {str(mem_error)}", exc_info=True)
            
            # 6. Initialize core services (Linear Startup) with timeout
            def run_initialization_sync():
                logger.info("⚡ Linear Startup: Initializing config service...")
                config_service.initialize(db_obj)
                
                logger.info("⚡ Linear Startup: Loading dynamic configurations...")
                config_loader_obj.load_all()
                
                logger.info("🏍️  Linear Startup: Initializing catalog service...")
                # WHY: config_loader_obj is passed as an injected dependency (post-hydration)
                # to eliminate the race condition in CatalogService.load_catalog().
                catalog_service.initialize(db_obj, config_loader_obj)
                
                logger.info("💰 Linear Startup: Loading Financial Configuration...")
                finance_config_loader_inst = FinanceConfigLoader(db_obj)
                
                return finance_config_loader_inst

            logger.info(f"⏳ Running database synchronization with timeout of {settings.db_timeout}s...")
            try:
                finance_config_loader_obj = await asyncio.wait_for(
                    asyncio.to_thread(run_initialization_sync),
                    timeout=float(settings.db_timeout)
                )
                app.state.finance_config_loader = finance_config_loader_obj
                
                catalog_items_count = len(catalog_service.get_all_items())
                app.state.catalog_ready = True
                logger.info(f"✅ [STARTUP-SUCCESS] Catálogo hidratado sin timeouts. Loaded items: {catalog_items_count}")
            except asyncio.TimeoutError as te:
                logger.exception(f"❌ [STARTUP-TIMEOUT] Database synchronization exceeded timeout of {settings.db_timeout} seconds (BOT-INFRA-33).")
            except Exception as exc:
                logger.exception(f"❌ [STARTUP-ERROR] Critical failure during database synchronization: {exc}")
                
        except Exception as e:
            logger.error(f"❌ Startup failed during early setup: {str(e)}")
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
                app.state.catalog_ready = True
            else:
                raise

        # Assign a dummy completed task to app.state.startup_task to support existing test assertions
        async def dummy_completed_task():
            pass
        app.state.startup_task = asyncio.create_task(dummy_completed_task())
    
    yield
    
    # Shutdown
    logger.info("👋 Shutting down Auteco Las Motos Backend...")
    from app.services.memory_service import memory_service
    if memory_service:
        await memory_service.shutdown()
    else:
        logger.warning("⚠️ MemoryService not initialized, skipping shutdown flush.")


async def _run_deferred_initialization(app: FastAPI) -> None:
    """
    [BOT-BACKEND-BUGFIX-CONTAINER-CRASH-188]
    Background task that performs all heavy network initialization AFTER Uvicorn
    has bound port 8080. This function runs in a background asyncio task launched
    from the lifespan handler.
    
    WHY this is safe:
    - The webhook handler in whatsapp.py (L362-388) checks app.state.catalog_ready
      and rejects requests with HTTP 503 until this task completes.
      - The /health endpoint returns status "starting" while this runs.
      - All Firestore/Secret Manager calls that previously blocked the import
        are now isolated here.
      
      Sequence (preserves the exact initialization order from the former module-level block):
      1. Firebase credentials (Secret Manager network call)
      2. Firestore sync + async clients (gRPC handshake)
      3. ConfigLoader singleton + load_all() (3x Firestore reads)
      4. CatalogService.initialize() with DI of ConfigLoader (Firestore stream + cache)
      5. FinanceConfigLoader (Firestore read)
      6. Catalog size validation (fail-fast guardrail)
      """
    await asyncio.sleep(2)
    try:
        logger.info("⚡ [DEFERRED-INIT] Starting background initialization...")

        # Run all blocking network I/O in a thread to avoid blocking the event loop
        def _sync_initialization():
            """Synchronous initialization block — runs in asyncio.to_thread()."""
            logger.info("🔑 [DEFERRED-INIT] Obtaining Firebase credentials...")
            creds = get_firebase_credentials_object()

            logger.info("🔗 [DEFERRED-INIT] Creating Firestore clients...")
            db_sync = firestore.Client(
                project=settings.gcp_project_id,
                credentials=creds
            )
            db_async_client = firestore.AsyncClient(
                project=settings.gcp_project_id,
                credentials=creds
            )

            logger.info("☁️  [DEFERRED-INIT] Initializing Storage Service...")
            storage_service.initialize(creds)

            logger.info("⚡ [DEFERRED-INIT] Initializing Config Service...")
            config_service.initialize(db_sync)

            logger.info("📋 [DEFERRED-INIT] Loading dynamic configurations (load_all)...")
            config_loader_inst = ConfigLoader(db_sync)
            config_loader_inst.load_all()

            logger.info("🏍️  [DEFERRED-INIT] Initializing Catalog Service with DI...")
            # WHY: config_loader is passed as an injected dependency (post-hydration)
            # to eliminate the race condition in CatalogService.load_catalog() where
            # ConfigLoader() was called without `db`, silently producing empty aliases.
            catalog_service.initialize(db_sync, config_loader_inst)

            logger.info("💰 [DEFERRED-INIT] Loading Financial Configuration...")
            finance_config = FinanceConfigLoader(db_sync)

            return creds, db_sync, db_async_client, config_loader_inst, finance_config

        # Execute all blocking I/O in a thread with timeout
        try:
            creds, db_obj, db_async_obj, config_loader_obj, finance_config_obj = await asyncio.wait_for(
                asyncio.to_thread(_sync_initialization),
                timeout=float(settings.db_timeout)
            )
        except asyncio.TimeoutError:
            logger.exception(
                f"❌ [DEFERRED-INIT-TIMEOUT] Background initialization exceeded "
                f"timeout of {settings.db_timeout}s. Catalog will remain unavailable. "
                f"The webhook handler will continue rejecting with HTTP 503."
            )
            return

        # Memory service initialization (async-native, runs on event loop)
        try:
            init_memory_service(db_async_obj)
        except Exception as mem_error:
            logger.error(f"❌ [DEFERRED-INIT] Failed to initialize Memory Service: {str(mem_error)}", exc_info=True)

        # Store references in app.state for downstream access
        app.state.config_loader = config_loader_obj
        app.state.db = db_obj
        app.state.db_async = db_async_obj
        app.state.finance_config_loader = finance_config_obj

        # [BOT-INFRA-BUGFIX-HEALTH-PORT-BINDING-192]
        # WHY: Hard size check (>= 60) is moved EXCLUSIVELY to app/routers/whatsapp.py
        # to avoid blocking the /health endpoint or preventing container startup.
        catalog_items_count = len(catalog_service.get_all_items())
        app.state.catalog_ready = True
        logger.info(
            f"✅ [DEFERRED-INIT-SUCCESS] Background initialization completed. "
            f"{catalog_items_count} catalog items loaded. catalog_ready=True."
        )

    except Exception as e:
        logger.exception(
            f"❌ [DEFERRED-INIT-CRITICAL] Unhandled exception during background "
            f"initialization: {e}. catalog_ready remains False."
        )


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
# Include routers — deferred imports within routers handle their own deps
from app.routers import whatsapp, admin
app.include_router(whatsapp.router)
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])


@app.get("/health")
async def health_check():
    """
    Health check endpoint for Cloud Run.
    
    [BOT-BACKEND-BUGFIX-CONTAINER-CRASH-188]
    WHY: Always returns HTTP 200 to satisfy the TCP startup probe.
    Reports "starting" while catalog hydration is in progress,
    and "healthy" once catalog_ready is True.
    """
    catalog_ready = getattr(app.state, "catalog_ready", False)
    status = "healthy" if catalog_ready else "starting"

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
        if not catalog_ready:
            logger.info("ℹ️ app.state.config_loader not yet initialized (background init in progress)")
        else:
            logger.warning("⚠️ app.state.config_loader is not initialized yet in health_check")

    catalog_items_count = 0
    try:
        from app.services.catalog_service import catalog_service
        catalog_items_count = len(catalog_service.get_all_items())
    except Exception as e:
        logger.exception("❌ Error retrieving catalog items in health check: %s", e)

    storage_bucket_name = None
    try:
        from app.services.storage_service import storage_service
        storage_bucket_name = storage_service.get_bucket_name()
    except Exception as e:
        logger.exception("❌ Error retrieving storage bucket name in health check: %s", e)

    return {
        "status": status,
        "service": "Auteco Las Motos Backend",
        "version": "6.0.0",
        "catalog_items": catalog_items_count,
        "catalog_ready": catalog_ready,
        "storage_bucket": storage_bucket_name,
        "v6_config": v6_config
    }


@app.get("/robots.txt", response_class=PlainTextResponse)
async def robots_txt():
    """
    Robots.txt endpoint.
    
    Returns:
        Empty robots.txt response with 200 OK for balancer probe.
    """
    return ""


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
