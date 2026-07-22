#!/bin/bash
echo "🔑 Activating Service Account..."
gcloud auth activate-service-account --key-file=deploy-key.json
gcloud config set project tiendalasmotos
echo "🚀 Deploying to Cloud Run..."
uvx google-agents-cli run deploy bot-tiendalasmotos --source . --region us-central1 --allow-unauthenticated

# [BOT-PLAN-CICD-IAM-205] El bloque de grant IAM fue ERRADICADO: apuntaba a la SA
# compute default mientras prod corre con SA personalizada, y era redundante — ambas
# runtime SAs ya heredan roles/secretmanager.secretAccessor a NIVEL PROYECTO.
# IAM es estado de infraestructura: se provisiona out-of-band, no en cada deploy.
# Runbook (ÚNICAMENTE si se recrea el secreto o se adopta una runtime SA nueva):
#   gcloud secrets add-iam-policy-binding WHATSAPP_TOKEN --project tiendalasmotos \
#     --member="serviceAccount:<RUNTIME_SA>" --role="roles/secretmanager.secretAccessor"
# Runtime SAs vigentes: prod = bot-admin@tiendalasmotos.iam.gserviceaccount.com ·
# beta = <PROJECT_NUMBER>-compute@developer.gserviceaccount.com
# Deploy SA (github-actions-deploy@): secretAccessor a nivel RECURSO (bootstrap 205 aplicado).
echo "🔐 Binding WHATSAPP_TOKEN desde Secret Manager (versión pineada)..."

TOKEN_VERSION=$(gcloud secrets versions list WHATSAPP_TOKEN \
  --project tiendalasmotos \
  --filter="state=ENABLED" \
  --sort-by="~createTime" \
  --limit=1 \
  --format="value(name)" | awk -F/ '{print $NF}')
if [ -z "$TOKEN_VERSION" ]; then
  echo "❌ FORENSIC: secreto WHATSAPP_TOKEN sin versiones ENABLED en tiendalasmotos."
  echo "   Bootstrap: printf '%s' '<system-user-token>' | gcloud secrets versions add WHATSAPP_TOKEN --data-file=-"
  exit 1
fi
echo "🔑 Binding WHATSAPP_TOKEN=WHATSAPP_TOKEN:${TOKEN_VERSION}"
gcloud run services update bot-tiendalasmotos \
  --region us-central1 \
  --project tiendalasmotos \
  --update-secrets="WHATSAPP_TOKEN=WHATSAPP_TOKEN:${TOKEN_VERSION}" || {
  echo "❌ FORENSIC: fallo --update-secrets en bot-tiendalasmotos (revisar IAM de la SA de runtime y existencia del servicio)"; exit 1; }
echo "✅ Deploy completado: WHATSAPP_TOKEN respaldado por Secret Manager."
