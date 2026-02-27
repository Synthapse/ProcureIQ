# ProcureIQ API — Business Summary

## What It Is

ProcureIQ is an **AI-powered procurement intelligence API** that helps organisations answer questions about vendors, contracts, renewals, obligations, and invoices using natural language. It combines **live graph data** (suppliers, contracts, invoices, risk scores) with **document intelligence** (policies, clauses, knowledge base) so teams get one coherent answer instead of switching between systems.

---

## Value Proposition

| For | Benefit |
|-----|--------|
| **Procurement & sourcing** | See which vendors create the most risk, which contracts are expiring, and how obligations stack up—in one conversation. |
| **Legal & compliance** | Link contract and obligation data to actual policy and clause content (e.g. “What do our policies say about these suppliers?”). |
| **Finance** | Get supplier, contract, and invoice lists with optional tenant scope for reporting and controls. |
| **Leadership** | Ask questions in plain language and receive summarised findings with clear data sources (graph vs knowledge base). |

---

## How It Works (High Level)

1. **User asks a question** (e.g. “Which vendors have the highest risk?” or “What contracts expire in the next 90 days?”).
2. **API runs an AI agent** that:
   - Pulls the right data from the **graph** (Neo4j: suppliers, contracts, obligations, invoices).
   - Optionally pulls from the **knowledge base** (policies, clauses, documents).
   - **Hybrid answers** combine both: e.g. “Here are our suppliers from the graph; here’s what our policies say about them.”
3. **Response is streamed** so the client can show progress (e.g. “Analyzing…”, “Retrieving data…”, “Generating response…”).
4. **Conversations are stored** per user and per thread, so follow-up questions stay in context.

---

## Main Capabilities

### 1. Natural language chat (primary interface)

- **Endpoint:** `POST /api/v1/chat/`
- **Input:** Question + user id (+ optional conversation id to continue a thread).
- **Output:** Server-Sent Events stream with phases (thinking, tool use, generating) and a final answer plus **metadata** (which tools were used, whether data came from graph and/or knowledge base).
- **Use:** Any procurement, risk, or compliance question that can be answered from supplier/contract/obligation/invoice data and/or the knowledge base.

### 2. Simple data access (lists)

- **Endpoints:**  
  - `GET /api/v1/data/suppliers`  
  - `GET /api/v1/data/contracts`  
  - `GET /api/v1/data/invoices`
- **Input:** Optional tenant filter and limit.
- **Output:** JSON list of records (e.g. supplier name, id, country, industry; contract title, value, end date; invoice number, amount, status).
- **Use:** Dashboards, reports, integrations, or when the client only needs raw lists.

### 3. Conversation continuity

- Each chat turn can send a **conversation_id** to continue the same thread.
- The API returns **conversation_id** in the final event so the next request can reuse it.
- **Conversations are persisted in Neo4j** (user → conversation → messages) for audit and future features.

### 4. Health and operations

- **`GET /health`** — API up.
- **`GET /health/neo4j`** — Graph database reachable.
- **`GET /health/digitalocean`** — Optional DigitalOcean agent (e.g. for knowledge base) reachable.
- **`GET /health/knowledge-base`** — Optional knowledge base (RAG) reachable.

---

## What the AI Can Answer (Examples)

- **Vendor risk:** “What is the risk profile of [vendor]?” — contracts, obligations, risk scores.
- **Renewals:** “Which contracts expire in the next 90 days?” — list, values, auto-renewal.
- **Concentration:** “Which suppliers have multiple contracts?” — concentration / blast-radius view.
- **Obligations:** “Show overdue obligations” — status, due dates, contract link.
- **Lists:** “List all suppliers / contracts / invoices” — from graph (and in chat, optionally combined with KB).
- **Hybrid (graph + knowledge base):** “What do our policies say about our current suppliers?” — supplier list + policy/clause content in one answer.

Answers include **metadata** (e.g. `tool_calls`, `data_sources`: graph and/or knowledge_base) so the business can see how the answer was built.

---

## Intended Audience

- **Product / business owners** evaluating procurement intelligence APIs.
- **Procurement, legal, and finance** teams defining requirements.
- **Integrators and partners** who need a short, accurate overview of scope and value.

For technical details (auth, request/response schemas, deployment), see the main [README](../README.md) and the interactive API docs at `/docs` when the API is running.
