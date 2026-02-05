#!/bin/bash

# Deployment script for Tienda Las Motos Backend to Cloud Run
# This script deploys the FastAPI application to Google Cloud Run

set -e  # Exit on error

# Configuration
PROJECT_ID="tiendalasmotos"
SERVICE_NAME="bot-tiendalasmotos"
REGION="us-central1"

echo "🚀 Deploying Tienda Las Motos Backend to Cloud Run..."
echo "Project: $PROJECT_ID"
echo "Service: $SERVICE_NAME"
echo "Region: $REGION"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: gcloud CLI is not installed"
    echo ""
    echo "Please install Google Cloud SDK:"
    echo "  macOS: curl https://sdk.cloud.google.com | bash"
    echo "  Or visit: https://cloud.google.com/sdk/docs/install"
    echo ""
    exit 1
fi

# Authenticate (if needed)
echo "🔐 Checking authentication..."
gcloud auth list

# Set project
echo "📋 Setting project..."
gcloud config set project $PROJECT_ID

# Deploy to Cloud Run
echo "☁️  Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --source . \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --project $PROJECT_ID \
  --timeout 300 \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 10 \
  --no-cpu-throttling

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📝 Next steps:"
echo "1. Get the service URL:"
echo "   gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)'"
echo ""
echo "2. Test the webhook verification:"
echo "   curl \"https://YOUR-SERVICE-URL/webhook?hub.mode=subscribe&hub.verify_token=motos2026&hub.challenge=test123\""
echo ""
echo "3. Configure this URL in Meta WhatsApp Business settings"
