# ✅ SIMPLIFIED CONFIGURATION - os.getenv Implementation

## 🎯 Critical Fix Applied

**Issue**: Pydantic BaseSettings not reliably reading environment variables in Cloud Run
**Solution**: Complete rewrite using native Python `os.getenv()`

---

## 🔧 Changes Made

### 1. **Completely Rewrote `app/core/config.py`**

**Before** (Pydantic):
```python
from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    whatsapp_token: str = Field(default="", alias="WHATSAPP_TOKEN")
```

**After** (os.getenv):
```python
import os

class Settings:
    def __init__(self):
        self.whatsapp_token: str = os.getenv("WHATSAPP_TOKEN", "")
        self.phone_number_id: str = os.getenv("PHONE_NUMBER_ID", "")
        # ... etc
        
        self._log_config_status()  # Print configuration on startup
```

---

### 2. **Added Configuration Logging**

On startup, you'll now see:

```
============================================================
🔧 CONFIGURATION LOADED
============================================================
GCP Project ID: tiendalasmotos
Secret Name: FIREBASE_CREDENTIALS
Storage Bucket: tiendalasmotos-documents
Webhook Verify Token: ✅ SET
WhatsApp Token: ✅ FOUND  (or ❌ MISSING)
Phone Number ID: ✅ FOUND  (or ❌ MISSING)
Port: 8080
============================================================
```

**If missing**:
```
⚠️  WARNING: WHATSAPP_TOKEN is not set!
   Set it with: gcloud run services update ... --set-env-vars='WHATSAPP_TOKEN=xxx'
```

---

### 3. **Added Early Return in `whatsapp.py`**

**Prevents crash** if token is missing:

```python
async def _send_whatsapp_message(to_phone: str, message_text: str) -> None:
    # CRITICAL: Early check - prevent crash if token is missing
    if not settings.whatsapp_token:
        logger.error("🔥 CRITICAL: Attempting to send message but WHATSAPP_TOKEN is empty!")
        logger.error("Message NOT sent. Please configure WHATSAPP_TOKEN in Cloud Run.")
        return  # Exit gracefully instead of crashing
```

---

## 🚀 Deployment Steps

### Step 1: Pull Latest Code in Cloud Shell

```bash
cd ~/Bot-TiendaLasMotos
git pull origin main
```

---

### Step 2: Verify Environment Variables Are Set

```bash
gcloud run services describe bot-tiendalasmotos \
  --region=us-central1 \
  --format="value(spec.template.spec.containers[0].env)"
```

**Expected output should include**:
```
WHATSAPP_TOKEN=EAAxxxxx...
PHONE_NUMBER_ID=123456789
```

**If NOT set**, run:

```bash
gcloud run services update bot-tiendalasmotos \
  --region=us-central1 \
  --set-env-vars="WHATSAPP_TOKEN=YOUR_TOKEN,PHONE_NUMBER_ID=YOUR_PHONE_ID"
```

---

### Step 3: Deploy

```bash
./deploy.sh
```

---

### Step 4: Check Startup Logs

Immediately after deployment, check logs:

```bash
gcloud run services logs read bot-tiendalasmotos --limit=100
```

**Look for the configuration block**:

```
============================================================
🔧 CONFIGURATION LOADED
============================================================
WhatsApp Token: ✅ FOUND
Phone Number ID: ✅ FOUND
============================================================
```

**If you see** `❌ MISSING`, the environment variables are not set correctly.

---

## 🔍 Debugging Guide

### Scenario 1: Logs show "WhatsApp Token: ❌ MISSING"

**Problem**: Environment variable not set in Cloud Run

**Solution**:
```bash
gcloud run services update bot-tiendalasmotos \
  --region=us-central1 \
  --set-env-vars="WHATSAPP_TOKEN=EAAxxxxx..."
```

---

### Scenario 2: Logs show "WhatsApp Token: ✅ FOUND" but still crashes

**Problem**: Token might be invalid or expired

**Solution**:
1. Verify token in Meta Business Manager
2. Generate new token if needed
3. Update Cloud Run with new token

---

### Scenario 3: No configuration block in logs

**Problem**: Application crashed before config could load

**Solution**:
```bash
# Check for Python errors
gcloud run services logs read bot-tiendalasmotos --limit=200 | grep -i error
```

---

## 📊 Expected Log Flow

### On Startup:
```
🚀 Starting Tienda Las Motos Backend...
============================================================
🔧 CONFIGURATION LOADED
============================================================
WhatsApp Token: ✅ FOUND
Phone Number ID: ✅ FOUND
============================================================
🔐 Retrieving credentials from Secret Manager...
🔥 Initializing Firestore client...
🧠 Loading V6.0 dynamic configuration...
✅ Application startup complete!
```

### On Message Received:
```
📨 WhatsApp message received
👤 From: 573001234567
💬 Message: Hola
💰 Routing to MotorFinanciero
📤 Sending message to 573001234567 via WhatsApp API
✅ Message sent successfully to 573001234567
```

### If Token Missing:
```
📨 WhatsApp message received
👤 From: 573001234567
💬 Message: Hola
💰 Routing to MotorFinanciero
🔥 CRITICAL: Attempting to send message but WHATSAPP_TOKEN is empty!
Message NOT sent. Please configure WHATSAPP_TOKEN in Cloud Run.
```

---

## ✅ Verification Checklist

After deployment:

- [ ] Configuration block appears in logs
- [ ] "WhatsApp Token: ✅ FOUND" shown
- [ ] "Phone Number ID: ✅ FOUND" shown
- [ ] No crash on startup
- [ ] Test message received by bot
- [ ] Bot attempts to send response
- [ ] No "Illegal header value" error
- [ ] Response delivered to WhatsApp user

---

## 🎯 Key Improvements

1. **Reliability**: `os.getenv()` is more reliable than Pydantic in Cloud Run
2. **Visibility**: Configuration status printed on every startup
3. **Safety**: Early return prevents crash if token missing
4. **Debugging**: Clear error messages indicate exactly what's missing

---

## 📞 Get WhatsApp Credentials

### WhatsApp Access Token
1. Go to: https://developers.facebook.com/apps/
2. Select your app → WhatsApp → API Setup
3. Copy "Temporary access token" (or generate permanent)

### Phone Number ID
1. Same page (WhatsApp → API Setup)
2. Find "Phone number ID"
3. Copy the numeric ID

---

**Status**: ✅ Configuration simplified and pushed to GitHub (commit `0e280eb`)

**Next**: Deploy from Cloud Shell and verify configuration logs
