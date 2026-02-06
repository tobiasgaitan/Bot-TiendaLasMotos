# CRM Memory Integration - Deployment Guide

## 🎯 Status

**Code Status:** ✅ Ready for deployment (commit `89f559a`)  
**Production Status:** ⚠️ Awaiting deployment

---

## 📦 What's Been Updated

### 1. Memory Service (`app/services/memory_service.py`)
- ✅ Complete implementation with flexible phone matching
- ✅ Handles `+57` prefix automatically
- ✅ Updates conversation summaries

### 2. AI Brain (`app/services/ai_brain.py`)
- ✅ Accepts `prospect_data` parameter
- ✅ Injects CRM context into system prompt
- ✅ Personalizes responses with name and motorcycle interest

### 3. WhatsApp Router (`app/routers/whatsapp.py`)
- ✅ PRE-PROCESSING: Loads prospect data before AI response
- ✅ POST-PROCESSING: Updates summaries after conversation

### 4. Main App (`app/main.py`)
- ✅ Initializes memory service on startup
- ✅ Added robust error handling to prevent silent failures

---

## 🚀 Deployment Instructions

### Option 1: Deploy from Cloud Shell (Recommended)

```bash
# 1. Open Cloud Shell
# https://console.cloud.google.com/cloudshell

# 2. Navigate to project directory
cd ~/Bot-TiendaLasMotos

# 3. Pull latest changes
git pull origin main

# 4. Verify you have the latest code
git log -1 --oneline
# Should show: 89f559a feat: Add robust error handling for Memory Service initialization

# 5. Deploy to Cloud Run
./deploy.sh

# 6. Wait for deployment to complete (~2-3 minutes)
```

### Option 2: Deploy via gcloud CLI (Local)

```bash
# 1. Install gcloud CLI if not installed
# https://cloud.google.com/sdk/docs/install

# 2. Authenticate
gcloud auth login

# 3. Set project
gcloud config set project tiendalasmotos

# 4. Deploy
./deploy.sh
```

---

## 🔍 Post-Deployment Verification

### 1. Check Startup Logs

```bash
gcloud run services logs read bot-tiendalasmotos \
  --region us-central1 \
  --project tiendalasmotos \
  --limit 100
```

**Look for these messages:**
```
🧠 Initializing Memory Service...
✅ Memory Service initialized successfully
```

**If you see this instead:**
```
❌ Failed to initialize Memory Service: [error message]
⚠️  Bot will continue without CRM memory integration
```
→ Check the error message and fix the issue

### 2. Test with Capitán Victoria

**Prerequisites:**
- Firestore must have a document in `prospectos` collection:
  ```json
  {
    "celular": "3192564288",  // WITHOUT country code!
    "nombre": "Capitán Victoria",
    "motoInteres": "Victory Black",
    "ai_summary": "Cliente VIP interesado en Victory Black",
    "chatbot_status": "PENDING"
  }
  ```

**Test Steps:**
1. Send WhatsApp message from `573192564288`:
   ```
   "Hola, quiero información"
   ```

2. Check logs for memory service activity:
   ```bash
   gcloud run services logs read bot-tiendalasmotos \
     --region us-central1 \
     --project tiendalasmotos \
     --limit 50 | grep "🧠"
   ```

3. **Expected logs:**
   ```
   🔍 Searching for prospect with celular: 3192564288
   ✅ Prospect found: Capitán Victoria | Interest: Victory Black | Has summary: True
   🧠 Prospect data loaded for 573192564288: Capitán Victoria
   💾 Prospect summary updated for 573192564288
   ```

4. **Expected bot response:**
   ```
   ¡Hola Capitán Victoria! 👋 
   
   Vi que te interesa la Victory Black. ¿Sigues buscando información 
   sobre esta moto ejecutiva?
   ```

---

## 🐛 Troubleshooting

### Issue: Memory Service Not Initializing

**Symptoms:**
- No `🧠 Initializing Memory Service...` in logs
- No `✅ Memory Service initialized successfully` in logs

**Possible Causes:**
1. Old code still deployed (need to redeploy)
2. Import error in `memory_service.py`
3. Firestore permissions issue

**Solution:**
```bash
# Redeploy with verbose logging
./deploy.sh

# Check for import errors
gcloud run services logs read bot-tiendalasmotos \
  --region us-central1 \
  --project tiendalasmotos \
  --limit 200 | grep -i "error\|import"
```

### Issue: Prospect Not Found

**Symptoms:**
- Logs show: `📭 No prospect found for 3192564288`
- Bot doesn't personalize greeting

**Possible Causes:**
1. Firestore document doesn't exist
2. `celular` field has wrong format (includes country code)
3. Phone number mismatch

**Solution:**
```bash
# Check Firestore directly
# Go to: https://console.firebase.google.com/project/tiendalasmotos/firestore

# Verify document exists with:
# - Collection: prospectos
# - Field: celular = "3192564288" (NO +57 prefix!)
```

### Issue: Bot Responds But Doesn't Personalize

**Symptoms:**
- Bot responds normally
- No personalized greeting
- No `🧠 Prospect data loaded` in logs

**Possible Causes:**
1. `memory_service` is `None` (initialization failed)
2. Prospect exists but `exists` flag is `False`

**Solution:**
```bash
# Check if memory service initialized
gcloud run services logs read bot-tiendalasmotos \
  --region us-central1 \
  --project tiendalasmotos \
  --limit 200 | grep "Memory Service"

# Should see:
# ✅ Memory Service initialized successfully
```

---

## 📋 Deployment Checklist

- [ ] Pull latest code from GitHub (`git pull origin main`)
- [ ] Verify commit is `89f559a` or later
- [ ] Run `./deploy.sh` from Cloud Shell
- [ ] Wait for deployment to complete
- [ ] Check startup logs for `✅ Memory Service initialized successfully`
- [ ] Verify Firestore has Capitán Victoria's data
- [ ] Send test message from `573192564288`
- [ ] Verify personalized greeting in response
- [ ] Check logs for `🧠 Prospect data loaded`
- [ ] Verify Firestore updated with new `ai_summary`

---

## 🎓 Next Steps After Deployment

1. **Monitor Logs:**
   - Watch for memory service activity
   - Track prospect recognition rate
   - Monitor summary update success

2. **Test Edge Cases:**
   - Unknown phone numbers (should create new prospects)
   - Different phone formats (`+57`, `57`, no prefix)
   - Data extraction (name, moto interest)

3. **Populate Firestore:**
   - Add more prospect data for testing
   - Ensure `celular` field is always without country code
   - Set `chatbot_status` to `PENDING` for new prospects

---

**Status:** ✅ Code ready for deployment  
**Next Action:** Deploy from Cloud Shell using instructions above
