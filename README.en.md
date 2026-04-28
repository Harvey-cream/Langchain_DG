# LangChain DG

An AI chat application built on LangChain + Django + React, supporting two modes: General AI Assistant and Interview Assistant.

## Features

### 🤖 AI Assistant (Langchain_Agent)
- **AI Programming Q&A**: Provides professional programming answers using RAG technology
- **OpenClaw Support**: Integrated OpenClaw tools
- **Vibe Coding**: Supports knowledge retrieval related to Vibe Coding
- **Interview Learning**: Offers Q&A on interview-related topics
- **Web Search**: Optional web search functionality

### 🎯 Interview Assistant (Langchain_Agent1)
- **AI/LLM Interviews**: Questions related to AI and large language models
- **Java Interviews**: Technical interview questions for Java stack
- **Vue Interviews**: Technical interview questions for Vue.js stack
- **Conversation Memory**: Supports multi-turn dialogue context retention

### 📄 Other Features
- **Streaming Output**: Supports real-time streaming responses
- **PDF Export**: Allows exporting chat content to PDF
- **RAG Retrieval**: Document retrieval based on Chroma vector database
- **MCP Support**: Model Context Protocol support for multi-server deployment
- **Skill Routing**: Intelligent selection of appropriate skill contexts

## Technology Stack

### Backend
- Python 3.10
- Django 5.0
- LangChain
- Chroma (Vector Database)
- SSE (Server-Sent Events)

### Frontend
- React 18
- TypeScript
- Vite
- Ant Design

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- Redis

### Backend Installation

```bash
cd backend_langchain

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment configuration
cp .env.example .env

# Run database migrations
python manage.py migrate

# Start server
python manage.py runserver
```

### Frontend Installation

```bash
cd frontend_langchain

# Install dependencies
npm install

# Start development server
npm run dev
```

### Docker Deployment

```bash
# Build and run
docker-compose up -d
```

## API Endpoints

### User API
- `POST /api/user/register/` - User registration
- `POST /api/user/login/` - User login
- `GET /api/user/info/` - Get user information

### AI Chat API
- `POST /api/agent/chat/` - Send chat message
- `GET /api/agent/chat/stream/` - Streaming chat
- `POST /api/agent/conversation/` - Manage conversation

### Interview Assistant API
- `POST /api/interview/chat/` - Interview chat
- `GET /api/interview/chat/stream/` - Streaming interview chat

## Configuration

Main configuration options are located in `backend_langchain/env/settings_pro.yaml` or `settings_debug.yaml`:

```yaml
llm:
  model: qwen-turbo
  temperature: 0.45

redis:
  host: localhost
  port: 6379

database:
  name: langchain_db
```

## Project Structure

```
backend_langchain/
├── Langchain_Agent/       # General AI Assistant
├── Langchain_Agent1/      # Interview Assistant
├── Langchain_rag/         # RAG Tools
├── Langchain_tool/        # Toolset
├── MCP/                   # MCP Multi-server
├── User/                  # User Module
├── common/                # Common Module
├── common_web/            # Web Common Module
├── config/                # Configuration Module
├── env/                   # Environment Configuration
└── human_in_the_loop/     # Human-in-the-Loop

frontend_langchain/
├── src/
│   ├── page/            # Page Components
│   ├── services/        # API Services
│   └── utils/           # Utility Functions
```

## Development Guide

### Adding a New RAG Knowledge Base

Configure PDF file paths and vector database parameters in `Scripts/build_knowledge.py`, then run:

```bash
python Scripts/build_knowledge.py
```

### Adding a New Tool

Add new tools in the `tools.py` file under the corresponding Agent directory using the `@tool` decorator.

## License

This project does not include a LICENSE file.

## Contribution Guide

Issues and Pull Requests are welcome!