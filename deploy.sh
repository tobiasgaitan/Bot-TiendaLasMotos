#!/bin/bash
echo "🔑 Activating Service Account..."
gcloud auth activate-service-account --key-file=deploy-key.json
gcloud config set project tiendalasmotos
echo "🚀 Deploying to Cloud Run..."
uvx google-agents-cli run deploy bot-tiendalasmotos --source . --region us-central1 --allow-unauthenticated
