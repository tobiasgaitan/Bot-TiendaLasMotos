# 🔧 CRITICAL FIX: Environment Variable Configuration

## ✅ Issue Resolved: Cloud Run Crash

**Error**: `Illegal header value b'Bearer '`

**Root Cause**: Environment variable names in Cloud Run didn't match config.py field names

---

## 🎯 Changes Made

### 1. **Fixed `app/core/config.py`**

Updated to use **Pydantic Field aliases** matching Cloud Run environment variables:

```python
class Settings(BaseSettings):
    # WhatsApp Configuration
    webhook_verify_token: str = Field(default="motos2026", alias="WEBHOOK_VERIFY_TOKEN")
    whatsapp_token: str = Field(default="", alias="WHATSAPP_TOKEN")
    phone_number_id: str = Field(default="", alias="PHONE_NUMBER_ID")
    
    class Config:
        populate_by_name = True  # Allow both field name and alias
```

**Key Changes**:
- ✅ `whatsapp_access_token` → `whatsapp_token` (alias: `WHATSAPP_TOKEN`)
- ✅ `whatsapp_phone_number_id` → `phone_number_id` (alias: `PHONE_NUMBER_ID`)
- ✅ Added `populate_by_name=True` for flexibility

---

### 2. **Added Token Validation in `app/routers/whatsapp.py`**

Added **CRITICAL validation** before WhatsApp API calls:

```python
# CRITICAL: Validate token before making request
if not settings.whatsapp_token or settings.whatsapp_token.strip() == "":
    logger.critical("❌ CRITICAL: WHATSAPP_TOKEN IS MISSING OR EMPTY!")
    logger.critical(f"Token value: '{settings.whatsapp_token}'")
    logger.critical("Please set WHATSAPP_TOKEN environment variable in Cloud Run")
    raise ValueError("WhatsApp token is not configured")

if not settings.phone_number_id or settings.phone_number_id.strip() == "":
    logger.critical("❌ CRITICAL: PHONE_NUMBER_ID IS MISSING OR EMPTY!")
    logger.critical(f"Phone Number ID value: '{settings.phone_number_id}'")
    logger.critical("Please set PHONE_NUMBER_ID environment variable in Cloud Run")
    raise ValueError("Phone Number ID is not configured")
```

**Benefits**:
- ✅ Prevents crash with empty token
- ✅ Logs detailed error message for debugging
- ✅ Clearly indicates which environment variable is missing

---

### 3. **Updated `.env.example`**

Standardized environment variable names:

```bash
# WhatsApp API Configuration
WHATSAPP_TOKEN=your_whatsapp_access_token_here
PHONE_NUMBER_ID=your_phone_number_id_here
WEBHOOK_VERIFY_TOKEN=motos2026
```

---

## 🚀 Deployment Commands

### Update Cloud Run Environment Variables

Run this in Cloud Shell to set the correct environment variables:

```bash
gcloud run services update bot-tiendalasmotos \
  --region=us-central1 \
  --set-env-vars="WHATSAPP_TOKEN=YOUR_ACTUAL_TOKEN,PHONE_NUMBER_ID=YOUR_ACTUAL_PHONE_ID,WEBHOOK_VERIFY_TOKEN=motos2026"
```

**Replace**:
- `YOUR_ACTUAL_TOKEN` with your WhatsApp Access Token from Meta
- `YOUR_ACTUAL_PHONE_ID` with your Phone Number ID from Meta

---

### Verify Environment Variables

Check current environment variables:

```bash
gcloud run services describe bot-tiendalasmotos \
  --region=us-central1 \
  --format="value(spec.template.spec.containers[0].env)"
```

---

### Redeploy Application

After updating environment variables, redeploy:

```bash
cd ~/Bot-TiendaLasMotos
git pull origin main
./deploy.sh
```

---

## 🔍 Verification Steps

### 1. Check Logs for Token Validation

After deployment, send a test message and check logs:

```bash
gcloud run services logs read bot-tiendalasmotos --limit=50
```

**Look for**:
- ✅ `📤 Sending message to [phone] via WhatsApp API` (token is valid)
- ❌ `CRITICAL: WHATSAPP_TOKEN IS MISSING OR EMPTY!` (token not set)

---

### 2. Test Message Flow

Send a WhatsApp message to your bot and verify:

1. **Message Received**: `📨 WhatsApp message received`
2. **Routing**: `💰 Routing to MotorFinanciero` (or other service)
3. **Token Validation**: No CRITICAL errors about missing token
4. **API Call**: `📤 Sending message to...`
5. **Success**: `✅ Message sent successfully`

---

## 📊 Environment Variable Mapping

| Cloud Run Env Var | Config Field | Usage |
|-------------------|--------------|-------|
| `WHATSAPP_TOKEN` | `whatsapp_token` | WhatsApp API Bearer token |
| `PHONE_NUMBER_ID` | `phone_number_id` | WhatsApp Phone Number ID |
| `WEBHOOK_VERIFY_TOKEN` | `webhook_verify_token` | Webhook verification |
| `GCP_PROJECT_ID` | `gcp_project_id` | Google Cloud Project |
| `SECRET_NAME` | `secret_name` | Firebase credentials secret |
| `STORAGE_BUCKET` | `storage_bucket` | Cloud Storage bucket |

---

## 🆘 Troubleshooting

### Error: "WHATSAPP_TOKEN IS MISSING OR EMPTY"

**Solution**:
```bash
# Set the environment variable
gcloud run services update bot-tiendalasmotos \
  --region=us-central1 \
  --set-env-vars="WHATSAPP_TOKEN=EAAxxxxx..."
```

### Error: "PHONE_NUMBER_ID IS MISSING OR EMPTY"

**Solution**:
```bash
# Set the environment variable
gcloud run services update bot-tiendalasmotos \
  --region=us-central1 \
  --set-env-vars="PHONE_NUMBER_ID=123456789"
```

### Error: "Illegal header value b'Bearer '"

**Cause**: Token is empty string
**Solution**: Set `WHATSAPP_TOKEN` environment variable (see above)

---

## ✅ Commit Pushed to GitHub

**Repository**: https://github.com/tobiasgaitan/Bot-TiendaLasMotos

**Commit**: `89aeb80` - "fix: Correct environment variable names and add token validation"

---

## 🎯 Next Steps

1. **Get WhatsApp Credentials** from Meta Business Manager
2. **Set Environment Variables** in Cloud Run (command above)
3. **Redeploy** from Cloud Shell
4. **Test** with real WhatsApp message
5. **Verify** logs show successful message sending

---

## 📞 Where to Get WhatsApp Credentials

### WhatsApp Access Token (`WHATSAPP_TOKEN`)
1. Go to: https://developers.facebook.com/apps/
2. Select your app
3. WhatsApp → API Setup
4. Copy "Temporary access token" (or generate permanent token)

### Phone Number ID (`PHONE_NUMBER_ID`)
1. Same page as above (WhatsApp → API Setup)
2. Find "Phone number ID" field
3. Copy the numeric ID

---

**Status**: ✅ Configuration fixed and pushed to GitHub
**Action Required**: Set environment variables in Cloud Run and redeploy
