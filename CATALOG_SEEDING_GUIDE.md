# 🏍️ Catalog Seeding Script - Usage Guide

## ✅ Script Created and Pushed to GitHub

**File**: `scripts/seed_catalog.py`
**Commit**: `7b9f7a4`
**Repository**: https://github.com/tobiasgaitan/Bot-TiendaLasMotos

---

## 📋 What the Script Does

Seeds the `catalog_items` collection in Firestore with 4 motorcycles:

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

## 🚀 How to Run (Cloud Shell)

### Step 1: Pull Latest Code

```bash
cd ~/Bot-TiendaLasMotos
git pull origin main
```

### Step 2: Install Dependencies (if needed)

```bash
pip3 install firebase-admin
```

### Step 3: Run the Seeding Script

```bash
python3 scripts/seed_catalog.py
```

---

## 📊 Expected Output

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

## 🔧 Technical Details

### Firebase Initialization
- Uses **Application Default Credentials**
- Works automatically in Cloud Shell
- No manual credential file needed

### Collection Structure
```
catalog_items/
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

## 🔍 Verify in Firestore Console

After running the script, verify in Firebase Console:

1. Go to: https://console.firebase.google.com/
2. Select project: **tiendalasmotos**
3. Navigate to: **Firestore Database**
4. Check collection: **catalog_items**
5. Should see 4 documents: `nkd-125`, `sport-100`, `victory-black`, `mrx-150`

---

## 🐛 Troubleshooting

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

## 📝 Additional Improvements

Also pushed improvements to `app/services/catalog.py`:

- ✅ Safe dictionary access with `.get()` to prevent KeyError
- ✅ Enhanced error handling with AttributeError catching
- ✅ Defensive programming for ConfigLoader attribute access
- ✅ Better logging for debugging data issues
- ✅ Graceful degradation if data is missing or malformed

---

## ✅ Next Steps

1. **Run the script** in Cloud Shell to seed the catalog
2. **Verify** the data in Firestore Console
3. **Test** the MotorVentas service with real catalog data
4. **Deploy** the updated application

---

**Status**: ✅ Script created, committed, and pushed to GitHub
**Commit**: `7b9f7a4`
**Ready**: To run in Cloud Shell
