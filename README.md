# LangChain DG

基于 LangChain 构建的 AI 对话应用，提供智能 Agent 和面试助手功能，支持流式输出、知识库检索和 PDF 导出。

## 功能特性

- 💬 **智能对话**：基于 LangGraph 的状态流图实现，支持多轮对话和上下文记忆
- 🔍 **知识库检索**：RAG 架构，支持 Markdown 和 PDF 文档向量化存储与检索
- 📄 **PDF 导出**：对话内容可导出为 PDF 格式
- 🔎 **网页搜索**：集成网络搜索能力（可选）
- 🔐 **安全认证**：JWT + SM2 国密算法双重加密
- ⚡ **流式响应**：Server-Sent Events (SSE) 实现实时流式输出

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.12, FastAPI, LangChain, LangGraph, SQLAlchemy (async), Chroma, Redis |
| 前端 | React 18, TypeScript, Vite, Ant Design |
| 部署 | Docker, Nginx |
| 向量模型 | DashScope (阿里云) |

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 18+
- Docker & Docker Compose

### 配置环境变量

复制并配置 `.env.example` 文件：

```bash
cp backend_langchain/.env.example backend_langchain/.env
```

根据部署环境选择配置文件：

```bash
# 开发环境
cp backend_langchain/env/settings_debug.example.yaml backend_langchain/env/settings_debug.yaml

# 生产环境
cp backend_langchain/env/settings_pro.example.yaml backend_langchain/env/settings_pro.yaml
```

### Docker 部署

```bash
docker compose up -d
```

服务将在 `http://localhost:8000` 启动。

### 本地开发

1. 安装后端依赖：

```bash
cd backend_langchain
pip install -r requirements.txt
```

2. 启动后端：

```bash
uvicorn app.main:app --reload --port 8000
```

3. 安装前端依赖并启动：

```bash
cd frontend_langchain
npm install
npm run dev
```

## 项目结构

```
backend_langchain/
├── app/                    # FastAPI 应用主目录
│   ├── main.py            # 应用入口
│   ├── routers/          # API 路由
│   │   ├── api.py        # 超级智能体 HTTP 接口
│   │   ├── interview.py # 面试助手接口
│   │   └── user.py      # 用户认证接口
│   ├── models.py         # SQLAlchemy 模型
│   └── settings.py       # 配置管理
├── Langchain_Agent/       # Agent 核心逻辑
│   ├── runtime.py       # Agent 运行时（图缓存、流式入口）
│   └── tools/          # 工具函数
├── Agent_memory/         # 对话记忆管理
├── common/              # 公共模块
│   ├── agent.py         # Agent 基础组件
│   ├── rag.py          # RAG 检索
│   └── skill_router.py # 技能路由
├── MCP/                 # MCP 工具集成
└── Scripts/             # 构建脚本

frontend_langchain/        # React 前端
├── src/
│   ├── page/            # 页面组件
│   │   ├── Langchain/  # 对话页面
│   │   └── Langchain_login/  # 登录注册
│   └── services/       # API 服务
```

## 构建知识库

### 方式一：容器内构建

```bash
docker compose exec backend python -m Scripts.build_rag_knowledge
```

### 方式二：本地构建

```bash
cd backend_langchain
python -m Scripts.build_rag_knowledge
```

支持指定领域和文档类型：

```python
python -m Scripts.build_rag_knowledge --agent-domains "vibe_coding" --do-interview
```

## 配置说明

主要配置项位于 `backend_langchain/app/settings.py`：

- `llm_config`: 大语言模型配置（API Key、模型名称）
- `dashscope_config`: 阿里云 DashScope 配置
- `rag_config`: RAG 向量库配置
- `redis_url`: Redis 连接地址

## 许可证

MIT License