# ⚠️ catalog_items ERRADICADA 2026-08-05 (v10.52.1)

> **SSOT único**: `pagina/catalogo/items`  
> **Backup**: `attic/backup_catalog_items_2026-08-05.json`  
> **Seed archivado**: `attic/seed_catalog.py` — **NO re-ejecutar**  
> La guía original se conserva como registro histórico. Las instrucciones para poblar la colección huérfana `catalog_items` están marcadas como obsoletas.

---

# 🏍️ Catalog Seeding Script - Usage Guide (Histórico)

## ✅ Script Created and Pushed to GitHub (Histórico)

**Original file**: `scripts/seed_catalog.py`  
**Archived file**: `attic/seed_catalog.py`  
**Commit**: `7b9f7a4`  
**Repository**: https://github.com/tobiasgaitan/Bot-TiendaLasMotos

---

## 📋 What the Script Did (Histórico)

Seeded the `catalog_items` collection in Firestore with 4 motorcycles:

1. **NKD 125** (Urbana) - $4,500,000 COP
   - Económica, ideal para ciudad
   - 125cc, 45 km/l

2. **Sport 100** (Deportiva) - $5,200,000 COP
   - Deportiva de entrada para jóvenes
   - 100cc, 40 km/l

3. **Victory Black** (Ejecutiva) - $8,500,000 COP
   - Elegante y potente para profesionales
   - 200cc, 35 km/l

4. **MRX 150** (Todo Terreno) - $7,200,000 COP
   - Aventurera y resistente
   - 150cc, 38 km/l

---

## 🚀 How to Run (Cloud Shell) — ⚠️ OBsoleto

```bash
# ⚠️ NO EJECUTAR. scripts/seed_catalog.py fue archivado a attic/seed_catalog.py
# y la colección catalog_items fue erradicada en v10.52.1.
# El catálogo canónico vive en pagina/catalogo/items.
```

---

## 📊 Expected Output (Histórico)

```
🚀 Starting Catalog Seeding Script...
Project: tiendalasmotos
Collection: catalog_items

✅ Firebase Admin initialized successfully

============================================================
🏍️  SEEDING MOTORCYCLE CATALOG
============================================================
✅ Seeded: NKD 125 (urbana)
   Price: $4,500,000 COP
   Engine: 125cc

✅ Seeded: Sport 100 (deportiva)
   Price: $5,200,000 COP
   Engine: 100cc

✅ Seeded: Victory Black (ejecutiva)
   Price: $8,500,000 COP
   Engine: 200cc

✅ Seeded: MRX 150 (todo-terreno)
   Price: $7,200,000 COP
   Engine: 150cc

============================================================
✅ Catalog seeding complete! 4 motorcycles added.
============================================================

============================================================
🔍 VERIFYING CATALOG
============================================================
✅ nkd-125: NKD 125 - urbana
✅ sport-100: Sport 100 - deportiva
✅ victory-black: Victory Black - ejecutiva
✅ mrx-150: MRX 150 - todo-terreno
============================================================
Total motorcycles in catalog: 4
============================================================

✅ Script completed successfully!
```

---

## 🔧 Technical Details (Histórico)

### Firebase Initialization
- Uses **Application Default Credentials**
- Works automatically in Cloud Shell
- No manual credential file needed

### Collection Structure (Histórico)
```
catalog_items/          ← colección erradicada
  ├── nkd-125/
  │   ├── id: "nkd-125"
  │   ├── name: "NKD 125"
  │   ├── category: "urbana"
  │   ├── description: "..."
  │   ├── highlights: [...]
  │   ├── price: 4500000
  │   ├── engine: "125cc"
  │   ├── fuel_efficiency: "45 km/l"
  │   ├── active: true
  │   ├── created_at: timestamp
  │   └── updated_at: timestamp
  ├── sport-100/
  ├── victory-black/
  └── mrx-150/
```

### Upsert Logic
- Uses `set(data, merge=True)` to update if exists
- Safe to run multiple times
- Won't duplicate data

---

## 🔍 Verify in Firestore Console (actualizado)

El catálogo canónico se verifica en:

1. Go to: https://console.firebase.google.com/
2. Select project: **tiendalasmotos**
3. Navigate to: **Firestore Database**
4. Check: **pagina → catalogo → items**
5. Should see 4+ documents: `nkd-125`, `sport-100`, `victory-black`, `mrx-150`

La colección `catalog_items` debe estar **ausente**.

---

## 🐛 Troubleshooting (Histórico)

### Error: "Could not automatically determine credentials"

**Solution**: Authenticate in Cloud Shell
```bash
gcloud auth application-default login
```

### Error: "Permission denied"

**Solution**: Ensure you have Firestore permissions
```bash
gcloud projects add-iam-policy-binding tiendalasmotos \
  --member="user:YOUR_EMAIL" \
  --role="roles/datastore.user"
```

### Error: "Module 'firebase_admin' not found"

**Solution**: Install firebase-admin
```bash
pip3 install firebase-admin
```

---

## 📝 Additional Improvements (Histórico)

Also pushed improvements to `app/services/catalog.py`:

- ✅ Safe dictionary access with `.get()` to prevent KeyError
- ✅ Enhanced error handling with AttributeError catching
- ✅ Defensive programming for ConfigLoader attribute access
- ✅ Better logging for debugging data issues
- ✅ Graceful degradation if data is missing or malformed

---

## ✅ Next Steps (actualizados)

1. **NO ejecutar** el seed script; está archivado en `attic/seed_catalog.py`.
2. **Verificar** el catálogo canónico en `pagina/catalogo/items`.
3. **Test** el `CatalogService` con los datos canónicos.
4. **Deploy** la aplicación actualizada.

---

**Status**: ⚠️ `catalog_items` erradicada en v10.52.1; script archivado en `attic/seed_catalog.py`  
**Commit**: `7b9f7a4` (histórico), erradicación v10.52.1  
**Ready**: NO ejecutar; el catálogo vive en `pagina/catalogo/items`
