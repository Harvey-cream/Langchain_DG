# P4 第二批：ContractPolicy + 私有知识库 RAG

> 历史阶段记录。当前 Review 已迁入 LangGraph；本文件的 Policy/RAG 数据规则继续有效，现行编排与最新验收见 [P4-review-graph.md](./P4-review-graph.md)。

实现及验收日期：2026-10-08。范围仅为 P4.6–P4.7，不包含 P4.8、P5、知识库聊天 Agent、组织权限系统或正式 MQ/Worker。不自动 Git Commit。

后续状态：下文是第二批当时的验收记录；第三批已增加确定性 Quality Gate，并执行真实 Document Intelligence / Review 全链路样例验收。最新实现、167 项后端/21 项浏览器测试和边界见 [P4-quality-gate.md](./P4-quality-gate.md)，不要把第二批“未执行真实 Review 质量评估”与第三批真实 smoke 混为一谈；完整法律质量评测仍未完成。

保持现有组织方式：HTTP CRUD 和短事务在 `products/contract/api.py`；合同 ORM 集中在 `models.py`；Review 共享事务在 `db.py`。新增 `knowledge.py` 承担参考文档解析/索引后台任务，`retrieval.py` 承担真正的混合检索。没有 Service / Store / Repository / Port 或新 Agent。

## 1. ContractPolicy 数据模型与 CRUD

`ContractPolicyModel` / `contract_policies`：

- UUID `id`、用户外键 `user_id`，API 展示 `owner_id`。
- `name`、`description`、`category`、`requirement`、`severity`。
- `applicable_contract_types`：类型列表；空列表表示类型不限。
- `applicable_party_role`：用户明确指定的业务角色；空字符串表示角色不限。
- `enabled`、`archived`、`version`、`created_at`、`updated_at`。

接口保持在 `api.py`：

| 接口 | 行为 |
|---|---|
| `GET /api/contract-policies` | 仅列出自己的规则，默认隐藏归档，可带 `include_archived=true` |
| `POST /api/contract-policies` | 校验并创建，version=1；不接受客户端 owner_id |
| `PATCH /api/contract-policies/{id}` | 编辑或启停；要求 expected_version，行锁检查后 version+1 |
| `DELETE /api/contract-policies/{id}?expected_version=N` | 归档、禁用、version+1，不破坏历史引用 |

规则正文最多 2,000 字符，描述最多 1,000，适用类型最多 12 项；风险等级只有 high/medium/low。不把付款 45 天、赔偿上限等示例作为所有用户的默认规则，也不新增 organization/tenant 表。

上传和重新审查均支持明确输入 `our_party`、`party_role`、`contract_type`，分别表示签约主体/甲乙方、业务角色和合同类型。类型/角色去首尾空白并 casefold 后精确匹配，不从客户名称或模型提取摘要猜测身份。空身份仍可以使用不限范围的通用企业规则；有范围限制的规则不会被自动套用。

## 2. Policy 版本化与适用范围

`db.prepare_review_context` 在真正开始 Review 时：

1. 检查 Run → Version → Contract 的实际 owner。
2. SQL 限制同用户、enabled=true、archived=false。
3. 精确筛选合同类型和业务角色。
4. 把完整适用规则（真实 ID、version、正文、范围、等级）存入 `AnalysisRun.context_snapshot.policies`。

采用最小可靠的 Run Snapshot，不另建规则版本表。编辑、禁用或归档当前规则不修改旧 Run；下一次新 Run 重新解析最新适用规则。`RiskFinding.policy_ids` 只能来自本次快照，禁止重复/不存在 ID，风险等级不得低于所引用规则的 severity。

Policy 历史追溯是“曾用于审查的版本”；不是独立的所有规则编辑日志或回滚系统。PATCH 过期版本返回 409，禁止覆盖别人刚保存的修改。

## 3. 用户知识库模型

仍集中在 `products/contract/models.py`，与 ContractVersion / Canonical Clause 分开：

- `ContractKnowledgeDocumentModel` / `contract_knowledge_documents`：原件名称、私有 OSS key、SHA-256、user_id、document_version、分类、状态、索引 generation、attempt、Chunk/字节/页数、embedding_model、错误和时间。
- `ContractKnowledgeChunkModel` / `contract_knowledge_chunks`：真实 UUID、document_id、user_id、document_version、generation、sequence、chunk_text、locator、token_index、embedding、embedding_model。
- PostgreSQL 使用 `vector(1024)` 和 HNSW `vector_cosine_ops` 索引；SQLite 仅为测试使用 JSON 向量。
- `(document_id, generation, sequence)` 唯一；未删除的 `(user_id, content_hash)` 条件唯一，阻止同用户重复创建同一原件。

当前原件不可变，document_version=1；重建索引只递增 generation，不冒充新的原始文档版本。不同原件创建不同 document_id。分类支持五个常用值及用户自定义文本；修改分类不重新调用 Embedding。

## 4. 上传到索引的实际调用链

```text
POST /api/contract-knowledge/documents/upload
  -> PDF/DOCX 校验 + 当前登录用户 + SHA-256 去重
  -> 短事务保存 uploading 意图
  -> OSS put（没有数据库行锁或长事务）
  -> 短事务标记 uploaded，提交后 BackgroundTasks
  -> knowledge.ingest_document(id, generation)
       -> 原子 UPDATE uploaded -> processing，attempt+1，仅一个任务领取
       -> OSS download -> P3 parse_contract（真实 PDF/DOCX parser）
       -> chunk_document -> 真实 Embedding
       -> 校验向量数量、1024 维、有限数值、非零
       -> 短事务检查 generation/status
       -> DELETE 旧 Chunk + INSERT 新 Chunk/vector/token_index + Ready，一起提交
```

Chunk 默认 1,200 字符、重叠 150；沿真实文档文字切片，不改写为模型条款，保留 block_sequences、start/end_char，PDF 有真实页码时保留 pages，DOCX 不伪造页码。知识库解析结果不会写入 P3 ContractVersion Facts。

状态增加 uploading 和 deleting 两个可恢复阶段。OSS 上传失败保留 failed 记录；可重新上传相同文件恢复原意图，也可删除。解析、Embedding 或索引发布失败标记 failed；重建索引发布回滚时旧行保留但因状态/代次不匹配而不可检索，下次成功再整体替换，不累积重复 Chunk。

删除先在短事务撤下当前 Chunk、递增 generation、标记 deleting，再清理 OSS；清理失败展示错误并允许重试，成功为 deleted 墓碑。迟到的上传成功会额外清理原件；迟到的上传失败/索引任务不会复活已删除记录。服务重启会把中断上传/索引标为 failed，把中断删除显示为可重试错误。

## 5. 实际 Hybrid Retrieval

仓库没有可运行的 Elasticsearch 或已有 BM25 实现。没有搬用旧 Knowledge Agent，也没有将普通 PostgreSQL FTS 命名为 BM25。

`retrieval.retrieve_references` 的真实分支：

| 分支 | 实现 |
|---|---|
| Dense | DashScope text-embedding-v3，1024 维；pgvector `<=>` cosine distance SQL + 向量索引 |
| BM25 | 持久化 token_index；Python Okapi BM25，k1=1.5、b=0.75，正值 log IDF；英文词/中文单字及双字分词 |
| Fusion | RRF：每个分支名次贡献 `1/(60+rank)`，真实 Chunk ID 去重 |
| Rerank | DashScope qwen3-rerank HTTP API 的真实模型返回 index/score，验证索引、评分和重复项 |

`common/integrations/retrieval_models.py` 只复用纯模型调用；Interview 原有包装委托此模块，仍保留 Interview 自己的 fallback。Contract 不借用 Interview 的表、检索规则或数据，模型失败不会退化排序后宣称完成 Rerank。

配置见根 `.env.example`：

| 环境变量 | 默认 / 允许范围 |
|---|---|
| CONTRACT_RAG_TOP_K | 3 / 1..8，每条款组最终资料数 |
| CONTRACT_RAG_RECALL_K | 24 / 1..100，各分支粗召回数 |
| CONTRACT_RAG_RERANK_COUNT | 16 / 1..100，融合后交给模型的候选数 |
| CONTRACT_RAG_TIMEOUT | 30 秒 / 1..120，完整一轮检索超时 |
| CONTRACT_RAG_BM25_MAX_CHUNKS | 10,000 / 1..50,000，每用户 Ready 语料容量 |

需要已有 DASHSCOPE_API_KEY 和 YAML 中的 Embedding/Rerank 配置。Embedding 模型改变后不混用不同空间，明确要求重新索引。空知识库返回 []，不调用 Embedding/Rerank。已有语料但模型故障/超时，明确返回可重试失败。

轻量 BM25 会读取该用户的 Ready Token 语料并计算，不是 Elasticsearch，也没有夸称百万级索引能力。超出容量显式失败，不静默漏查；大规模知识库需后续接入专门检索服务。

## 6. Review 按 Clause / Clause Group 动态召回

正式入口 `document/contract_jobs.execute_analysis` 给工作流传入 `retrieval_factory=SessionLocal`，因此生产路径真正启用 RAG，不只是单独搜索演示。

```text
AnalysisRun -> 原子领取
  -> P3 DocumentIntelligencePipeline.ensure（已有 Facts 直接复用）
  -> 冻结适用 Policy + 显式业务场景
  -> Review Agent V2 的 bounded review_windows
       -> targets 的类型 + 标题 + 当前原文 + party_role + contract_type 构造 Query
       -> Dense + BM25 -> RRF -> Rerank -> Top-K
       -> 当前用户/代次再次验证
       -> 保存本轮实际提供资料的快照
       -> Canonical Clause + Context + Policy + References -> Structured Output
       -> 当前窗口逐字证据 / 真实 ID / 引用关联 / Policy 等级验证
  -> 所有窗口结果合并去重
  -> 持久化条款与快照再验证
  -> 风险、Run 结果、历史展示指针原子发布
```

Query 每个目标最多取当前片段前 900 字符，总长最多 8,000；不是固定 clause_type 关键词，也不是整份合同一次查询。相关条款通过原有邻近/业务关联上下文提供。相同 Query 只在同一 Run 中缓存一次，下一次新 Run 重新召回当前 Ready 知识库。

完整模型输入 JSON 上限 24,000 字符，最多 8 个目标片段，保留超长条款的无损分段。为参考资料预留约 6,000 字符；资料必要时缩短后，只保存实际进入模型的片段快照。适用 Policy 不静默截断，预算不足明确失败。字符预算不等同于模型的精确 Token 数。

## 7. 典型输入输出例子

这是说明代码行为的示例，不是真实法律审查质量验收结论；下列 P/C/D/K 均表示数据库实际生成的 UUID，模型不能任意创造它们。

用户 A 在界面创建 Policy P v1：采购合同、buyer、付款期限原则上不超过 45 天、medium。上传 A 的《企业采购规范.docx》，生成 Document D v1 / generation=1，真实 Chunk K 原文为“付款期限原则上不超过45天。”。

用户上传合同 V1，明确输入 party_role=buyer、contract_type=procurement。P3 已发布 Canonical Clause C 原文“甲方应在收到发票后90天内付款。”。

Review 冻结 P v1；Query 来自 C 的真实文字和采购方场景；只在 A 的 Ready 文档中检索 K。模型可输出：

```python
RiskFinding(
    clause_id=C,
    risk_type="payment",
    risk_level="medium",
    evidence="甲方应在收到发票后90天内付款。",
    reason="付款期限90天超过本企业45天的审查要求。",
    recommendation="结合业务条件将期限调整为45天以内，并交法务确认。",
    policy_ids=[P],
    reference_citations=[
        ReferenceCitation(chunk_id=K, source_excerpt="付款期限原则上不超过45天。")
    ],
)
```

若无适用企业规则，policy_ids=[]，界面标为一般模型判断；有参考资料也不会伪装为强制 Policy。若 source_excerpt 不在本次提供的 K 中、C 不属于这轮检索目标、K 未召回，校验失败；不能靠返回一个看似 UUID 的值通过验收。

之后用户把规则改为 P v2（30 天），重建 D 的 generation=2：新 Run 读取 P v2 / 新 K；旧 Run 仍展示 P v1 / 旧 K 的名称、版本、原文和定位。V1 的 Canonical Clause ID、Blocks 和 Document Facts 不变。

## 8. 权限隔离、引用与迁移

每次检索先按实际 Contract owner 定义范围，SQL 同时限制 Chunk.user_id / Document.user_id、Ready、文档版本、generation 和 embedding_model；BM25 语料从该 SQL 读取，Dense SQL 本身也带相同 WHERE。不存在全库先搜完再仅在输出过滤用户的步骤。Rerank 只接收已授权候选。

文档列表、分类、重试、删除、下载、当前 Chunk 详情均按登录用户检查；其他用户访问返回 404。搜索请求不接受用户自行指定的 owner_id。

Run 快照保存实际 document_id / document_version / index_generation / chunk_id / owner_id / filename / category / chunk_text / locator / embedding_model，以及本次适用 clause_ids。Risk 保存 policy_ids 和 chunk_id/source_excerpt；Policy version 与文档元数据通过 Run 快照解析，而不是依赖可修改或删除的当前行。

`GET /api/contracts/{contract}/versions/{version}/analysis-runs/{run}/references/{chunk}` 验证合同版本归属和 Run 关联，再返回当时的快照；当前 Chunk 已删除也仍可解释历史。当前知识库 Chunk 接口只允许 Ready 检索资产，两类接口职责不同。

合同、参考文档和 metadata 在 Prompt 中均被视为不可信数据；禁止执行其中指令，Policy 优先于一般案例。不把企业规则说成国家法律，不宣称机器完成了最终法律合规核验。代码保障真实来源/ID/逐字引用；开放文本判断仍需法务复核，不能保证模型零幻觉。

迁移：`0007_contract_policy` → `0008_contract_knowledge`，继承第一批 `0006_review_v2`。本地业务库已升级到 0008，并通过 alembic check 和只读 schema audit。新增表和字段由 Alembic 管理，不在启动时自动建合同表。有 Policy/知识库文档或历史引用时 downgrade 明确拒绝；不删除共享 vector extension，不静默丢失历史解释依据。

## 9. 前端功能

- `/contracts/policies`：创建、修改、适用范围、版本、风险等级、启停、归档；过期编辑返回错误，可刷新。
- `/contracts/knowledge`：上传 PDF/DOCX、重复文件提示、分类、状态轮询、失败原因、索引重试/重建、原件下载、删除及清理失败重试；显示原件版本、索引代次、片段数/大小/真实页数。
- 合同上传与重新分析可明确指定身份、角色和合同类型，不猜甲乙方。
- 风险卡区分“企业规则”“一般模型风险判断”“RAG 参考资料（非强制政策）”，展示文档名称、版本、真实引用片段/页码和历史快照抽屉。
- 下载通过已有带认证 HTTP 客户端；401 清理登录态并跳转登录，不把过期用户留在错误页面。
- 浏览器回归覆盖规则全流程、知识库重建/分类/清理恢复、来源展示、业务场景、移动端和下载鉴权过期。

## 10. 实际验收、命令与边界

先完成 P4.6，再运行 Policy + V2 + Schema 阶段测试（32 passed）及前端构建，随后才开始 P4.7。

最终验收结果见下表；Mock 与真实外部调用分开记录：

| 验收 | 实际依赖与结果 |
|---|---|
| `pytest tests/contract tests/common -q` | 122 passed；SQLite 真实 Alembic/事务/API/解析器，外部 OSS/Embedding/Rerank/Review 显式模拟 |
| `npm run test:contract` | 18 passed；真实浏览器运行 React，HTTP API 使用模拟数据 |
| TypeScript / Vite build | 通过，3,350 modules |
| Contract + HTTP 客户端 ESLint | 通过 |
| compileall / Contract、公共模型与 Interview 独立 import | 通过 |
| 业务库 `alembic upgrade head` / `alembic check` / schema audit | 真实 PostgreSQL 通过，head=0008，audit issues/warnings 均空 |
| `scripts.contract.test_contract_migration_postgres` | 真实临时 PG 库 upgrade/audit/downgrade/reupgrade/check 通过，临时库已清理 |
| `scripts.contract.test_document_facts_concurrency` | 真实 PG Facts 发布及 Review V2 并发重试/领取/发布/迟到失败保护通过，临时库已清理；不调用真实 Review 模型 |
| `scripts.contract.test_contract_knowledge_live --models-only` | 真实 text-embedding-v3（1024维）和 qwen3-rerank 调用通过；仅模型 smoke，不当作完整链路 |
| `scripts.contract.test_contract_knowledge_live` | 真实 OSS → PDF/DOCX Parser → 真实 Embedding → PG pgvector + BM25 → RRF → 真实 Rerank 通过；跨用户隔离、真实 PDF 页码、并发领取、幂等、generation 重建通过；虚构原件及临时库已清理 |
| `scripts.contract.test_contract_demo_live --mock-review` | 真实业务库/OSS/PDF/DOCX/Facts、并发 V2/V3、重试与历史选择通过；Document Intelligence / Review 模型模拟，创建的虚构记录和 OSS 原件已清理 |
| 真实 Review LLM 质量评估 | 本批未执行，不把模拟结构化输出或真实检索成功当作法律风险质量验收 |

真实演示最初发现上传 `add_all([version, run])` 的 INSERT 顺序触发 PostgreSQL 外键错误，已改为父 Version flush 后再添加 Run，并补真实 SQLite 外键和 PG/OSS 演示回归。额外覆盖了索引发布中途失败回滚、迟到上传成功/失败、索引删除竞态、重启恢复和带业务数据的迁移降级保护。

Windows 沙箱内 asyncio 本地 socketpair/浏览器服务可能阻塞，测试与真实网络联调在获准的沙箱外执行。使用已有 `.venv-py312` / Python 3.12.10；Black 仅安装在被忽略的本地虚拟环境用于排版，没有新增项目运行依赖。

后端复验（在 backend_langchain 下，使用 .venv-py312）：

```powershell
.\.venv-py312\Scripts\python.exe -m alembic upgrade head
.\.venv-py312\Scripts\python.exe -m alembic check
.\.venv-py312\Scripts\python.exe -m scripts.contract.audit_contract_schema
.\.venv-py312\Scripts\python.exe -m pytest tests/contract tests/common -q
.\.venv-py312\Scripts\python.exe -m scripts.contract.test_contract_knowledge_live
```

前端复验：`npm run build`、`npm run test:contract`。

MVP 限制：最大 20MB、100 页文字 PDF、80,000 字符；没有 OCR、知识库聊天、来源版本编辑器、全规则审计日志、精确 Token 计费或持久化 Worker。BackgroundTasks 仍限单 API 进程，重启后显式失败并人工重试；目标服务器仍需安装原有依赖、升级迁移、部署后端及重新构建前端，不等同于本地验证后已经发布。

核心文件：`products/contract/models.py`、`api.py`、`db.py`、`schemas/{api,analysis}.py`、`agents/review_agent.py`、`workflows/review_workflow.py`、`knowledge.py`、`retrieval.py`；纯模型调用复用在 `common/integrations/retrieval_models.py`。测试在 `tests/contract/test_policy.py`、`test_knowledge.py` 及既有 Review/Schema 文件，真实检索脚本为 `scripts/contract/test_contract_knowledge_live.py`。前端新增两个管理页面，已有结果和上传工作台继续使用原组件体系。

API 对照资料：[DashScope Embedding](https://help.aliyun.com/zh/model-studio/text-embedding-synchronous-api)、[DashScope Rerank](https://help.aliyun.com/zh/model-studio/text-rerank-api)、[pgvector](https://github.com/pgvector/pgvector)。BM25 实际公式与 RRF 实现以本仓库 `retrieval.py` 为准。
