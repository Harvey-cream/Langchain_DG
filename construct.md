# Agent 架构
## 总览（纯文本 · 任意编辑器可见）

```
                    ┌──────── 用户 ────────┐
                    │                      │
         ┌──────────┴──────────┐  ┌────────┴──────────┐
         │ 企业知识库AI助手 │  │   面试 Agent 线    │
         │  上传→清洗→RAG→问答  │  │  Workflow 路由     │
         └──────────┬──────────┘  │  ├ JD Agent        │
                    │             │  ├ 模拟面试 Agent   │
                    │             │  ├ 评估 Agent       │
                    │             │  └ …可扩展          │
                    │             └────────┬──────────┘
                    └──────────┬───────────┘
                               ▼
                    ┌────── 共用底座 ──────┐
                    │ Context Builder      │
                    │ Cascade / skill→agent│
                    │ RAG · MCP · PDF      │
                    │ 会话记忆 PG ckpt     │
                    └──────────┬───────────┘
                               │ 流式结束后异步
                               ▼
                    ┌── Memory Agent ──────┐
                    │ Trigger→memories     │
                    │ （跨会话长期记忆）      │
                    └──────────────────────┘
```

- **Skill**：各 Agent / 子 Agent 独立一套，`skill_recall` 路由（归属 SubGraph）
- **Context Builder**：图前并行准备 History 读 / 按需 Memory / Retrieval Planner→RAG
- **Memory Agent**：主回复完成后异步；先 Trigger，有价值才写 `memories`

## 请求链路（知识库线 · 性能）

```
FastAPI SSE
  ↓
Context Builder          # asyncio：History读 || Memory || Planner→RAG
  ↓                      # History 压缩写：gather 外串行
Cascade Router           # 高置信规则短路 → 否则 Supervisor LLM
  ↓
Supervisor Graph         # 挂载唯一 Business SubGraph
  ↓
Business SubGraph        # Skill（可复用预计算 RAG）→ agent ↔ tools
  ↓
SSE / 落库
  ↓
Async Memory Writer      # 不挡 SSE
```

| 层 | 说明 |
|----|------|
| **Context Builder** | `runtime/context/builder.py`；`turn_context` 注入 `configurable`；`retrieved_context` 预填 State |
| **Retrieval Planner** | `infrastructure/rag/retrieval_planner.py`；一次 LLM 合并原 Gate+Rewrite |
| **Cascade Router** | `products/knowledge/cascade.py`；进 `products/knowledge/supervisor.py` 的 `route` 节点 |
| **Memory 读** | `should_retrieve_memory` 按需；写路径仍异步后置 |

## 子 Agent 工程规范（常用）

目录约定（对话线子 Agent 与后置 Agent 共用）：

```
products/<line>/subagents/<name>/
  __init__.py     # 只导出 build_<name>_graph
  graph.py        # StateGraph：节点函数 + 边 + compile()
  prompts.py      # 本 Agent 系统提示（与 graph 同目录，勿集中到 runtime）
  schemas.py      # 可选：Pydantic 结构化输出
```

分层边界（硬约束）：

```
products/knowledge  ✗→  products/interview      两条线互不 import
products/*          ✓→  runtime/ infrastructure/
runtime/            ✗→  products/               Runtime 不含业务
```

| 规范 | 说明 |
|------|------|
| **一 Agent 一子图** | 自有节点与边；总控只 `add_node` 挂载，不改子图内部 |
| **工厂** | `build_<name>_graph(...)`；对话子图默认 **不自带 checkpointer**（由 Supervisor/`stream` 外层挂） |
| **节点** | `async def` 写在 `build_*` 内（与 `doc_summary` / `knowledge_qa` 一致） |
| **结构化输出** | LLM 决策用 **Pydantic + `with_structured_output`**（总控 `RouteDecision`、Memory `ExtractResult`/`DecideResult`、Planner `RetrievalPlan`） |
| **说明书** | 知识库线子 Agent 在 `products/knowledge/subagents/registry.py` 写职责/何时用/何时不用，供 Supervisor 分诊 |
| **两条线隔离** | 知识库 / 面试顶层互不调用；跨线只共用底座 |
| **Memory 例外** | **不进** 任一线路由顶层；专用 `MemoryAgentState`；无 SSE、无 checkpointer；SSE 落库后 `ainvoke` |

对话子图典型边：`START → skill_recall → agent (↔ tools) → END`。  
Memory 写图：`START → trigger → extract → apply → END`。

参考实现：`products/knowledge/subagents/{doc_summary,knowledge_qa}`、`infrastructure/memory/agent`；总控：`products/knowledge/supervisor.py`。

## Agent 视图

```
┌─────────────────────────────────────────────────────────────┐
│                        Agent 层                              │            
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌─────────────────────┐      ┌─────────────────────┐      │
│   │ 企业知识库AI助手线  │      │    面试 Agent 线     │      │
│   └──────────┬──────────┘      └──────────┬──────────┘      │
│              │                            │                 │
│   ┌──────────┼──────────┐    ┌─────────────┼─────────────┐   │
│   ▼          ▼          ▼    ▼             ▼             ▼   │
│ ┌────────┐ ┌────────┐ ┌────────┐ ┌─────────┐ ┌───────────┐ ┌─────────┐
│ │文档摘要 │ │合规速查 │ │知识问答 │ │JD Agent │ │模拟面试    │ │评估     │
│ │Agent   │ │Agent   │ │Agent   │ │         │ │Agent      │ │Agent    │
│ └────────┘ └────────┘ └────────┘ └─────────┘ └───────────┘ └─────────┘
│              … 入库 Pipeline（非 Agent）…    … 可扩展 …       │
│                                                              │
│   ┌─────────────────────┐                                    │
│   │   Memory Agent      │  ← 异步后置，写 memories            │
│   └─────────────────────┘                                    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

- **线内顶层路由（Supervisor）**：知识库线为**路由型顶层 Graph**（不写长答案）：`Cascade Router`（高置信规则短路）+ Supervisor LLM 兜底，见 `products/knowledge/{supervisor,cascade}.py`。默认 LLM 分诊；仅高置信意图允许规则短路。面试线当前为单图（`products/interview/runtime.py`），线内 Supervisor + 子 Agent 为后续扩展位。
- **两条线严禁串联**：两边顶层互不调用、不共用一张总控图；前端分入口，只共用底座（图工厂 / RAG / SSE 等）。线内子 Agent 可串联（如面试 `JD → 模拟 → 评估`），跨线不可。
- **Memory Agent**：异步后置，挂在主回复之后，不并入任一线路由顶层。
- **子 Agent 定义**：每个子 Agent 有独立说明书（职责 / 何时用 / 何时不用），交给总控 LLM；**各自独立子图**（自有节点与边，见 `products/knowledge/subagents/`），图内仍可有 Skill 集。

## Agent 说明

### 共用技术

| 技术 | 作用 |
|------|------|
| **LangGraph** | `skill_recall → agent ↔ tools`；知识库线外层 Supervisor |
| **Context Builder** | 图前并行上下文；History 读并行、压缩写串行 |
| **Retrieval Planner** | Gate+Rewrite 合并为一次 structured LLM |
| **Skill 路由** | 向量匹配意图 + 约束输出结构（每 Agent 独立 Skill 集；留在 SubGraph） |
| **RAG** | pgvector（表 `rag_embeddings`）；corpus=user 与内置 `knowledge` 隔离；可按需 |
| **会话记忆** | PostgreSQL checkpoint（独立库）；超阈值压缩（摘要 + 保留近几轮） |
| **SSE** | 流式对话；附件当轮临时注入，不落库 |

---

### 企业知识库AI助手线

**入库 Pipeline（非 Agent）**  
`上传 → 清洗切块 → 向量化 → 写入 user_knowledge`  
后台任务，不走 LLM 对话；为下方 Agent 提供知识源。

| Skill / Agent | 职责 | RAG / 工具 |
|---------------|------|------------|
| **knowledge_qa** | 找文档、问答、对比与出处（知识问答 Agent） | 用户 corpus；MCP/PDF |
| **doc_summary** | 摘要 / 导读 / 要点提炼（文档摘要 Agent） | 用户 corpus；强制检索 |
| **document_export** | 导出 PDF（暂挂知识问答图） | confirm / finalize PDF |
| **repo_inspector** | 仅仓库链接时解析（暂挂知识问答图） | MCP |
| **compliance_lookup**（待做） | 制度/政策条款 + 出处 | 用户 corpus；输出格式固定 |

```
入库 Pipeline ──→ user_knowledge
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
    文档摘要    合规速查    知识问答
```

---

### 面试 Agent 线

Workflow 按意图路由子 Agent，可串联：`JD → 模拟 → 评估`。

| Agent | 职责 | RAG / 工具 |
|-------|------|------------|
| **JD Agent** | 生成/优化岗位描述 | 可选模板库；结构化输出 |
| **模拟面试 Agent** | 出题、追问、答题辅导 | `interview` corpus；按赛道过滤 |
| **评估 Agent** | 作答评分、维度分析、复盘 | 结合当轮对话；可导出 PDF |

---

### Memory Agent（异步）

| 项 | 说明 |
|----|------|
| **包路径** | `infrastructure/memory/agent`（`build_memory_agent_graph`） |
| **时机** | 主回复流式结束、会话落库之后；`asyncio.create_task` → `ainvoke`，不挡 SSE |
| **Trigger** | 规则过滤（长度 / 偏好关键词等）；无长期价值直接 END |
| **流水线** | `trigger → extract → apply`；Extract/Decide 用 Pydantic；apply 内 search→decide→upsert |
| **表** | `memories`（pgvector，与 `rag_embeddings` 隔离） |
| **读取** | `format_retrieved_memories` + `should_retrieve_memory` 按需 Top-K 注入 System |
| **原则** | 不进 Supervisor；失败只打日志 |

```
回复完成 → Memory Trigger →（有价值）extract/decide → memories（PG+pgvector）
下次提问 →（按需）Retrieve → 注入 Prompt → Main Agent
```
