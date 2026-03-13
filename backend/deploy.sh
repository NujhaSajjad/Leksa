#!/bin/bash
# ─────────────────────────────────────────────────
#  Leksa Backend — Cloud Run Deployment Script
#  Usage: ./deploy.sh
# ─────────────────────────────────────────────────
set -e

# ── Config (apni values dena) ─────────────────────
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-your-gcp-project-id}"
REGION="us-central1"
SERVICE_NAME="leksa-backend"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "🚀 Deploying Leksa Backend to Cloud Run..."
echo "   Project : $PROJECT_ID"
echo "   Region  : $REGION"
echo "   Image   : $IMAGE"
echo ""

# ── Step 1: Auth check ────────────────────────────
echo "1️⃣  Checking gcloud auth..."
gcloud auth print-access-token > /dev/null 2>&1 || {
    echo "❌ gcloud login karo: gcloud auth login"
    exit 1
}
gcloud config set project "$PROJECT_ID"

# ── Step 2: APIs enable karo ──────────────────────
echo "2️⃣  Enabling required APIs..."
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    containerregistry.googleapis.com \
    firestore.googleapis.com \
    --quiet

# ── Step 3: Docker build + push ───────────────────
echo "3️⃣  Building Docker image..."
docker build -t "$IMAGE" .

echo "4️⃣  Pushing to Container Registry..."
docker push "$IMAGE"

# ── Step 4: Cloud Run deploy ──────────────────────
echo "5️⃣  Deploying to Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
    --image "$IMAGE" \
    --platform managed \
    --region "$REGION" \
    --allow-unauthenticated \
    --memory 1Gi \
    --cpu 1 \
    --timeout 300 \
    --concurrency 80 \
    --set-env-vars "GEMINI_API_KEY=${GEMINI_API_KEY},GOOGLE_CLOUD_PROJECT=${PROJECT_ID},USE_FIRESTORE=true" \
    --quiet

# ── Done ──────────────────────────────────────────
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --region "$REGION" --format "value(status.url)")

echo ""
echo "✅ Deployment complete!"
echo "   Backend URL: $SERVICE_URL"
echo "   Health check: $SERVICE_URL/health"
echo ""
echo "👉 Frontend mein ye URL set karo:"
echo "   VITE_BACKEND_URL=$SERVICE_URL"
