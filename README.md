# ProcureIQ

AI-powered procurement intelligence platform that combines **graph analytics** (Neo4j) with **generative AI** (LangChain + DigitalOcean Gradient) to help organisations understand vendor risk, contract exposure, and renewal impact.

## Architecture

```
User → FastAPI → LangChain Agent (DigitalOcean Gradient LLM)
                      ↓
             Tool-calling (ReAct)
                      ↓
          Neo4j Graph Database
          (Supplier → Contract → Obligation)
```

## Quick Start

### 1. Start Neo4j
```bash
docker-compose up neo4j -d
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env with your DigitalOcean Gradient API key
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the API
```bash
uvicorn app.main:app --reload
```

Visit http://localhost:8000/docs for the interactive API documentation.

## Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/chat/` | Natural language procurement Q&A |
| POST | `/api/v1/graph/vendor-risk` | Vendor risk profile |
| POST | `/api/v1/graph/renewal-impact` | Expiring contracts analysis |
| POST | `/api/v1/graph/contract-dependencies` | Contract dependency graph |
| GET | `/api/v1/graph/suppliers` | List suppliers |
| GET | `/api/v1/graph/contracts` | List contracts |
| GET | `/api/v1/graph/top-risk-suppliers` | Highest-risk vendors |

## Example Questions (Chat API)

```json
{ "question": "Which vendors create the highest termination risk next quarter?" }
{ "question": "What is the risk profile of TechFlow Solutions?" }
{ "question": "Which contracts are expiring in the next 90 days?" }
```

## Graph Data Model

Nodes: `Supplier`, `Contract`, `ContractLine`, `ContractObligation`, `Invoice`, `Tenant`, `User`, `Conversation`, `Message`

Relationships:
- `(Supplier)-[:HAS_CONTRACT]->(Contract)`
- `(Contract)-[:HAS_LINE]->(ContractLine)`
- `(Contract)-[:HAS_OBLIGATION]->(ContractObligation)`
- `(Invoice)-[:RELATES_TO_CONTRACT]->(Contract)`
- `(User)-[:HAS_CONVERSATION]->(Conversation)-[:HAS_MESSAGE]->(Message)` (chat history)

## Running Tests

```bash
pytest tests/ -v
```

## Deploy to Google Cloud Run

The app listens on `PORT` (default 8080), so it runs on Cloud Run as-is.

### 1. Prerequisites

- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) (`gcloud`) installed and logged in
- A GCP project with Cloud Run and Artifact Registry enabled

**Artifact Registry:** Create the repo and grant yourself (and Cloud Build) permission to push:

```bash
export PROJECT_ID=your-gcp-project-id   # e.g. cognispace
export REGION=us-central1               # e.g. europe-central2

# Create Docker repository (if it doesn't exist)
gcloud artifacts repositories create procureiq \
  --repository-format=docker \
  --location=${REGION} \
  --project=${PROJECT_ID}

# Grant your user Artifact Registry Admin (so you can push)
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="user:YOUR_EMAIL@gmail.com" \
  --role="roles/artifactregistry.admin"

# Grant Cloud Build service account (for gcloud builds submit)
PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format='value(projectNumber)')
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/artifactregistry.admin"
```

Replace `YOUR_EMAIL@gmail.com` with the account from `gcloud auth list`.

**If you get "Permission denied" when pushing:**

1. Run the setup script (grants your user + Cloud Build SA, and repository-level access):

```bash
export PROJECT_ID=cognispace
export REGION=europe-central2
chmod +x scripts/setup-artifact-registry.sh
./scripts/setup-artifact-registry.sh
```

2. **Use Cloud Build to build and push** (don’t use local `docker build` + `docker push`). Cloud Build pushes the image with its service account, which the script grants:

```bash
gcloud config set project ${PROJECT_ID}
gcloud builds submit --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/procureiq/api .
```

3. Wait ~2 minutes for IAM to propagate, then run the command in step 2 again if it failed once.

### 2. Build and push the image

**The build must run in the same GCP project as the Artifact Registry** (the project in the image tag). Otherwise Cloud Build runs in a different project and gets "uploadArtifacts denied".

```bash
# Use the project that owns the registry (e.g. cognispace)
export PROJECT_ID=cognispace
export REGION=europe-central2

gcloud config set project ${PROJECT_ID}
gcloud auth configure-docker ${REGION}-docker.pkg.dev

# Build and push (Cloud Build runs in PROJECT_ID and pushes to its Artifact Registry)
gcloud builds submit --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/procureiq/api .
```

### 3. Deploy with your `.env` (recommended)

To make the same variables from your local `.env` available on Cloud Run:

```bash
# From the project root, with PROJECT_ID and REGION set (see step 2)
chmod +x scripts/deploy-cloudrun.sh
./scripts/deploy-cloudrun.sh
```

The script converts `.env` to the format Cloud Run expects and deploys with `--env-vars-file`, so every variable in `.env` (NEO4J_URI, OPENAI_API_KEY, DO_KB_RETRIEVE_URL, etc.) is available to the app there—same as in `config.py` locally.

**One-off without the script:** generate the env file and deploy manually:

```bash
python3 scripts/env-to-yaml.py .env > env.yaml
gcloud run deploy procureiq \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/procureiq/api \
  --region ${REGION} \
  --allow-unauthenticated \
  --env-vars-file env.yaml
rm env.yaml
```

### 4. Deploy to Cloud Run (manual env vars)

All configuration is via environment variables (same as `.env` locally). Set them with `--set-env-vars` or `--set-secrets` (recommended for keys).

**Env vars (from `.env.example`):**

| Variable | Required | Description |
|----------|----------|-------------|
| `NEO4J_URI` | ✅ | Neo4j connection URI (e.g. `bolt+s://xxx.databases.neo4j.io`) |
| `NEO4J_USER` | ✅ | Neo4j user |
| `NEO4J_PASSWORD` | ✅ | Neo4j password |
| `OPENAI_API_KEY` | one of | OpenAI API key (if using OpenAI LLM) |
| `DO_INFERENCE_ACCESS_KEY` | one of | DO Inference key (if using DO Inference LLM) |
| `DO_GRADIENT_API_KEY` | one of | DO Gradient key (if using Gradient LLM) |
| `DO_API_TOKEN` | for KB | DO API token (GenAI:read) for Knowledge Base |
| `DO_KB_RETRIEVE_URL` | for KB | kbaas retrieve URL (e.g. `https://kbaas.do-ai.run/v1/<uuid>/retrieve`) |
| `DO_AGENT_URL` | optional | DO hosted agent URL |
| `DO_AGENT_ACCESS_KEY` | optional | DO agent access key |
| `APP_ENV` | | e.g. `production` |
| `LOG_LEVEL` | | e.g. `INFO` |

**Deploy with env vars (replace values):**

```bash
gcloud run deploy procureiq \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/procureiq/api \
  --region ${REGION} \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars "NEO4J_URI=bolt+s://YOUR_NEO4J,NEO4J_USER=neo4j,NEO4J_PASSWORD=YOUR_PASSWORD,OPENAI_API_KEY=YOUR_OPENAI_KEY,DO_KB_RETRIEVE_URL=https://kbaas.do-ai.run/v1/YOUR_KB_UUID/retrieve,DO_API_TOKEN=YOUR_DO_TOKEN,APP_ENV=production,LOG_LEVEL=INFO"
```

**Deploy with Secret Manager (recommended for production):**

Create secrets in [Secret Manager](https://console.cloud.google.com/security/secret-manager), then:

```bash
gcloud run deploy procureiq \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/procureiq/api \
  --region ${REGION} \
  --set-env-vars "NEO4J_URI=bolt+s://YOUR_NEO4J,NEO4J_USER=neo4j,DO_KB_RETRIEVE_URL=https://kbaas.do-ai.run/v1/YOUR_KB_UUID/retrieve,APP_ENV=production,LOG_LEVEL=INFO" \
  --set-secrets "NEO4J_PASSWORD=neo4j-password:latest,OPENAI_API_KEY=openai-key:latest,DO_API_TOKEN=do-api-token:latest"
```

### 5. Get the URL

After deploy, `gcloud run services describe procureiq --region ${REGION}` shows the service URL, or open [Cloud Run](https://console.cloud.google.com/run) in the console.


gcloud artifacts repositories create procureiq \
  --repository-format=docker \
  --location=europe-central2 \
  --project=cognispace

  gcloud projects add-iam-policy-binding cognispace \
  --member="user:YOUR_EMAIL@domain.com" \
  --role="roles/artifactregistry.writer"

gcloud auth configure-docker ${REGION}-docker.pkg.dev
gcloud builds submit --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/procureiq/api .

chmod +x scripts/deploy-cloudrun.sh
./scripts/deploy-cloudrun.sh