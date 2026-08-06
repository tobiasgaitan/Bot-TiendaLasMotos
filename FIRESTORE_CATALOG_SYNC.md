# ⚠️ catalog_items ERRADICADA 2026-08-05 (v10.52.1)

> **SSOT único**: `pagina/catalogo/items`  
> **Backup**: `attic/backup_catalog_items_2026-08-05.json`  
> **Seed archivado**: `attic/seed_catalog.py` — **NO re-ejecutar**  
> **Motivo**: MotorVentas lee el catálogo canónico desde `pagina/catalogo/items` (ver `app/services/catalog_service.py`). La colección huérfana `catalog_items` fue respaldada y eliminada de producción.

---

## ✅ MotorVentas Synced with Firestore Catalog (Histórico)

Este documento se conserva como registro histórico de la integración original. Las instrucciones operativas que apuntaban a `catalog_items` están marcadas como obsoletas.

## 🎯 Critical Fix Applied (Histórico)

**Issue**: Bot responding with "Sin descripción disponible"  
**Root Cause**: MotorVentas was not querying Firestore catalog_items collection  
**Solution**: Rewrote `_load_catalog()` to fetch data directly from Firestore (hoy la ruta canónica es `pagina/catalogo/items`)

---

## 🔧 Changes Made (Histórico)

### 1. **Updated `app/services/catalog.py`** (versión histórica)

```python
def _load_catalog(self) -> List[Dict[str, Any]]:
    try:
        if self._db:
            logger.info("📚 Loading catalog from Firestore pagina/catalogo/items collection...")
            
            catalog_ref = self._db.collection("pagina").document("catalogo").collection("items")
            docs = catalog_ref.stream()
            
            catalog = []
            for doc in docs:
                data = doc.to_dict()
                if data.get("active", True):
                    moto = {
                        "id": data.get("id", doc.id),
                        "name": data.get("name", "Moto"),
                        "category": data.get("category", "general"),
                        "description": data.get("description", "Sin descripción disponible"),
                        "highlights": data.get("highlights", []),
                        "price": data.get("price", 0),
                        "engine": data.get("engine", "N/A"),
                        "fuel_efficiency": data.get("fuel_efficiency", "N/A"),
                        "active": data.get("active", True)
                    }
                    catalog.append(moto)
                    logger.info(f"  ✅ Loaded: {moto['name']} ({moto['category']})")
            
            if catalog:
                logger.info(f"✅ Catalog loaded successfully: {len(catalog)} motorcycles")
                return catalog
    except Exception as e:
        logger.error(f"❌ Error loading catalog from Firestore: {str(e)}")
    
    return self._default_catalog()
```

> **Nota**: El código actual de `CatalogService` vive en `app/services/catalog_service.py` y lee del SSOT `pagina/catalogo/items`. El snippet anterior ilustra la estructura histórica.

---

## 📊 Expected Log Output

```
✅ MotorVentas initialized with 4 motorcycles
📚 Loading catalog from Firestore pagina/catalogo/items collection...
  ✅ Loaded: NKD 125 (urbana)
  ✅ Loaded: Sport 100 (deportiva)
  ✅ Loaded: Victory Black (ejecutiva)
  ✅ Loaded: MRX 150 (todo-terreno)
✅ Catalog loaded successfully: 4 motorcycles
```

---

## 🚀 Deployment Steps (actualizadas)

### Step 1: Pull Latest Code in Cloud Shell

```bash
cd ~/Bot-TiendaLasMotos
git pull origin main
```

### Step 2: Verify Catalog is in the SSOT

El catálogo canónico vive en:

```
Firestore → pagina → catalogo → items
```

**NO ejecutar** `python3 scripts/seed_catalog.py`; el script fue archivado en `attic/seed_catalog.py` y la colección `catalog_items` ya no existe.

### Step 3: Deploy to Cloud Run

```bash
./deploy.sh
```

### Step 4: Verify in Logs

```bash
gcloud run services logs read bot-tiendalasmotos --limit=100
```

**Look for**:
- `📚 Loading catalog from Firestore pagina/catalogo/items collection...`
- `✅ Loaded: NKD 125 (urbana)` (and other motorcycles)
- `✅ Catalog loaded successfully: 4 motorcycles`

---

## 🧪 Testing

### Test Query 1: General Catalog

**User**: "Hola, quiero ver las motos"

**Expected Response**:
```
🏍️ **Catálogo Tienda Las Motos**

Tenemos estas increíbles opciones para ti:

**NKD 125** - Moto urbana económica, ideal para la ciudad y el trabajo diario
**Sport 100** - Moto deportiva de entrada, perfecta para jóvenes que buscan estilo y velocidad
**Victory Black** - Moto ejecutiva elegante y potente, diseñada para profesionales exigentes
**MRX 150** - Moto aventurera todo terreno, resistente y versátil para cualquier camino

💡 Dime qué tipo de moto buscas o pregúntame por alguna específica.
💳 También puedo hacer una simulación de crédito personalizada.
```

---

### Test Query 2: Category Search

**User**: "Busco una moto para ciudad"

**Expected Response**:
```
🏍️ **Motos para ciudad**

**NKD 125**
📝 Moto urbana económica, ideal para la ciudad y el trabajo diario
✨ Bajo consumo de combustible, Perfecta para tráfico urbano, Mantenimiento económico, Diseño moderno y compacto

💳 ¿Te gustaría una simulación de crédito para alguna de estas motos?
📱 También puedo darte más información sobre cualquiera de ellas.
```

---

### Test Query 3: Specific Motorcycle

**User**: "Cuéntame sobre la Victory Black"

**Expected Response**:
```
🏍️ **Motos encontradas**

**Victory Black**
📝 Moto ejecutiva elegante y potente, diseñada para profesionales exigentes
✨ Diseño elegante y sofisticado, Motor potente y confiable, Confort superior, Tecnología avanzada

💳 ¿Te gustaría una simulación de crédito para alguna de estas motos?
📱 También puedo darte más información sobre cualquiera de ellas.
```

---

## 🔍 Troubleshooting

### Issue: Still showing "Sin descripción disponible"

**Possible Causes**:
1. Catalog not seeded in the SSOT (`pagina/catalogo/items`)
2. Firestore client not initialized
3. Old code still deployed

**Solution**:
```bash
# 1. Verify the SSOT catalog is populated
# Firestore Console → pagina → catalogo → items
# Should see 4+ documents

# 2. Redeploy with latest code
git pull origin main
./deploy.sh
```

---

### Issue: "No motorcycles found in catalog_items collection"

**Status**: ⚠️ Obsoleto. La colección `catalog_items` fue erradicada en v10.52.1.

**Solution**: Verificar el SSOT en `pagina/catalogo/items`.

---

### Issue: "Firestore client not available"

**Solution**: Check `main.py` startup logs
```bash
gcloud run services logs read bot-tiendalasmotos --limit=200 | grep -i firestore
```

Should see:
```
🔥 Initializing Firestore client...
✅ Firestore client initialized
```

---

## ✅ Verification Checklist

After deployment:

- [ ] 4+ motorcycles visible in Firestore Console (`pagina/catalogo/items`)
- [ ] `catalog_items` collection **absent** in Firestore Console
- [ ] Deployment completed without errors
- [ ] Logs show "Loading catalog from Firestore pagina/catalogo/items collection"
- [ ] Logs show "Loaded: NKD 125 (urbana)" and other motorcycles
- [ ] Logs show "Catalog loaded successfully: 4 motorcycles"
- [ ] Test message shows real motorcycle descriptions (not "Sin descripción disponible")
- [ ] Category search works (e.g., "moto para ciudad")
- [ ] Specific motorcycle search works (e.g., "Victory Black")

---

## 📦 Data Flow

```
User Message
     ↓
WhatsApp Webhook
     ↓
POST /webhook
     ↓
CatalogService._load_catalog()
     ↓
Firestore.collection("pagina").document("catalogo").collection("items").stream()
     ↓
[NKD 125, Sport 100, Victory Black, MRX 150]
     ↓
Format Response
     ↓
Send via WhatsApp API
     ↓
User receives detailed motorcycle info
```

---

**Status**: ⚠️ `catalog_items` erradicada; SSOT activo en `pagina/catalogo/items`  
**Commit**: `826ba2c` (histórico), erradicación v10.52.1  
**Repository**: https://github.com/tobiasgaitan/Bot-TiendaLasMotos
