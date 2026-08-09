# LangChain DG

基于 LangGraph 的多 Agent 对话应用：企业知识库助手（Supervisor + 子 Agent）与面试线隔离运行，共用 RAG / SSE / Memory 底座。

## 功能特性

- 🤖 **多 Agent**：知识库线 Cascade + Supervisor 路由至文档摘要 / 知识问答子图；面试线独立入口；Memory Agent 异步后置
- 💬 **智能对话**：LangGraph 状态图，PostgreSQL checkpoint 多轮记忆，超长会话可压缩
- 🔍 **知识库检索**：pgvector RAG；用户库按 `corpus + user_id` 隔离；Retrieval Planner 按需检索
- 📄 **PDF 导出**：HITL 确认后导出（知识库 / 面试线）
- 🔎 **网页搜索**：可选联网（知识库问答）
- 🔐 **安全认证**：JWT + SM2
- ⚡ **流式响应**：SSE；图前 Context Builder 并行准备 Memory / RAG 上下文

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.12, FastAPI, LangChain, LangGraph, SQLAlchemy (async), PostgreSQL + pgvector, Redis |
| 前端 | React 18, TypeScript, Vite, Ant Design |
| 部署 | Docker, Nginx |
| 向量 / LLM | DashScope（阿里云） |

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 18+
- Docker & Docker Compose
- PostgreSQL（业务库 + checkpoint 库，需 pgvector）

### 配置环境变量

```bash
cp .env.example .env
```

```bash
# 开发
cp backend_langchain/env/settings_debug.example.yaml backend_langchain/env/settings_debug.yaml

# 生产
cp backend_langchain/env/settings_pro.example.yaml backend_langchain/env/settings_pro.yaml
```

### Docker 部署

```bash
docker compose up -d
```

服务默认 `http://localhost:8000`。

### 本地开发

1. 安装后端依赖：

```bash
cd backend_langchain
pip install -r requirements.txt
```

2. 启动后端：

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

3. 安装前端并启动：

```bash
cd frontend_langchain
npm install
npm run dev
```

## 项目结构

```
backend_langchain/
├── app/                         # FastAPI
│   ├── main.py
│   ├── routers/
│   │   ├── api.py               # 知识库助手 SSE / 对话
│   │   ├── interview.py         # 面试线
│   │   ├── documents.py         # 用户文档上传入库
│   │   └── user.py              # 认证
│   ├── services/document_pipeline/  # 清洗切块 → 向量化
│   ├── models.py
│   └── settings.py
├── agent/                       # Agent 核心（两条线隔离）
│   ├── context_builder.py       # 图前并行：History / Memory / Planner→RAG
│   ├── stream.py                # SSE 编排 + 异步 Memory 调度
│   ├── graph_factory.py         # 共用图工厂 / 流式事件
│   ├── checkpointer.py          # PG checkpoint
│   ├── graphs/
│   │   ├── supervisor_knowledge.py   # 知识库总控
│   │   ├── cascade_route.py          # 高置信规则短路
│   │   ├── knowledge_subagents.py    # 子 Agent 说明书
│   │   └── agents/
│   │       ├── doc_summary/     # 文档摘要子图
│   │       ├── knowledge_qa/    # 知识问答子图（工具 / PDF / 可选联网）
│   │       └── memory/          # 长期记忆写图（trigger→extract→apply）
│   ├── runtime/
│   │   ├── runtime_knowledge.py
│   │   └── runtime_interview.py # 面试线（单图 + Skill，可演进 Supervisor）
│   ├── rag/                     # pgvector、Planner、Skill、精排
│   ├── memory/                  # 会话压缩 + 长期记忆读写
│   ├── tools/                   # 知识库 / 面试工具
│   ├── hitl/                    # PDF 人机确认
│   └── mcp/                     # MCP
├── Scripts/                     # 建库 / 诊断脚本
└── env/                         # yaml 配置样例

frontend_langchain/
├── src/
│   ├── page/
│   │   ├── Langchain/           # 对话
│   │   └── Langchain_login/
│   └── services/
```

架构说明见仓库根目录 `construct.md`。

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

```bash
python -m Scripts.build_rag_knowledge --agent-domains "vibe_coding" --do-interview
```

用户上传文档走 `documents` 入库 Pipeline（非 Agent），写入 `corpus=user` 并按 `user_id` 隔离。

## 配置说明

主要配置：`backend_langchain/app/settings.py` + `env/settings_*.yaml`：

- `llm_config`：大模型
- `dashscope_config`：嵌入 / 精排 / 可选联网
- `rag_config`：检索与 Planner 相关开关
- `postgres` / checkpoint：业务库与 LangGraph 会话库
- `redis_url`：Redis（如 Celery）

## 许可证

MIT License
