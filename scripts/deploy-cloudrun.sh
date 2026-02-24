#!/usr/bin/env bash
# Deploy ProcureIQ to Cloud Run using variables from .env
# Prerequisites: gcloud CLI, PROJECT_ID and REGION set, image already built and pushed.
#
# Usage:
#   export PROJECT_ID=your-gcp-project
#   export REGION=us-central1
#   ./scripts/deploy-cloudrun.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

if [ -z "$PROJECT_ID" ] || [ -z "$REGION" ]; then
  echo "Set PROJECT_ID and REGION, e.g.:"
  echo "  export PROJECT_ID=my-project"
  echo "  export REGION=us-central1"
  exit 1
fi

if [ ! -f .env ]; then
  echo "No .env file. Copy .env.example to .env and fill in values."
  exit 1
fi

IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/procureiq/api"
ENV_YAML="$(mktemp)"
trap "rm -f $ENV_YAML" EXIT

echo "Converting .env to env vars file..."
python3 "$SCRIPT_DIR/env-to-yaml.py" .env > "$ENV_YAML"

echo "Deploying to Cloud Run (image: $IMAGE)..."
gcloud run deploy procureiq \
  --image "$IMAGE" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --env-vars-file "$ENV_YAML"

echo "Done. Service URL:"
gcloud run services describe procureiq --region "$REGION" --format 'value(status.url)'
