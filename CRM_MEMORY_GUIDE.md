# CRM Memory Integration - Quick Reference

## 🎯 System Overview

The WhatsApp bot has **persistent memory** that recognizes prospects from Firestore and personalizes conversations.

---

## 🔧 How It Works

1. **Message Received** → Load prospect data from Firestore
2. **AI Brain** → Inject context into system prompt
3. **Personalized Response** → Use name and motorcycle interest
4. **Update Summary** → Save conversation to Firestore

---

## 📊 Firestore Schema

**Collection:** `prospectos`

**Required Fields:**
```json
{
  "celular": "3192564288",           // Without country code!
  "nombre": "Capitán Victoria",
  "moto_interest": "Victory Black",
  "ai_summary": "Cliente VIP...",
  "chatbot_status": "PENDING"
}
```

⚠️ **Important:** `celular` must be **without** country code (e.g., `3192564288`, not `573192564288`)

---

## 🧪 Testing with Capitán Victoria

### Test Message
Send from **573192564288**:
```
"Hola, quiero información"
```

### Expected Response
```
¡Hola Capitán Victoria! 👋 

Vi que te interesa la Victory Black. ¿Sigues buscando información 
sobre esta moto ejecutiva?
```

### Expected Logs
```
🔍 Searching for prospect with celular: 3192564288
✅ Prospect found: Capitán Victoria | Interest: Victory Black | Has summary: True
🧠 Prospect data loaded for 573192564288: Capitán Victoria
💾 Prospect summary updated for 573192564288
```

### Firestore Changes
- `chatbot_status`: `PENDING` → `ACTIVE`
- `ai_summary`: Updated with new conversation
- `updated_at`: New timestamp

---

## 📝 Key Features

### ✅ Flexible Phone Matching
- Handles `573192564288`, `+573192564288`, `3192564288`
- Automatically strips `+` and country code `57`

### ✅ AI Data Extraction
- Extracts name from conversation
- Extracts motorcycle interest
- Updates Firestore automatically

### ✅ Graceful Errors
- Doesn't block conversations on errors
- Creates new prospects if not found
- Logs all operations

---

## 🔍 Verification Checklist

- [ ] Firestore has prospect data with `celular` = `3192564288`
- [ ] Send WhatsApp message from `573192564288`
- [ ] Check Cloud Run logs for `🧠 Prospect data loaded`
- [ ] Verify personalized greeting in response
- [ ] Check Firestore for updated `ai_summary`
- [ ] Verify `chatbot_status` changed to `ACTIVE`

---

## 📍 Code Locations

| Component | File | Lines |
|-----------|------|-------|
| Memory Service | `app/services/memory_service.py` | 1-211 |
| AI Context Injection | `app/services/ai_brain.py` | 216-228 |
| WhatsApp Integration | `app/routers/whatsapp.py` | 159-168, 299-316 |
| Initialization | `app/main.py` | 79 |

---

## 🔄 One-Shot Legacy Migration (v10.57.0 — BOT-BUILD-FUNNEL-SKIP-014)

**IMPORTANTE:** No ejecutar sobre Firestore sin orden literal separada de Tobias (C-10).

Tras el deploy de v10.57.0, los documentos legacy que cumplan:
- `moto_interest` no canónico (categoría, con acentos o variaciones no machean un `name` exacto del catálogo), **Y**
- `habeas_data_accepted=True` o `forma_pago="Crédito"`

quedarán atrapados en `PHASE_1_PROFILING` (por diseño: la compuerta Habeas ahora exige modelo canónico). Para sanearlos sin tocar historial:

```python
# Script operacional one-shot (NO commitear en app/ ni en scripts/)
# Ejecutar en entorno con acceso a Firestore y catalog_service inicializado.

async def migrate_legacy_phase_latches():
    from app.services.memory_service import memory_service
    from app.services.catalog_service import catalog_service

    docs = (
        memory_service._db.collection("prospectos")
        .where("habeas_data_accepted", "==", True)
        .stream()
    )
    async for doc in docs:
        data = doc.to_dict() or {}
        moto = data.get("moto_interest", "")
        if not moto:
            continue
        matches = catalog_service.search_items(str(moto))
        is_canonical = False
        if matches:
            target = catalog_service._normalize_item_id_key(str(moto))
            is_canonical = any(
                catalog_service._normalize_item_id_key(str(item.get("name", ""))) == target
                for item in matches
            )
        if not is_canonical:
            await memory_service.reset_phase_latches(doc.id)
            print(f"Latches reset for {doc.id} (non-canonical moto={moto})")
```

Este script es **idempotente**: `reset_phase_latches` usa `set(merge=True)` y sólo escribe los latches de fase + `moto_interest/moto_interes` a cadena vacía; `nombre`, `ciudad` e historial se preservan.

---

## 🚀 Status

✅ **PRODUCTION READY**

All components operational and security-approved.
