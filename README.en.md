# LangChain DG

An AI conversational application built on LangChain, featuring intelligent Agents and an interview assistant, with support for streaming output, knowledge base retrieval, and PDF export.

## Features

- 💬 **Intelligent Conversation**: Implemented via LangGraph state flow graphs, supporting multi-turn dialogue and context memory
- 🔍 **Knowledge Base Retrieval**: RAG architecture supporting vectorized storage and retrieval of Markdown and PDF documents
- 📄 **PDF Export**: Export conversation content in PDF format
- 🔎 **Web Search**: Integrated web search capability (optional)
- 🔐 **Security Authentication**: Dual encryption with JWT + SM2 national cryptographic algorithm
- ⚡ **Streaming Response**: Real-time streaming output via Server-Sent Events (SSE)

## Technology Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.12, FastAPI, LangChain, LangGraph, SQLAlchemy (async), Chroma, Redis |
| Frontend | React 18, TypeScript, Vite, Ant Design |
| Deployment | Docker, Nginx |
| Vector Model | DashScope (Alibaba Cloud) |

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+
- Docker & Docker Compose

### Configure Environment Variables

Copy and configure the `.env.example` file:

```bash
cp backend_langchain/.env.example backend_langchain/.env
```

Select configuration files based on deployment environment:

```bash
# Development environment
cp backend_langchain/env/settings_debug.example.yaml backend_langchain/env/settings_debug.yaml

# Production environment
cp backend_langchain/env/settings_pro.example.yaml backend_langchain/env/settings_pro.yaml
```

### Docker Deployment

```bash
docker compose up -d
```

The service will be available at `http://localhost:8000`.

### Local Development

1. Install backend dependencies:

```bash
cd backend_langchain
pip install -r requirements.txt
```

2. Start the backend:

```bash
uvicorn app.main:app --reload --port 8000
```

3. Install frontend dependencies and start:

```bash
cd frontend_langchain
npm install
npm run dev
```

## Project Structure

```
backend_langchain/
├── app/                    # FastAPI application main directory
│   ├── main.py            # Application entry point
│   ├── routers/          # API routes
│   │   ├── api.py        # Super-agent HTTP API
│   │   ├── interview.py # Interview assistant interface
│   │   └── user.py      # User authentication interface
│   ├── models.py         # SQLAlchemy models
│   └── settings.py       # Configuration management
├── Langchain_Agent/       # Agent core logic
│   ├── runtime.py       # Agent runtime (graph cache, stream entry)
│   └── tools/          # Utility functions
├── Agent_memory/         # Conversation memory management
├── common/              # Common modules
│   ├── agent.py         # Base Agent components
│   ├── rag.py          # RAG retrieval
│   └── skill_router.py # Skill routing
├── MCP/                 # MCP tool integration
└── Scripts/             # Build scripts

frontend_langchain/        # React frontend
├── src/
│   ├── page/            # Page components
│   │   ├── Langchain/  # Conversation page
│   │   └── Langchain_login/  # Login and registration
│   └── services/       # API services
```

## Build Knowledge Base

### Option 1: Build inside Container

```bash
docker compose exec backend python -m Scripts.build_rag_knowledge
```

### Option 2: Build Locally

```bash
cd backend_langchain
python -m Scripts.build_rag_knowledge
```

Supports specifying domains and document types:

```python
python -m Scripts.build_rag_knowledge --agent-domains "vibe_coding" --do-interview
```

## Configuration Details

Primary configuration is located in `backend_langchain/app/settings.py`:

- `llm_config`: LLM configuration (API key, model name)
- `dashscope_config`: Alibaba Cloud DashScope configuration
- `rag_config`: RAG vector database configuration
- `redis_url`: Redis connection address

## License

MIT License