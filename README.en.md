# LangChain DG

**Enterprise Contract Lifecycle AI Agent Platform**

> An AI Agent platform for enterprise contract lifecycle management, covering document intelligence, risk review, human-in-the-loop approval, version tracking, counterparty-revised contract diff, negotiation assistance and contract delivery — powered by LangGraph, RAG and policy-aware workflows.

---

## Overview

LangChain DG is an **Enterprise Contract Lifecycle AI Agent Platform**. It is built around the full contract business loop: upload → document structuring → risk review → human approval → new version → counterparty-revised diff → negotiation assistance → contract delivery.

The platform follows a **Workflow First, Agent Second** philosophy that decouples deterministic business logic from LLM reasoning nodes. **LangGraph** drives agent workflows and resumable execution, **PostgreSQL** holds business state, and shared capabilities such as **RAG / ContractPolicy / MCP / OSS** form the foundation of an Agent Application built for real business processes.

> The repository's earlier positioning — a "multi-agent chat app / enterprise knowledge-base Q&A" — has evolved. **Contract is the primary product line.** The enterprise Knowledge product has been retired; its reusable retrieval / embedding / pgvector capabilities remain as shared infrastructure. The Interview Agent is kept as an independent product line, but it is no longer the project's focus.

### Status Legend

Every capability is tagged so planned work is never mistaken for something shipped:

| Tag | Meaning |
|-----|---------|
| **Available** | Implemented and runnable |
| **In Progress** | Architecture settled, under development |
| **Planned** | On the roadmap, not yet started |

---

## Features

### Contract Domain & Versioning — Available

- **Customer / Contract / ContractVersion** domain entities and application services
- **Append-only version model**: the `Contract ID` is stable while `V1 / V2 / V3` are full snapshots; history is never overwritten
- **Contract ownership and user isolation**: every query is scoped by `user_id`
- **Version numbering and history tracking**: monotonic version numbers with a unique `(contract_id, number)` constraint
- Full CRUD APIs for customers, contracts and contract versions

### Document Intelligence — In Progress

- PDF / Markdown / TXT parsing plus a clean-and-chunk pipeline
- Embedding ingestion into pgvector for retrieval
- **Structured `ContractClause` extraction** is being integrated as the input to the review workflow

### AI Risk Review — Planned

- **Review Workflow** for contract clauses
- **RiskFinding**: structured risk output
- **ContractPolicy / RAG context**: enterprise policies and historical contracts as retrieval context
- Pydantic structured output to constrain LLM decisions

### Human-in-the-loop — Planned

- AI never overwrites a contract directly; risks are first turned into a **Revision Proposal**
- A human **accepts / rejects / edits**, which produces a **new ContractVersion**
- Explicit principle: **AI suggestion ≠ final business decision**

### Contract Diff & Negotiation — Planned

- **Diff Engine**: `previous version + current version → structured changes`
- **Negotiation Agent**: revision suggestions and talking points grounded in the diff and ContractPolicy

### Agent Runtime — Available

- **LangGraph** state graphs and resumable execution
- **PostgreSQL Checkpoint** for agent runtime state, supporting interrupt / resume
- **SSE streaming** with a pre-graph Context Builder that prepares History / Memory / RAG context in parallel
- **Context Builder** under `runtime/context`

### Platform Capabilities — Available

- **PostgreSQL + pgvector** for business data, vectors and checkpoints
- **RAG**: embedding / rerank / retrieval planner
- **Memory**: short-term conversation compression plus an asynchronous long-term Memory Agent
- **MCP**: external tool integration
- **OSS**: Alibaba Cloud Object Storage adapter
- **Redis / Docker / Nginx** for deployment and infrastructure

---

## Architecture

### Layered View

```
                            React (SPA)
                                │
                                ▼
                        FastAPI (HTTP / SSE)
                                │
                                ▼
                    Contract Application Layer
        ┌───────────────────────┼────────────────────────┐
        ▼                       ▼                        ▼
     Domain                  Workflow                  Agents
 (entities / rules)     (deterministic)      (reasoning / planning / risk)
        └───────────────────────┼────────────────────────┘
                                ▼
                    Agent Runtime / LangGraph
                                │
        ┌───────────────┬───────┴────────┬────────────────┐
        ▼               ▼                ▼                ▼
     Context          RAG           Tools / MCP      Checkpoint
  (pre-graph)      (pgvector)     (external)       (runtime state)
                                │
                                ▼
                        Infrastructure
        ┌───────────────┬───────────────┬────────────────┐
        ▼               ▼               ▼                ▼
   PostgreSQL       Redis            OSS            Document
      + pgvector   (queue/cache)  (object store)  (parse/render)
```

### Design Principles

**1. Workflow First, Agent Second**

Agents are not the whole system — workflows control the business process. LLMs and Agents are used only at nodes that genuinely need reasoning, planning, risk analysis, revision or negotiation. Deterministic operations such as CRUD, versioning, diff, parsing, storage, export and email are plain services, engines or workers.

**2. Business State vs Runtime State**

- **PostgreSQL** stores business facts: Customer, Contract, ContractVersion, ContractClause, ContractChange, RiskFinding, Policy
- **LangGraph Checkpoint** stores only agent runtime state (interrupt / resume / workflow execution)
- `ContractVersion` is never placed in, or recovered from, a checkpoint

**3. Human-in-the-loop**

AI never overwrites a contract directly:

```
RiskFinding → Revision Proposal → Human Accept / Reject / Edit → New ContractVersion
```

**4. Version-first Contract Model**

```
Customer
  └── Contract              (stable Contract ID)
        └── ContractVersion  (V1 / V2 / V3 full snapshots)
              └── ContractClause
                    ├── RiskFinding
                    └── ContractChange
```

**5. Deterministic + Agent Hybrid**

The Document Parser, Diff Engine, Version Manager, PDF Renderer and Email Worker are plain services, not Agents. Review, revision and negotiation are decision-making capabilities, and only those use Agents.

> Design decisions are recorded in [`docs/adr/`](./docs/adr): product isolation, domain separation, workflow-first, agent runtime boundary, business state vs checkpoint, durable background jobs, and the SSE transport boundary.

---

## Contract Workflow

The full contract pipeline under the target architecture:

```
   Upload PDF / Markdown
          │
          ▼
      ContractVersion                    ── Available
          │
          ▼
   Document Intelligence                 ── In Progress
          │
          ▼
     ContractClause
          │
          ▼
     Review Workflow                     ── Planned
          │
          ▼
      RiskFinding
          │
          ▼
   Revision Proposal
          │
          ▼
  Human-in-the-loop  ◄── Accept / Reject / Edit
          │
          ▼
    New ContractVersion
          │
          ▼
   Diff / Negotiation
          │
          ▼
        Export
          │
          ▼
   Email / Delivery
```

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.12, FastAPI, LangGraph, SQLAlchemy (async), Pydantic |
| Frontend | React 18, TypeScript, Vite, Ant Design |
| Data | PostgreSQL, pgvector, Redis |
| AI | RAG, embeddings, rerank, LLM, MCP |
| Infrastructure | Alibaba Cloud OSS, Docker, Docker Compose, Nginx |
| Models | DashScope (Alibaba Cloud Bailian) |
| Security | JWT + SM2 (Chinese national cryptography) |

---

## Project Structure

```
backend_langchain/
├── app/                          # FastAPI application layer
│   ├── main.py                   # App entry / lifespan
│   ├── routers/                  # HTTP routes: user / customer / contract / interview
│   ├── dependencies/             # Dependency wiring
│   ├── services/
│   │   └── document_pipeline/    # Clean / chunk / embed ingest
│   ├── auth/                     # JWT + SM2
│   ├── sse.py                    # SSE orchestration
│   └── settings.py
│
├── products/                     # Product lines (never import each other)
│   ├── contract/                 # Primary product: contract lifecycle
│   │   ├── domain/               # Contract / Customer / ContractVersion entities & errors
│   │   ├── application/          # Use-case services + ports
│   │   ├── schemas/              # API DTOs
│   │   ├── workflows/            # Reserved: review workflow (not in Phase 1)
│   │   ├── agents/               # Reserved: decision-point agents
│   │   └── policies/             # Reserved: ContractPolicy
│   └── interview/                # Additional product line: interview agent
│
├── runtime/                      # Execution mechanics (no business logic)
│   ├── execution/                # Shared State / graph factory
│   ├── context/                  # Pre-graph Context Builder
│   ├── checkpoint/               # LangGraph PostgreSQL checkpointer
│   └── streaming/                # astream → unified events
│
├── agent_platform/               # Platform ports
│   ├── agent_runtime/            # Agent runtime ports / events
│   ├── document/                 # Document processing port
│   ├── retrieval/                # Retrieval port
│   └── storage/                  # Object storage port
│
├── infrastructure/               # Shared infrastructure adapters
│   ├── db/                       # SQLAlchemy models / repositories
│   ├── rag/                      # pgvector / planner / rerank / web search
│   ├── memory/                   # Short-term compression + long-term Memory Agent
│   ├── oss/                      # Alibaba Cloud OSS adapter
│   ├── pdf/                      # PDF human confirmation + rendering
│   ├── queue/                    # JobQueue / Worker ports
│   └── mcp/                      # MCP multi-server
│
├── harness/                      # AgentRun / Trace run records
├── migrations/                   # 0001 contract schema / 0002 knowledge retire
├── knowledge/                    # docs2 (interview corpus) + retired corpus archive
├── scripts/                      # DB build / diagnostics / smoke tests
├── tests/contract/
└── env/                          # yaml config samples

frontend_langchain/
└── src/
    ├── app/routes/               # Routing (ContractRoutes)
    ├── pages/
    │   ├── contract/             # ContractListPage / ContractVersionPage
    │   └── interview/
    ├── features/
    │   ├── contract/             # api / types
    │   └── chat/
    ├── page/                     # Legacy: chat / login & register
    ├── services/                 # api / chatApi / chatStream / request
    └── utils/                    # sm2
```

---

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+
- Docker & Docker Compose
- PostgreSQL (business DB + checkpoint DB, with pgvector)

### Configure Environment Variables

```bash
cp .env.example .env
```

```bash
# Development
cp backend_langchain/env/settings_debug.example.yaml backend_langchain/env/settings_debug.yaml

# Production
cp backend_langchain/env/settings_pro.example.yaml backend_langchain/env/settings_pro.yaml
```

### Docker Deployment

```bash
docker compose up -d
```

The service is available at `http://localhost:8000` (the stack also includes PostgreSQL / pgvector, Redis and Nginx).

### Local Development

1. Install backend dependencies:

```bash
cd backend_langchain
pip install -r requirements.txt
```

2. Start the backend:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

3. Install frontend dependencies and start:

```bash
cd frontend_langchain
npm install
npm run dev
```

---

## Roadmap

- [x] Contract / Customer / ContractVersion domain foundation
- [x] Product / Runtime / Infrastructure separation
- [x] Legacy Knowledge retirement
- [x] Agent runtime (LangGraph / SSE / checkpoint / Context Builder)
- [x] Shared infrastructure (RAG / Memory / MCP / OSS / Redis / Docker)
- [ ] Contract file upload + OSS binding
- [ ] Document Intelligence → ContractClause
- [ ] Review Workflow → RiskFinding
- [ ] Revision + human-in-the-loop
- [ ] Version diff
- [ ] Negotiation Agent
- [ ] DOCX / PDF export
- [ ] Email delivery
- [ ] Durable background jobs (Queue / Worker rollout)

---

## Additional Product Lines

### Interview Agent (secondary / evolving independently)

The Interview Agent remains as an independent product line, business-isolated from Contract and sharing the underlying Runtime / RAG / Memory capabilities. Product lines must **never import each other** (see [ADR 0001](./docs/adr/0001-product-isolation.md)); they only share platform capabilities.

### Legacy Knowledge Base

The enterprise Knowledge product has been retired: `knowledge/docs1` and the old vector data are archived under `knowledge/_retired_agent_corpus/`, with the table-archive script at `migrations/0002_retire_knowledge_data.py` (run explicitly, reversible).

Note that the **Knowledge product is not the same as RAG capability**. What was retired is the knowledge-base Q&A product; its reusable retrieval / embedding / pgvector capabilities remain as shared infrastructure.

If the interview corpus still needs to be built, it lives at `backend_langchain/knowledge/docs2/<domain>/**/*.pdf`:

```bash
cd backend_langchain
python -m scripts.build_rag_knowledge --interview-only
```

---

## Configuration

Primary configuration lives in `backend_langchain/app/settings.py` plus `env/settings_*.yaml`:

- `llm_config`: LLM
- `dashscope_config`: embeddings / rerank / optional web search
- `rag_config`: retrieval and planner switches
- `postgres` / checkpoint: business DB and LangGraph session DB
- `oss_config`: Alibaba Cloud OSS
- `redis_url`: Redis

Secrets are injected into the yaml as `${VAR}` from the repository-root `.env`.

---

## License

MIT License
