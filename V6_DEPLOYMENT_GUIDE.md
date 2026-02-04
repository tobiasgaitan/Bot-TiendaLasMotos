# V6.0 Configuration System - Deployment Guide

## 📋 Overview

Este documento describe cómo desplegar la **Fase 1 de V6.0: Configuración Dinámica** en tu entorno de Cloud Run.

## 🎯 What Was Created

### 1. **config_loader.py** - Configuration Loader
- **Path**: `app/core/config_loader.py`
- **Purpose**: Carga configuración dinámica desde Firestore
- **Features**:
  - Carga personalidad de Sebas desde Firestore
  - Carga reglas de enrutamiento
  - Fail-safe defaults si Firestore no está disponible
  - Método `refresh()` para hot-reload

### 2. **init_v6_config.py** - Database Initialization
- **Path**: `scripts/init_v6_config.py`
- **Purpose**: Poblar Firestore con configuración inicial
- **Creates**:
  - `configuracion/sebas_personality`: Personalidad y system prompt de Sebas
  - `configuracion/routing_rules`: Keywords para enrutamiento de mensajes
  - `configuracion/catalog_config`: Configuración del catálogo

### 3. **INTEGRATION_EXAMPLE.py** - Integration Guide
- **Path**: `INTEGRATION_EXAMPLE.py`
- **Purpose**: Muestra exactamente cómo modificar `main.py`

---

## 🚀 Deployment Steps

### Step 1: Initialize Firestore Configuration

Ejecuta esto **UNA SOLA VEZ** desde Cloud Shell:

```bash
# Navegar al directorio del proyecto
cd ~/Bot-TiendaLasMotos

# Ejecutar script de inicialización
python3 scripts/init_v6_config.py
```

**Expected Output**:
```
============================================================
V6.0 Configuration Initialization
Tienda Las Motos - WhatsApp Bot
============================================================

🔥 Connecting to Firestore...
✅ Connected to Firestore

📝 Initializing Sebas personality configuration...
✅ Sebas personality configuration created
📝 Initializing routing rules...
✅ Routing rules configuration created
📝 Initializing catalog configuration...
✅ Catalog configuration created

🔍 Verifying configuration...
  ✅ sebas_personality: OK
  ✅ routing_rules: OK
  ✅ catalog_config: OK

✅ All V6.0 configuration documents created successfully!
```

### Step 2: Verify Firestore Data

Verifica que los documentos fueron creados:

```bash
# Opción 1: Via gcloud CLI
gcloud firestore documents list --collection-ids=configuracion

# Opción 2: Via Firebase Console
# Ir a: https://console.firebase.google.com/project/tiendalasmotos/firestore
# Navegar a: configuracion/
```

Deberías ver 3 documentos:
- `sebas_personality`
- `routing_rules`
- `catalog_config`

### Step 3: Update main.py

Abre `INTEGRATION_EXAMPLE.py` y aplica los cambios a `app/main.py`:

**Changes needed**:

1. **Add import** (línea ~14):
```python
from app.core.config_loader import ConfigLoader
```

2. **Add initialization** (línea ~54, después de `catalog_service.initialize(db)`):
```python
# 4.5. Load V6.0 dynamic configuration
logger.info("🧠 Loading V6.0 dynamic configuration...")
config_loader = ConfigLoader(db)
config_loader.load_all()

# Store in app state for access in routes
app.state.config_loader = config_loader
app.state.db = db
```

3. **Update health check** (opcional, línea ~88):
```python
@app.get("/health")
async def health_check(request: Request):
    config_loader = request.app.state.config_loader
    
    return {
        "status": "healthy",
        "service": "Tienda Las Motos Backend",
        "version": "6.0.0",
        "catalog_items": len(catalog_service.get_all_items()),
        "storage_bucket": storage_service.get_bucket_name(),
        "v6_config": {
            "sebas_model": config_loader.get_sebas_personality().get("model_version"),
            "routing_keywords_loaded": len(config_loader.get_routing_rules().get("financial_keywords", [])),
        }
    }
```

### Step 4: Deploy to Cloud Run

```bash
# Desde Cloud Shell
cd ~/Bot-TiendaLasMotos
./deploy.sh
```

### Step 5: Verify Deployment

```bash
# Test health endpoint
curl https://[YOUR-CLOUD-RUN-URL]/health

# Check logs
gcloud run services logs read bot-tiendalasmotos --limit=50
```

**Expected log output**:
```
🚀 Starting Tienda Las Motos Backend...
🔐 Retrieving credentials from Secret Manager...
🔥 Initializing Firestore client...
📋 Loading configuration...
✅ Financial config loaded: X keys
✅ Partners config loaded: X keys
🏍️  Loading catalog...
🧠 Loading V6.0 dynamic configuration...
✅ Sebas personality loaded (model: gemini-2.0-flash)
✅ Routing rules loaded (17 financial keywords)
✅ Catalog config loaded (4 items)
☁️  Initializing Cloud Storage...
✅ Application startup complete!
```

---

## ✅ Verification Checklist

- [ ] `init_v6_config.py` ejecutado exitosamente
- [ ] 3 documentos creados en Firestore `configuracion/`
- [ ] `main.py` actualizado con ConfigLoader
- [ ] Deployment exitoso a Cloud Run
- [ ] Logs muestran "🧠 Loading V6.0 dynamic configuration..."
- [ ] `/health` endpoint responde con `v6_config` section
- [ ] Enrutamiento actual sigue funcionando (backward compatibility)

---

## 🔧 Troubleshooting

### Error: "Module 'app.core.config_loader' not found"
**Solution**: Verifica que `config_loader.py` esté en `app/core/` y que el import sea correcto.

### Error: "configuracion/sebas_personality not found"
**Solution**: Ejecuta `init_v6_config.py` nuevamente desde Cloud Shell.

### Warning: "Using default configurations"
**Cause**: Firestore documentos no existen o hay error de permisos.
**Solution**: Verifica que `init_v6_config.py` se ejecutó correctamente y que el service account tiene permisos de lectura en Firestore.

---

## 📚 Next Steps (Phase 2)

Una vez que V6.0 Fase 1 esté desplegado y funcionando:

1. **Migrate ai_brain.py** to use `config_loader.get_sebas_personality()`
2. **Migrate routing logic** to use `config_loader.get_routing_rules()`
3. **Add admin endpoint** for hot-reload: `POST /admin/config/refresh`
4. **Implement real-time updates** via Firestore listeners

---

## 🛡️ Security Notes

- ✅ No credentials hardcoded
- ✅ Configuration loaded from Firestore (secure)
- ✅ Fail-safe defaults prevent crashes
- ✅ Backward compatible with current production code

---

## 📞 Support

Si encuentras problemas durante el deployment, revisa:
1. Logs de Cloud Run: `gcloud run services logs read bot-tiendalasmotos`
2. Firestore Console: https://console.firebase.google.com/project/tiendalasmotos/firestore
3. Este README y `INTEGRATION_EXAMPLE.py`
