"""
EXAMPLE: How to integrate ConfigLoader into main.py

This file shows the EXACT changes needed to integrate V6.0 configuration
into your existing main.py WITHOUT breaking current functionality.

INSTRUCTIONS:
1. Add the import at the top
2. Add the initialization code in the lifespan function
3. Optionally update the health check endpoint
"""

# ==================== STEP 1: Add Import ====================
# Add this line around line 14, after other imports:

from app.core.config_loader import ConfigLoader


# ==================== STEP 2: Modify lifespan function ====================
# In the lifespan function, add this code after line 54 (after catalog_service.initialize)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("🚀 Starting Tienda Las Motos Backend...")
    
    try:
        # ... existing code (lines 37-54) ...
        
        # 4. Load catalog into memory
        logger.info("🏍️  Loading catalog...")
        catalog_service.initialize(db)
        
        # ✨ NEW: 4.5. Load V6.0 dynamic configuration
        logger.info("🧠 Loading V6.0 dynamic configuration...")
        config_loader = ConfigLoader(db)
        config_loader.load_all()
        
        # Store in app state for access in routes
        app.state.config_loader = config_loader
        app.state.db = db  # Also store db for future use
        
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


# ==================== STEP 3: Update health check (OPTIONAL) ====================
# Optionally enhance the health check endpoint to show V6.0 status

@app.get("/health")
async def health_check(request: Request):
    """
    Health check endpoint for Cloud Run.
    
    Returns:
        Status information about the application
    """
    config_loader = request.app.state.config_loader
    
    return {
        "status": "healthy",
        "service": "Tienda Las Motos Backend",
        "version": "6.0.0",  # Updated version
        "catalog_items": len(catalog_service.get_all_items()),
        "storage_bucket": storage_service.get_bucket_name(),
        "v6_config": {
            "sebas_model": config_loader.get_sebas_personality().get("model_version"),
            "routing_keywords_loaded": len(config_loader.get_routing_rules().get("financial_keywords", [])),
            "catalog_config_items": len(config_loader.get_catalog_config().get("items", []))
        }
    }


# ==================== STEP 4: Access config in routes (FUTURE) ====================
# Example of how to access config_loader in your route handlers:

@app.post("/webhook")
async def webhook_handler(request: Request):
    # Access the config loader from app state
    config_loader = request.app.state.config_loader
    
    # Get Sebas personality for AI responses
    sebas_config = config_loader.get_sebas_personality()
    system_instruction = sebas_config["system_instruction"]
    
    # Get routing rules for message classification
    routing_rules = config_loader.get_routing_rules()
    financial_keywords = routing_rules["financial_keywords"]
    
    # ... rest of your webhook logic ...


# ==================== NOTES ====================
"""
IMPORTANT NOTES:

1. BACKWARD COMPATIBILITY:
   - Your existing routing logic in whatsapp.py will continue to work
   - No changes needed to services/finance.py, services/catalog.py, services/ai_brain.py
   - This is purely additive - we're adding new capability without breaking existing code

2. DEPLOYMENT SEQUENCE:
   Step 1: Run init_v6_config.py in Cloud Shell to populate Firestore
   Step 2: Update main.py with the changes shown above
   Step 3: Deploy to Cloud Run with ./deploy.sh
   Step 4: Verify /health endpoint shows V6.0 configuration loaded

3. FUTURE ENHANCEMENTS (Phase 2):
   - Migrate ai_brain.py to use config_loader.get_sebas_personality()
   - Migrate routing logic to use config_loader.get_routing_rules()
   - Add admin endpoint to call config_loader.refresh() for hot-reload

4. FAIL-SAFE BEHAVIOR:
   - If Firestore documents don't exist, config_loader uses hardcoded defaults
   - Your app will never crash due to missing configuration
   - Logs will show warnings if using defaults instead of Firestore config
"""
