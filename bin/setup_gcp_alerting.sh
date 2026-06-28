#!/usr/bin/env bash
# ==============================================================================
# Script de Configuración de Alertas Asíncronas en GCP (Ticket BOT-INFRA-ALERT-080)
# ==============================================================================
# Este script configura de forma declarativa e inmutable:
#   1. El Tópico de Alertas principal y su respectivo Dead Letter Topic (DLT).
#   2. El Log Sink nativo de Cloud Logging filtrando CATALOG_VALIDATION_FAIL
#      y errores críticos de _firestore_io con severidad >= ERROR.
#   3. Suscripción Push blindada con Exponential Backoff y despacho al Webhook.
# ==============================================================================

set -euo pipefail

PROJECT_ID="tiendalasmotos"
TOPIC_NAME="log-alerts-topic"
DLT_NAME="log-alerts-dlt"
SINK_NAME="log-alerts-sink"
SUBSCRIPTION_NAME="log-alerts-webhook-sub"
WEBHOOK_ENDPOINT="https://api.tiendalasmotos.com/v1/alerts/webhook"

echo "🚀 Iniciando configuración de infraestructura de alertas en GCP para el proyecto '$PROJECT_ID'..."

# 1. Crear Tópico de Alertas y su respectivo Dead Letter Topic (DLT) para aislamiento forense
echo "Creating Pub/Sub topics..."
gcloud pubsub topics create "$TOPIC_NAME" --project="$PROJECT_ID" || echo "Topic $TOPIC_NAME already exists."
gcloud pubsub topics create "$DLT_NAME" --project="$PROJECT_ID" || echo "Topic $DLT_NAME already exists."

# 2. Crear el Log Sink con filtro calibrado para evitar falsos positivos de I/O
echo "Creating Log Sink..."
gcloud logging sinks create "$SINK_NAME" \
  "pubsub.googleapis.com/projects/$PROJECT_ID/topics/$TOPIC_NAME" \
  --log-filter='resource.type="cloud_run_revision" AND (textPayload:"CATALOG_VALIDATION_FAIL" OR (severity>=ERROR AND textPayload:"_firestore_io"))' \
  --project="$PROJECT_ID" || echo "Log Sink $SINK_NAME already exists/updated."

# 3. Dar permisos de publicación al Service Account del Sink
echo "Binding IAM policy for Log Sink Service Account..."
SINK_SA=$(gcloud logging sinks describe "$SINK_NAME" --project="$PROJECT_ID" --format="value(writerIdentity)")
gcloud pubsub topics add-iam-policy-binding "$TOPIC_NAME" \
  --member="$SINK_SA" \
  --role="roles/pubsub.publisher" \
  --project="$PROJECT_ID"

# 4. Crear la suscripción push blindada con ACK Deadline extendido y Dead Letter Topic
echo "Creating Pub/Sub subscription with Backoff and DLT..."
gcloud pubsub subscriptions create "$SUBSCRIPTION_NAME" \
  --topic="$TOPIC_NAME" \
  --push-endpoint="$WEBHOOK_ENDPOINT" \
  --ack-deadline=60 \
  --min-retry-delay=10s \
  --max-retry-delay=600s \
  --dead-letter-topic="$DLT_NAME" \
  --project="$PROJECT_ID" || echo "Subscription $SUBSCRIPTION_NAME already exists."

echo "✅ Configuración de infraestructura completada con éxito."
