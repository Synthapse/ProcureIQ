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

### 4. Seed sample data
```bash
python -m app.data.seed
```

### 5. Run the API
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

Nodes: `Supplier`, `Contract`, `ContractLine`, `ContractObligation`, `Invoice`, `Tenant`

Relationships:
- `(Supplier)-[:HAS_CONTRACT]->(Contract)`
- `(Contract)-[:HAS_LINE]->(ContractLine)`
- `(Contract)-[:HAS_OBLIGATION]->(ContractObligation)`
- `(Invoice)-[:RELATES_TO_CONTRACT]->(Contract)`

## Running Tests

```bash
pytest tests/ -v
```
