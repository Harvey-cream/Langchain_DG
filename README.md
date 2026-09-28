# LangChain DG

**企业合同全生命周期 AI Agent 平台**

> 面向企业合同全生命周期的 AI Agent 平台，覆盖合同上传、文档结构化、风险审查、Human-in-the-loop、版本追踪、客户回传 Diff、谈判辅助与最终合同交付，基于 LangGraph、RAG、ContractPolicy 构建可追溯、可恢复的智能合同处理闭环。

---

## 项目简介

LangChain DG 是一个**企业合同全生命周期 AI Agent 平台**。系统围绕合同的完整业务闭环构建：合同上传 → 文档结构化 → 风险审查 → 人工确认 → 新版本生成 → 客户回传 Diff → 谈判辅助 → 合同交付。

平台采用 **Workflow First、Agent Second** 的设计思想，将确定性业务逻辑与 LLM 推理节点解耦：以 **LangGraph** 负责 Agent Workflow 与可恢复执行，以 **PostgreSQL** 保存业务状态，以 **RAG / ContractPolicy / MCP / OSS** 等共享能力构建面向真实业务流程的 Agent Application。

> 本仓库此前的“多 Agent 对话应用 / 企业知识库问答”定位已经演进。**Contract 是当前第一产品线**；企业知识库（Knowledge）产品已退休，其可复用的 retrieval / embedding / pgvector 能力继续作为底层能力服务新产品。Interview Agent 作为独立产品线保留，但不再是项目主线。

## 核心能力

### 合同领域与版本模型

- **Customer / Contract / ContractVersion** 领域实体与用例服务
- **append-only 版本模型**：`Contract ID` 稳定，`V1 / V2 / V3` 为完整快照，历史版本不覆盖
- **合同归属与用户隔离**：所有查询按 `user_id` 隔离
- **版本编号与历史追踪**：版本号单调递增，`(contract_id, number)` 唯一
- Customer / Contract / ContractVersion 的完整 CRUD API

### 文档智能

- PDF / Markdown / TXT 文档解析与清洗切块流水线
- 面向检索的 embedding 入库（pgvector）
- **结构化 `ContractClause` 抽取**，作为审查工作流的输入

### AI 风险审查

- **Review Workflow**：面向合同条款的审查工作流
- **RiskFinding**：结构化风险点输出
- **ContractPolicy / RAG 上下文**：以企业政策与历史合同为检索上下文
- 采用 Pydantic 结构化输出约束 LLM 决策

### Human-in-the-loop

- AI 不直接覆盖合同，风险点先转为 **Revision Proposal**
- 人工 **Accept / Reject / Edit** 后生成**新 ContractVersion**
- 明确原则：**AI suggestion ≠ final business decision**

### 合同 Diff 与谈判辅助

- **Diff Engine**：`Previous Version + Current Version → 结构化变更`
- **谈判辅助 Agent**：基于 Diff 与 ContractPolicy 生成修改建议与话术

### Agent Runtime

- **LangGraph** 状态图与可恢复执行
- **PostgreSQL Checkpoint**：保存 Agent 运行时状态，支持 interrupt / resume
- **SSE 流式**：图前 Context Builder 并行准备 History / Memory / RAG 上下文
- **Context Builder**：`products/interview/agent/context`，图前并行装配面试上下文

### 平台能力

- **PostgreSQL + pgvector**：业务库、向量库、Checkpoint 库
- **RAG**：Embedding / Rerank / Retrieval Planner
- **Memory**：短期会话压缩 + 长期 Memory Agent（异步后置）
- **MCP**：外部工具接入
- **OSS**：阿里云对象存储适配
- **Redis / Docker / Nginx**：部署与基础设施

---

## 架构

### 当前目录边界

```text
backend_langchain/
├─ app/                         # FastAPI 组合入口，只负责挂载各产品路由
├─ common/                      # 两条产品线真正共用的配置、数据库、鉴权、账号、存储、MCP
├─ products/
│  ├─ contract/                 # 合同 API、ORM、查询、文档处理、工作流与审查 Agent
│  └─ interview/                # 面试 API、会话、Agent Runtime、RAG、Memory、PDF 与语料
├─ scripts/{common,contract,interview}/
└─ tests/{common,contract}/

frontend_langchain/src/
├─ app/                         # SPA 入口页面
├─ common/                      # 登录态与 HTTP 客户端
└─ products/{contract,interview}/
```

代码按产品线物理隔离。`contract` 与 `interview` 不互相 import；只有确实被两边使用的能力才放入 `common`。同一领域、同一职责的代码优先收拢，不为每个简单用例额外建立 Service / Port / Repository 层。

### 分层视图

```
                            React (SPA)
                                │
                                ▼
                        FastAPI (HTTP / SSE)
                                │
                                ▼
              FastAPI Router（HTTP + 用例编排）
        ┌───────────────────────┼────────────────────────┐
        ▼                       ▼                        ▼
     Domain                  Workflow                  Agents
 (实体 / 不变量)         (确定性编排)            (推理 / 规划 / 风险)
        └───────────────────────┼────────────────────────┘
                                ▼
                    Agent Runtime / LangGraph
                                │
        ┌───────────────┬───────┴────────┬────────────────┐
        ▼               ▼                ▼                ▼
     Context          RAG           Tools / MCP      Checkpoint
   (图前装配)     (pgvector)      (外部能力)      (运行时状态)
                                │
                                ▼
                        Infrastructure
        ┌───────────────┬───────────────┬────────────────┐
        ▼               ▼               ▼                ▼
   PostgreSQL       Redis            OSS            Document
      + pgvector   (Queue/缓存)   (对象存储)     (解析 / 渲染)
```

### 设计理念

**1. Workflow First, Agent Second**

Agent 不是整个系统，业务流程由 Workflow 控制。LLM / Agent 只进入真正需要 reasoning、planning、risk analysis、revision、negotiation 的节点；CRUD、Version、Diff、Parsing、Storage、Export、Email 等确定性逻辑使用普通 Python 模块 / Engine / Worker。

**2. Business State 与 Runtime State 分离**

- **PostgreSQL** 保存业务事实：Customer、Contract、ContractVersion、ContractClause、ContractChange、RiskFinding、Policy
- **LangGraph Checkpoint** 只保存 Agent 运行时状态（interrupt / resume / workflow execution）
- `ContractVersion` 永远不放进 Checkpoint，也不从 Checkpoint 恢复

**3. Human-in-the-loop**

AI 不直接覆盖合同，核心链路为：

```
RiskFinding → Revision Proposal → Human Accept / Reject / Edit → New ContractVersion
```

**4. Version-first Contract Model**

```
Customer
  └── Contract              (Contract ID 稳定)
        └── ContractVersion  (V1 / V2 / V3 完整快照)
              └── ContractClause
                    ├── RiskFinding
                    └── ContractChange
```

**5. Deterministic + Agent Hybrid**

Document Parser、Diff Engine、Version Manager、PDF Renderer、Email Worker 是普通服务，不是 Agent；Review、Revision、Negotiation 属于智能决策能力，才使用 Agent。

> 设计决策记录见 [`backend_langchain/common/docs/adr/`](./backend_langchain/common/docs/adr)：产品隔离、领域分离、Workflow First、Agent Runtime 边界、业务状态 vs Checkpoint、持久化后台任务、SSE 传输边界。

---

## 合同工作流

目标架构下的完整合同处理链路：

```
   用户上传 PDF / Markdown
          │
          ▼
      ContractVersion
          │
          ▼
   Document Intelligence
          │
          ▼
     ContractClause
          │
          ▼
     Review Workflow
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

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.12, FastAPI, LangGraph, SQLAlchemy (async), Pydantic |
| 前端 | React 18, TypeScript, Vite, Ant Design |
| 数据 | PostgreSQL, pgvector, Redis |
| AI | RAG, Embedding, Rerank, LLM, MCP |
| 基础设施 | 阿里云 OSS, Docker, Docker Compose, Nginx |
| 向量 / LLM | DashScope（阿里云百炼） |
| 安全 | JWT + SM2 国密 |

---

## 项目结构

```
backend_langchain/
├── app/                          # FastAPI 应用层
│   ├── main.py                   # 应用入口 / lifespan
│   ├── routers/                  # HTTP 路由：user / contract / interview
│   ├── services/
│   │   └── document_pipeline/    # 文档清洗 / 切块 / 向量化 ingest
│   ├── auth/                     # JWT + SM2
│   ├── sse.py                    # SSE 编排
│   └── settings.py
│
├── products/                     # 产品线（互不 import）
│   ├── contract/                 # 第一产品线：合同全生命周期
│   │   ├── domain/               # 文档事实 / 审查状态值对象
│   │   ├── schemas/              # API DTO
│   │   ├── document_intelligence/# 文档结构化流水线
│   │   ├── workflows/            # 合同审查工作流
│   │   └── agents/               # 合同审查 LLM 适配
│   └── interview/                # 其他产品线：面试 Agent
│
├── runtime/                      # 运行机制（无业务）
│   ├── execution/                # 通用 State / 图工厂
│   ├── context/                  # 图前 Context Builder
│   ├── checkpoint/               # LangGraph PostgreSQL checkpointer
│   └── streaming/                # astream → 统一事件
│
├── agent_platform/
│   └── storage/                  # 当前实际使用的对象存储端口
│
├── infrastructure/               # 共享底座适配器
│   ├── db/                       # SQLAlchemy Models + 复杂审查持久化
│   ├── rag/                      # pgvector / Planner / Rerank / WebSearch
│   ├── memory/                   # 短期压缩 + 长期 Memory Agent
│   ├── oss/                      # 阿里云 OSS 适配
│   ├── pdf/                      # PDF 人机确认 + 渲染
│   └── mcp/                      # MCP 多服务
│
├── migrations/                   # 0001 contract schema / 0002 knowledge retire
├── knowledge/                    # docs2（Interview 语料）+ 已退休语料归档
├── scripts/                      # 建库 / 诊断 / smoke
├── tests/contract/
└── env/                          # yaml 配置样例

frontend_langchain/
└── src/
    ├── app/routes/               # 路由（ContractRoutes）
    ├── pages/
    │   ├── contract/             # ContractListPage / ContractVersionPage
    │   └── interview/
    ├── features/
    │   ├── contract/             # api / types
    │   └── chat/
    ├── page/                     # Legacy：对话 / 登录注册
    ├── services/                 # 认证 API / chatStream / request
    └── utils/                    # sm2
```

---

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 18+
- Docker & Docker Compose
- PostgreSQL（业务库 + Checkpoint 库，需 pgvector）

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

服务默认 `http://localhost:8000`（同栈包含 PostgreSQL / pgvector、Redis、Nginx）。

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

---

## Roadmap

- [x] Contract / Customer / ContractVersion 领域基础
- [x] Product / Runtime / Infrastructure 分层隔离
- [x] Legacy Knowledge 产品退休
- [x] Agent Runtime（LangGraph / SSE / Checkpoint / Context Builder）
- [x] 共享基础设施（RAG / Memory / MCP / OSS / Redis / Docker）
- [x] Contract 文件上传 + OSS 绑定
- [x] Document Intelligence → Canonical ContractClause
- [x] Review Workflow V1 → Clause / Risk
- [ ] Revision + Human-in-the-loop
- [ ] Version Diff
- [ ] Negotiation Agent
- [ ] DOCX / PDF 导出
- [ ] Email 交付
- [ ] 持久化后台任务（Queue / Worker 落地）

---

## 其他产品线

### Interview Agent（次要 / 并行演进）

现有 Interview Agent 作为独立产品线继续保留，与 Contract 产品业务隔离。Interview 自己持有 Agent Runtime / RAG / Memory；两条线只共用 `common` 下的鉴权、数据库、配置、对象存储和外部集成。产品线之间**严禁互相 import**（见 [ADR 0001](./backend_langchain/common/docs/adr/0001-product-isolation.md)）。

### Legacy 知识库

旧版 Agent 语料 `docs1` 仍作为当前语料保留，并已迁移到 PostgreSQL/pgvector；旧的 Chroma 向量文件已删除。相关数据库表归档脚本见 `migrations/0002_retire_knowledge_data.py`（显式执行，可回滚）。

需要说明的是：**Knowledge 产品 ≠ RAG 能力**。退休的是知识库问答产品，其中可复用的 retrieval / embedding / pgvector 能力继续作为底层能力服务新产品。

如仍需构建 Interview 语料，语料位于 `backend_langchain/products/interview/knowledge/docs2/<domain>/**/*.pdf`：

```bash
cd backend_langchain
python -m scripts.interview.build_rag_knowledge --interview-only
```

---

## 配置说明

主要配置：`backend_langchain/common/settings.py` + `env/settings_*.yaml`：

- `llm_config`：大模型
- `dashscope_config`：嵌入 / 精排 / 可选联网
- `rag_config`：检索与 Planner 相关开关
- `postgres` / checkpoint：业务库与 LangGraph 会话库
- `oss_config`：阿里云 OSS
- `redis_url`：Redis

密钥通过仓库根目录 `.env` 以 `${VAR}` 注入 yaml。

---

## 许可证

MIT License
