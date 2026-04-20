# LangChain AI Assistant Backend Service

A backend service for AI assistants built on Django + LangChain, providing conversational AI programming and interview assistance features.

## Project Overview

This project is a production-grade AI conversational system with a frontend-backend separated architecture:

- **Backend**: Django + LangChain + Chroma vector database
- **Frontend**: React + TypeScript + Ant Design
- **Deployment**: Docker + Nginx

### Core Features

1. **AI Programming Assistant** - RAG-based intelligent programming Q&A
   - AI programming knowledge base retrieval
   - Openclaw knowledge retrieval
   - Vibecoding knowledge retrieval
   - Interview study material retrieval

2. **AI Interview Assistant** - Technical interview coaching
   - AI/LLM interview knowledge
   - Java interview question bank
   - Vue interview question bank

3. **User System**
   - User registration/login
   - JWT authentication
   - SM2 national cryptography encryption
   - Conversation history management

## Technology Stack

### Backend
- Python 3.10
- Django 4.x
- LangChain
- Chroma (vector database)
- Qwen (Tongyi Qianwen large model)
- Redis
- SQLite (checkpointer)

### Frontend
- React 18
- TypeScript
- Ant Design
- Vite

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- Docker & Docker Compose (optional)

### Backend Configuration

1. Create a virtual environment:
```bash
cd backend_langchain
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or venv\Scripts\activate  # Windows
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables:
```bash
cp .env.example .env
# Edit the .env file to configure required environment variables
```

4. Run database migrations:
```bash
python manage.py migrate
```

5. Start the development server:
```bash
python manage.py runserver 0.0.0.0:8000
```

### Frontend Configuration

1. Install dependencies:
```bash
cd frontend_langchain
npm install
```

2. Start the development server:
```bash
npm run dev
```

### Docker Deployment

```bash
docker-compose up -d
```

## Project Structure

```
├── backend_langchain/          # Django backend
│   ├── Langchain_Agent/        # AI Programming Assistant module
│   ├── Langchain_Agent1/       # AI Interview Assistant module
│   ├── User/                   # User module
│   ├── common/                 # Common components
│   │   ├── agent.py           # Agent core logic
│   │   ├── embedding.py       # Vector embeddings
│   │   └── skill_router.py    # Skill routing
│   ├── config/                 # Configuration module
│   ├── env/                    # Environment configuration
│   └── Scripts/                # Knowledge base construction scripts
├── frontend_langchain/         # React frontend
│   └── src/
│       ├── page/               # Page components
│       ├── services/           # API services
│       └── utils/              # Utility functions
└── nginx/                      # Nginx configuration
```

## API Endpoints

### User Endpoints
- `POST /api/user/register/` - User registration
- `POST /api/user/login/` - User login
- `GET /api/user/info/` - Get user information
- `PUT /api/user/info/` - Update user information

### Chat Endpoints
- `POST /api/chat/` - Send message (non-streaming)
- `GET /api/chat/stream/` - Streaming chat
- `GET /api/conversations/` - Get conversation list
- `POST /api/conversations/` - Create conversation
- `DELETE /api/conversations/<id>/` - Delete conversation

### Interview Endpoints
- `POST /api/interview/chat/` - Interview chat
- `GET /api/interview/stream/` - Streaming interview chat

## Build Knowledge Base

### From PDF
```bash
python Scripts/build_knowledge.py
```

### From Markdown
```bash
python Scripts/build_md_knowledge.py
```

## Environment Variables

| Variable Name | Description | Default Value |
|---------------|-------------|---------------|
| `DATABASE_URL` | Database connection string | SQLite local file |
| `REDIS_URL` | Redis connection string | Local Redis |
| `LLM_API_KEY` | Large model API key | - |
| `LLM_BASE_URL` | Large model API endpoint | - |
| `EMBEDDING_MODEL` | Embedding model name | - |

## License

MIT License