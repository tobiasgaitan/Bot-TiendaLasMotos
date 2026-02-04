# Deployment Guide - Tienda Las Motos Backend

## Prerequisites

### 1. Install Google Cloud SDK

**macOS/Linux:**
```bash
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
```

**Or download from:** https://cloud.google.com/sdk/docs/install

### 2. Authenticate with Google Cloud

```bash
gcloud auth login
gcloud auth application-default login
```

### 3. Verify Project Access

```bash
gcloud config set project tiendalasmotos
gcloud projects describe tiendalasmotos
```

## Deployment Methods

### Method 1: Using the Deployment Script (Recommended)

```bash
./deploy.sh
```

This script will:
- Check for gcloud installation
- Set the correct project
- Deploy to Cloud Run with optimized settings
- Display the service URL

### Method 2: Manual Deployment

```bash
gcloud run deploy bot-tiendalasmotos \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --project tiendalasmotos \
  --timeout 300 \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 10
```

### Method 3: Docker Build + Deploy

```bash
# Build the image
docker build -t gcr.io/tiendalasmotos/bot-tiendalasmotos .

# Push to Google Container Registry
docker push gcr.io/tiendalasmotos/bot-tiendalasmotos

# Deploy from image
gcloud run deploy bot-tiendalasmotos \
  --image gcr.io/tiendalasmotos/bot-tiendalasmotos \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --project tiendalasmotos
```

## Post-Deployment Verification

### 1. Get Service URL

```bash
gcloud run services describe bot-tiendalasmotos \
  --region us-central1 \
  --format 'value(status.url)'
```

### 2. Test Health Endpoint

```bash
curl https://YOUR-SERVICE-URL/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "Tienda Las Motos Backend",
  "version": "1.0.0",
  "catalog_items": 23,
  "storage_bucket": "tiendalasmotos-documents"
}
```

### 3. Test Webhook Verification

```bash
curl "https://YOUR-SERVICE-URL/webhook?hub.mode=subscribe&hub.verify_token=motos2026&hub.challenge=test123"
```

Expected response: `test123`

### 4. View Logs

```bash
gcloud run services logs read bot-tiendalasmotos \
  --region us-central1 \
  --limit 50
```

Look for:
- ✅ Firebase credentials retrieved successfully
- ✅ Financial config loaded
- ✅ Partners config loaded
- ✅ Catalog loaded: X items
- ✅ Cloud Storage initialized successfully

## Configure WhatsApp Webhook

1. Go to Meta for Developers: https://developers.facebook.com
2. Navigate to your WhatsApp Business App
3. Go to WhatsApp > Configuration
4. Set Webhook URL: `https://YOUR-SERVICE-URL/webhook`
5. Set Verify Token: `motos2026`
6. Subscribe to message events

## Troubleshooting

### Issue: "Permission denied" during deployment

**Solution:**
```bash
gcloud auth login
gcloud config set project tiendalasmotos
```

### Issue: "Secret not found"

**Solution:** Verify the secret exists:
```bash
gcloud secrets describe FIREBASE_CREDENTIALS --project tiendalasmotos
```

### Issue: Service fails to start

**Solution:** Check logs:
```bash
gcloud run services logs read bot-tiendalasmotos --region us-central1 --limit 100
```

### Issue: Firestore connection fails

**Solution:** Verify service account permissions:
- Cloud Run service account needs `roles/datastore.user`
- Check IAM permissions in GCP Console

## Environment Variables (Optional Override)

To override default environment variables:

```bash
gcloud run deploy bot-tiendalasmotos \
  --source . \
  --set-env-vars "WEBHOOK_VERIFY_TOKEN=custom-token,STORAGE_BUCKET=custom-bucket" \
  --region us-central1 \
  --project tiendalasmotos
```

## Monitoring

### View Service Details

```bash
gcloud run services describe bot-tiendalasmotos --region us-central1
```

### Monitor Metrics

Visit Cloud Console:
https://console.cloud.google.com/run/detail/us-central1/bot-tiendalasmotos/metrics

## Updating the Service

To deploy updates:

```bash
./deploy.sh
```

Or manually:

```bash
gcloud run deploy bot-tiendalasmotos --source . --region us-central1
```

## Rollback

To rollback to a previous revision:

```bash
# List revisions
gcloud run revisions list --service bot-tiendalasmotos --region us-central1

# Rollback to specific revision
gcloud run services update-traffic bot-tiendalasmotos \
  --to-revisions REVISION-NAME=100 \
  --region us-central1
```
