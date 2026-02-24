#!/usr/bin/env bash
# Fix "Permission artifactregistry.repositories.uploadArtifacts denied".
# Grants the specific permission artifactregistry.repositories.uploadArtifacts (via custom role)
# and roles/artifactregistry.writer. Run: export PROJECT_ID=cognispace REGION=europe-central2 && ./scripts/setup-artifact-registry.sh
set -e
if [ -z "$PROJECT_ID" ] || [ -z "$REGION" ]; then
  echo "Usage: export PROJECT_ID=cognispace REGION=europe-central2 && ./scripts/setup-artifact-registry.sh"
  exit 1
fi
ACCOUNT=$(gcloud config get-value account 2>/dev/null)
if [ -z "$ACCOUNT" ]; then
  echo "Run: gcloud auth login"
  exit 1
fi
echo "Project: $PROJECT_ID  Region: $REGION  Account: $ACCOUNT"
echo "Creating repository procureiq (ignore error if it exists)..."
gcloud artifacts repositories create procureiq \
  --repository-format=docker \
  --location="$REGION" \
  --project="$PROJECT_ID" 2>/dev/null || true

# Custom role with only artifactregistry.repositories.uploadArtifacts (create if not exists)
CUSTOM_ROLE_ID="ArtifactRegistryUploadOnly"
echo "Creating custom role with permission artifactregistry.repositories.uploadArtifacts..."
gcloud iam roles create "$CUSTOM_ROLE_ID" \
  --project="$PROJECT_ID" \
  --title="Artifact Registry upload artifacts only" \
  --permissions=artifactregistry.repositories.uploadArtifacts \
  --stage=GA 2>/dev/null || true
CUSTOM_ROLE="projects/$PROJECT_ID/roles/$CUSTOM_ROLE_ID"

echo "Granting $ACCOUNT permission artifactregistry.repositories.uploadArtifacts (project)..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="user:$ACCOUNT" \
  --role="$CUSTOM_ROLE"
echo "Granting $ACCOUNT permission on repository procureiq..."
gcloud artifacts repositories add-iam-policy-binding procureiq \
  --location="$REGION" \
  --project="$PROJECT_ID" \
  --member="user:$ACCOUNT" \
  --role="$CUSTOM_ROLE"

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
CB_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"
echo "Granting Cloud Build ($CB_SA) permission artifactregistry.repositories.uploadArtifacts..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${CB_SA}" \
  --role="$CUSTOM_ROLE"

echo "Re-authenticating Docker with Artifact Registry..."
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
echo ""
echo "Done. IMPORTANT: run the build in THIS project so Cloud Build can push:"
echo "  gcloud config set project $PROJECT_ID"
echo "  gcloud builds submit --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/procureiq/api ."
