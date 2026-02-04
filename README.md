# Tienda Las Motos - WhatsApp Bot Backend

FastAPI backend for motorcycle sales automation via WhatsApp.

## Features

- **Secret Manager Integration**: Secure credential management
- **Firestore Configuration**: Dynamic config loading (financiera, aliados)
- **Catalog Management**: In-memory motorcycle catalog with category filtering
- **Cloud Storage**: Infrastructure ready for document uploads
- **WhatsApp Webhook**: Meta verification and message reception

## Project Structure

```
Bot-TiendaLasMotos/
├── app/
│   ├── core/           # Configuration and security
│   ├── services/       # Business logic services
│   ├── routers/        # API endpoints
│   └── main.py         # Application entry point
├── requirements.txt
├── Dockerfile
└── .env.example
```

## Local Development

1. **Set up environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run locally**:
   ```bash
   uvicorn app.main:app --reload --port 8080
   ```

4. **Access API**:
   - API: http://localhost:8080
   - Docs: http://localhost:8080/docs
   - Health: http://localhost:8080/health

## Docker Deployment

1. **Build image**:
   ```bash
   docker build -t bot-tiendalasmotos .
   ```

2. **Run container**:
   ```bash
   docker run -p 8080:8080 bot-tiendalasmotos
   ```

## Cloud Run Deployment

```bash
gcloud run deploy bot-tiendalasmotos \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --project tiendalasmotos
```

## API Endpoints

- `GET /` - Root endpoint
- `GET /health` - Health check
- `GET /webhook` - WhatsApp verification
- `POST /webhook` - WhatsApp message reception

## Environment Variables

- `GCP_PROJECT_ID` - Google Cloud Project ID
- `SECRET_NAME` - Secret Manager secret name
- `STORAGE_BUCKET` - Cloud Storage bucket name
- `WEBHOOK_VERIFY_TOKEN` - WhatsApp verification token
- `PORT` - Server port (default: 8080)

## Security

- Credentials retrieved from Secret Manager (never stored locally)
- Non-root Docker user
- Input validation with Pydantic
- Secure webhook verification

## Version

1.0.0 - Phase 1 (Webhook Infrastructure)
