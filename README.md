# LangChain DG

基于 LangGraph 的多 Agent 对话应用：AI 面试大师与合同管理两条产品线，共用 RAG / SSE / Memory 底座。

## 功能特性

- 🤖 **多 Agent**：AI 面试大师独立入口（单图 + Skill）；Memory Agent 异步后置
- 💬 **智能对话**：LangGraph 状态图，PostgreSQL checkpoint 多轮记忆，超长会话可压缩
- 🔍 **RAG 检索**：pgvector；Interview 语料按 `corpus` 隔离；Retrieval Planner 按需检索
- 📄 **PDF 导出**：HITL 确认后导出（面试线）
- 📑 **合同管理**：客户 / 合同 / 合同版本 CRUD 与文件归属
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
│   │   ├── interview.py         # 面试线 SSE / 对话
│   │   ├── contract.py          # 合同 / 合同版本
│   │   ├── customer.py          # 客户
│   │   └── user.py              # 认证
│   ├── services/document_pipeline/  # 清洗切块 → 向量化
│   ├── sse.py                   # SSE 编排 + 异步 Memory 调度
│   ├── models.py
│   └── settings.py
├── runtime/                     # 运行机制（无业务）
│   ├── context/builder.py       # 图前并行：History / Memory / Planner→RAG
│   ├── execution/graph_factory.py  # 通用 State / 图工厂
│   ├── streaming/stream.py      # astream → 统一事件
│   └── checkpoint/checkpointer.py  # PG checkpoint
├── products/                    # 产品线（互不 import）
│   ├── interview/
│   │   ├── runtime.py           # 面试线入口（单图 + Skill，可演进 Supervisor）
│   │   ├── prompts.py
│   │   ├── skills.py
│   │   └── tools.py
│   └── contract/
│       ├── domain/              # 纯业务实体 / 值对象 / 领域错误
│       ├── schemas/             # API DTO
│       ├── application/         # 用例服务 + Ports
│       └── ...
├── infrastructure/              # 共享底座
│   ├── rag/                     # pgvector、Planner、Skill 引擎、精排
│   ├── memory/                  # 会话压缩 + 长期记忆读写
│   │   └── agent/               # 长期记忆写图（trigger→extract→apply）
│   ├── pdf/                     # PDF 人机确认 + 渲染
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

## 构建面试知识库

Interview 语料位于 `backend_langchain/knowledge/docs2/<domain>/**/*.pdf`：

```bash
cd backend_langchain
python -m Scripts.build_rag_knowledge --do-interview
```

> 企业知识库（Agent）产品已于 Phase D 退休：`knowledge/docs1` 与 Chroma 数据归档在
> `knowledge/_retired_agent_corpus/`；`agent_documents` / `agent_web_sources` 表
> 归档脚本见 `migrations/0002_retire_knowledge_data.py`（显式执行，可回滚）。
> `rag_embeddings` 中 `corpus in ('agent','user')` 的历史向量保留待迁移。

## 配置说明

主要配置：`backend_langchain/app/settings.py` + `env/settings_*.yaml`：

- `llm_config`：大模型
- `dashscope_config`：嵌入 / 精排 / 可选联网
- `rag_config`：检索与 Planner 相关开关
- `postgres` / checkpoint：业务库与 LangGraph 会话库
- `redis_url`：Redis（如 Celery）

## 许可证

MIT License
