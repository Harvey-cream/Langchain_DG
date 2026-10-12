# P4 第三批：Review Quality Gate / Evidence Grounding / 全量验收

> 历史阶段记录。后续 P4 架构优化已引入 Review LangGraph，本文 Gate 规则继续保留；现行入口、节点图、真实 Tool Calling 和 197 项后端验收见 [P4-review-graph.md](./P4-review-graph.md)。下文“不新增 LangGraph”仅描述本批当时范围。

实现与验收日期：2026-10-08。范围为 P4.8，延续 [Review V2](./P4-review-v2.md) 和 [Policy + RAG](./P4-policy-rag.md)。没有新增 Quality Agent、LangGraph、Planner、Graph RAG、Retry Framework 或 Harness；没有实现 P5，也没有自动提交 Commit。

本批完成的是来源、输出协议与内部一致性的确定性校验，以及真实服务全链路 smoke test。**来源校验通过不等于风险判断正确，更不等于已经完成法律合规核验。**

## 1. 修改清单与职责

- `products/contract/quality.py`：集中实现 `ReviewQualityError`、`locate_excerpt`、`verify_review` 和保守去重。它是纯 Python 校验模块，不是新的业务服务层或 Agent。
- `agents/review_agent.py`：窗口级质量校验、最多两次输出尝试、纠错反馈、远距离业务条款上下文、实际模型调用记录。
- `workflows/review_workflow.py`：审查结果复核、失败记录、检索事件和短事务发布；不改变 P3 文档事实。
- `db.py`：在 `complete_run` 写风险前，依据真实持久化条款和已授权的 Run 快照再次校验；去重、报告、风险和展示指针原子提交。
- `retrieval.py`：精排后重新检查资料是否仍可用，排除撤下的片段并记录数量，不补写虚假引用。
- `api.py`、`domain/review.py`：返回当前/最新 Run 的校验状态，统一 Prompt 标识 `review-v2-p4.8`。
- `common/config/failover.py`：仅补充本次异步调用实际成功的模型标签，避免把备用模型误记为主模型；不引入新故障转移机制。
- 前端 `types.ts`、`components/AnalysisResult.tsx`：来源校验、法律依据未核实、重复风险处理和检索降级提示；延续原条款、Policy 和参考资料抽屉。
- `tests/contract/test_quality.py`：45 项新增场景；`frontend_langchain/tests/contract.spec.ts`：新增 3 个浏览器场景。
- `scripts/contract/test_contract_knowledge_live.py`：新增 `--review`，覆盖真实 PDF/DOCX 上传、文档模型、检索模型、审查模型、发布和历史接口。
- 更新中英文 README、Demo 说明和各批次文档入口。

HTTP CRUD 仍在 `api.py`；ORM 仍集中在 `models.py`；数据库共享事务仍在 `db.py`。本批没有恢复 Service / Store / Repository / Port 层。

## 2. Quality Gate 的真实实现

主入口：

```python
verified = verify_review(
    result,
    persisted_clauses,
    context.version_id,
    policies=run.context_snapshot.get("policies", []),
    references=run.context_snapshot.get("references", []),
    owner_id=actual_contract_owner,
    party_role=run.party_role,
    contract_type=run.contract_type,
)
result = verified.result
run.context_snapshot = {
    **run.context_snapshot,
    "quality_gate": verified.report,
}
# 校验完成后才创建 ContractRiskModel、写结果并标记 completed。
```

校验按以下顺序执行，任何致命错误都会抛出带稳定 `code` 的 `ReviewQualityError`：

1. 强制 Pydantic 校验真实字段值；对已经是模型实例的结果也先 dump 再校验，不能用 `model_construct` / `model_copy` 绕过字段校验。模型必须明确返回 `risks`，没有风险应返回 `[]`，不能把漏字段当成无风险。
2. 检查审查条款集的重复 ID、Version；主条款和 related IDs 都必须真实存在，关联不能自引用或重复。
3. 检查上下文 ID、版本、owner 和适用范围，再定位合同证据与知识库引用。
4. 恢复为真实来源中的连续文字后，再检查实际保存形状的字段限制；例如空白展开后的引用仍不能超过 1,200 字符。
5. 复用 `schemas/analysis.py::validate_findings` 检查 Policy 等级下限、重复 Policy/引用、实际引用范围等。
6. 禁止额外的正式修改字段；对文本中的 ContractChange 引用或已批准/已执行正式修改声明作最低限度保护。Review 只提供待确认建议。
7. 规范化风险分类、标注未核实法律判断和参考资料性质；执行可解释的保守去重。

Run 的校验报告保存 `review-quality-v1`、Version ID、输入/保留/重复数量、Canonical IDs、每条风险的证据位置、Policy 版本、引用位置、提示、规范化前原始结果和被去重原始结果。原始结果记录不是新的公开法律结论。

报告里的字符位置是 Python 字符偏移 `[start_char, end_char)`，不是 PDF 坐标或 UTF-16 浏览器偏移；关联 PDF 页码继续来自 P3 的真实来源。

## 3. Grounding / Citation / Dedupe 规则

### 合同证据

`locate_excerpt` 首先做精确连续子串定位；找不到才允许 Unicode **canonical equivalence（NFD）** 和空白序列等价，并用来源位置映射回原文。恢复出的 `evidence` 始终是实际来源的切片，不是模型改写文本。

允许 `café` 与 `cafe\u0301`、已有换行与单个空格等价。不允许兼容字符转换 NFKC、删除标点、合并英文单词、修改数字、增删否定词、补回不存在的文字或模糊相似匹配。例如“赔偿金额不设上限”不能被修复成“赔偿责任不得超过合同金额”。

沿用并回归了 P3 的 `DocumentBlock.join_previous` / `join_block_text`：同一个原始块的技术性连续切片不人为插入换行；不同原始块仍保留边界。Parser、Canonical 组装和验证采用同一个拼接约定。旧的已发布 Facts 不重新解析、不覆盖。

### Policy

`prepare_review_context` 从数据库读取属于实际 owner、启用且未归档、符合用户明确输入角色/合同类型的规则，冻结完整版本快照。Gate 只接受这个 Run 确实加载的 ID，检查正整数 version、合法 severity、owner、范围和所引用等级下限。

没有 Policy 引用的风险显示为一般模型判断，不自动包装成违反企业规则。当前规则编辑/停用/归档不倒写旧 Run；下一次 Run 使用新版本。这里的“命中规则”表示模型引用了真实适用规则，**不是通过代码证明模型的业务判断必然正确**。

### RAG

从检索到发行引用快照分两步：

1. 检索 SQL 限制当前用户的 Ready 文档/片段，真实 dense + BM25 → RRF → Rerank；精排后排除已经撤下的片段。
2. `record_review_references` 在模型使用前检查实际 Chunk 与实际 Document 的对应关系、owner、版本、generation、名称、分类和真实文字，再把本次提供的原文及目标 clause_ids 写入 Run。

Gate 只允许模型引用本次已提供且关联主条款的 Chunk ID；`source_excerpt` 必须能定位到真实片段，document_id / document_version / generation 由已经授权的快照追溯，不让模型任意编写来源名称或版本。

历史快照发行后，知识库删除/重建不会使旧 Run 的来源消失，也不会让旧引用自动指向新 Chunk。历史引用 API 仍先校验 Run 所属用户。参考案例或模板不是天然权威法律依据；发现典型法律断言措辞时标注 `insufficient_legal_basis`，其余判断仍只是 `review_hint`。

### 去重

候选键为 `primary clause_id + normalized risk_type + grounded evidence`。分类进行 NFC、大小写和空白/连字符规范化；不能安全规范化的分类归为 `other` 并保留原值。证据比较仅使用已经定位的来源文字和安全空白/Unicode 规范化。

只有等级、reason、recommendation、related IDs、Policy IDs 和引用内容也一致时才判定为确定重复。报告保留规则名、输入序号、保留序号和被移除的完整原始风险。不同证据绝不因同类型而合并；同候选键但不同判断/建议/来源集合保留，并标注疑似重复。不使用 LLM、语义相似度或人工定义分类同义词词典偷偷吞掉结果。

## 4. 最小跨条款审查

原窗口约束保留：最多 8 个目标片段，完整输入 JSON 最多 24,000 字符，最多 4 个相关上下文条款；这不是精确 token 预算。

在窗口目标之外，按付款、交付、验收、解除、责任的关联类型和退款关键词寻找相关条款；优先给不同相关类型留位置，再考虑附近重复类型，避免远处交付/退款条款被近邻挤掉。

例如 Clause 2 全额预付、Clause 8 收款后 90 日交付、Clause 12 任何情况不退款：审查 Clause 2 的窗口可以包含另外两条；风险以 Clause 2 为 primary，evidence 定位付款原文，`related_clause_ids` 包含 8/12 的真实 ID。Agent 检查关联 ID 确实提供给当前窗口，最终 Gate 检查它们属于同一 Version，前端可以分别打开完整条款。完全相同的组合风险会去重。

这是 bounded context + 模型判断，不是全合同穷尽依赖分析。过长相关条款、超过 4 条的依赖或者跨目标切片边界的论证可能不能在单次窗口完整覆盖，不能承诺发现所有跨条款风险。

## 5. 实际 ReviewWorkflow 调用链与失败策略

```text
api.upload / api.analyze
  -> 提交 Version / AnalysisRun；提交后派发现有后台任务
  -> document.contract_jobs.execute_analysis
  -> run_contract_review
       T1 claim_run + mark_parsing，短事务提交
       DocumentIntelligencePipeline.ensure：已有 Facts 直接复用
       T3 prepare_review_context + mark_analyzing，短事务提交
       LangChainContractReviewer.review
         -> review_windows：targets + related clauses + frozen Policies
         -> clause_query -> retrieve_references：dense/BM25/RRF/Rerank
         -> record_review_references：真实库检查并发行快照
         -> structured LLM（include_raw=True）
         -> verify_review + 当前窗口范围校验
            不通过 -> 同窗口最多再尝试一次，附错误码/纠错提示
       Workflow verify_review：保留重复候选，尚不正式发布
       T4 db.complete_run：Version -> Run 行锁
         -> 用真实持久化事实和 Run 快照再次 Gate
         -> 全局保守去重
         -> RiskFinding + quality report + trace + result + selection
         -> 同一个事务提交 completed
  -> analysis API -> React 风险/条款/来源展示
```

窗口/Workflow 校验不能代替数据库最终发布防线；直接绕过 Agent 调用 `complete_run` 也不能保存伪造证据。各层调用复用同一套纯校验函数，不另复制一套规则。全局去重只在发布前进行，窗口内不静默删除原始重复项。

结构化输出、非法条款、虚构证据、Policy ID 或引用两次仍无效：Rollback，按 Version → Run 同一加锁顺序记录失败 Gate / 尝试信息，再 `fail_run`。不写 Risk、不写伪成功结果、不改旧的展示指针，迟到失败不能覆盖 completed。

空知识库/空检索属于非致命情况，不编引用；检索期间部分片段撤下可以排除并提示。服务超时、模型服务失败、未通过真实快照授权等不能伪装成 Hybrid Retrieval 成功。若资料在精排复查之后、快照发行之前再次被删除，采用保守失败而不是发行未经验证的引用；目前没有为这类竞态新增复杂自动重试框架。

Trace 保存 Prompt 版本、窗口目标 ID/切片偏移/长度/SHA-256、相关 IDs、实际提供的 Chunk IDs、输入长度和逐次调用状态/模型标识。优先使用模型响应的 metadata，再使用实际成功 fallback 配置标签；未知则留空，多个模型则 Run.model_name 为 `multiple`。这是服务返回或配置的标识，不是独立认证的模型来源证明。

## 6. 数据库和前端

本批不新增表或列，不增加 Alembic revision。复用 P4 第一/二批的 `AnalysisRun.context_snapshot`、`model_name`、`prompt_version` 和 V2 风险字段，当前 head 仍为 `0008_contract_knowledge`。从旧环境部署仍需要先升级到该 head。

API：历史 Run 返回本 Run 的质量报告；分析结果返回选中 Run 的 context/model/prompt，另外返回 `latest_quality_gate`。因此最新失败与当前展示的旧成功不会混为一个“校验通过”状态。

前端保留原文、来源条款/页码、相关条款、Policy 名称/版本/正文、RAG 文档/版本/generation/片段和历史快照。新增：

- “当前展示结果已通过来源校验，不代表法律结论正确”。
- 确定重复风险数量、变体保留说明、短证据等必要提示。
- “法律依据未核实 · 仅供复核提示”和“待核实的模型判断”。
- 空或部分检索限制，未补写缺失引用。
- 最新 Gate 失败提示；没有本版报告的历史结果不被追认为通过。

技术定位字段仍在 API 快照用于追溯，不把全部字段直接堆给普通用户。没有新增正式修改、批准或 Revision 功能。

## 7. 完整测试记录

使用已有 `.venv-py312` / Python 3.12.10；Windows 沙箱中 asyncio/本地服务受限的测试在获准的沙箱外执行。测试不引入新的业务运行依赖。

| 检查 | 结果与真实程度 |
|---|---|
| `pytest tests/contract tests/common -q` | **167 passed**；新增 Gate 场景 45 项，原有 122 项全部保留；SQLite/Alembic/事务/API/Parser 为真实代码，外部服务显式模拟 |
| `npm run test:contract` | **21 passed**；真实无头 Edge/React，API 使用模拟数据；包含移动端来源展示、失败保持旧历史、检索降级、Token 过期跳转 |
| `npm run build` | 通过，TypeScript + Vite，3,350 modules |
| 合同线 + 本次 HTTP 文件 + 浏览器测试 ESLint | 通过，0 错误/警告 |
| `npm run lint` 全项目 | 未通过：未改动的 Interview ChatPage / ChatInput / stream 共 3 错误、2 警告；未扩大范围修改面试线 |
| `compileall` | 合同、相关公共文件、脚本、测试通过 |
| 真实业务库 `alembic check` / schema audit | 通过；head=0008；无模型漂移，audit issues/warnings 和数据异常为空 |
| `scripts.contract.test_contract_migration_postgres` | 本批真实临时 PostgreSQL upgrade/audit/downgrade/reupgrade/check 通过，临时库清理 |
| `scripts.contract.test_document_facts_concurrency` | 本批真实 PostgreSQL Facts / Review 并发发布、领取、幂等、迟到失败保护通过，临时库清理；不冒充真实 Review 模型测试 |
| `scripts.contract.test_contract_demo_live --mock-review` | 最终代码真实业务库/OSS/PDF/DOCX、并发版本、重试、Facts 复用、历史选择和隔离通过；Document Intelligence / Review 模型明确模拟，虚构记录/原件清理 |
| `scripts.contract.test_contract_knowledge_live --review` | 真实 OSS/PDF/DOCX/Embedding/PG pgvector/BM25/RRF/Rerank + 真实 Document Intelligence/Review + Gate/结果发布通过；覆盖 Policy v1→v2、索引 generation 1→2、新审查 Facts 复用、删除后历史依据、跨用户接口隔离；使用虚构数据和临时库并清理 |

真实 Review 样例首次验收返回 3 条风险，并确实包含 Policy 引用和 RAG 引用，模型服务返回的标识为 `gemini-3.7-flash`。风险条数是当次实际输出，不是固定算法预期。真实脚本以 ASGI 客户端调用实际 FastAPI 路由；只注入测试登录身份和临时数据库 factory，不模拟文档/审查/检索模型。密码登录/JWT 密码学链路和目标服务器部署不是这个临时库脚本的验收范围。

单元覆盖包括：Unicode/空白定位及禁止模糊改写、非法/跨 Version ID、空白/缺字段/越界结构、Policy owner/适用范围/版本/等级、虚假/跨文档/跨用户引用、恢复后字段限制、保守去重与保留变体、远距离付款/交付/退款组合、最多两次尝试和错误反馈、fallback 真实标签、绕过 Agent 的数据库防线、失败零风险且旧结果/Facts 保留、部分资料撤下。

既有测试继续覆盖首次上传、重新审查、无 Policy、空知识库、无风险、检索/模型失败、V1 历史、用户隔离和迁移保护。Mock 场景与真实外部调用严格分开，不用真实检索成功替代真实 Review 验收，更不用少量真实输出冒充法律质量评估。

复跑命令（在 backend / frontend 各自目录运行）：

```powershell
.\.venv-py312\Scripts\python.exe -m pytest tests/contract tests/common -q
.\.venv-py312\Scripts\python.exe -m alembic check
.\.venv-py312\Scripts\python.exe -m scripts.contract.audit_contract_schema
.\.venv-py312\Scripts\python.exe -m scripts.contract.test_contract_migration_postgres
.\.venv-py312\Scripts\python.exe -m scripts.contract.test_document_facts_concurrency
.\.venv-py312\Scripts\python.exe -m scripts.contract.test_contract_demo_live --mock-review
.\.venv-py312\Scripts\python.exe -m scripts.contract.test_contract_knowledge_live --review
```

```powershell
npm run build
npm run test:contract
node node_modules/eslint/bin/eslint.js src/products/contract src/common/http/request.ts tests/contract.spec.ts --ext .ts,.tsx --report-unused-disable-directives --max-warnings 0
```

## 8. 尚未解决的问题

- Gate 验证来源真实和内部协议，不验证商业推理、条款是否真正违反 Policy 或法律效力；法律断言标注是最低限度的措辞检测，不是法律评估器。
- 去重刻意保守：语义相同但表述不同的风险可能仍保留；不确定项不会被静默丢弃。
- 跨条款审查受窗口/相关条款数量限制，不是所有依赖的穷尽检测；扫描件/OCR 和全面法律案例评测未在本批实现。
- 异步任务仍是现有后台方案，不是正式持久化 MQ Worker；生产多进程/断电恢复、目标服务器部署需后续专门验收。
- 企业知识库使用当前用户私有权限，不包含组织共享、复杂授权或资料权威性鉴定。
- 全项目 ESLint 仍有面试线存量问题；本批不声称整个项目没有任何缺陷。
- 本批真实模型 smoke 覆盖有限虚构合同，不能保证零幻觉、风险召回率、法律正确率或所有供应商行为；完整 Harness / Eval 留在 P11。

## 9. 验收判断

达到 P4.8 的工程验收目标：真实 Version Facts → Policy/RAG → Review → 确定性 Gate → 原子保存 → 来源展示链路可运行，失败不会发布不可追溯的成功结果，历史依据与用户隔离保留。P4 三批对应的已实现功能和核心回归完成。

不将此结论扩大为“法律审查质量已全面认证”“全部仓库检查为零问题”或“已经生产上线”。工作停止在 P4；未进入 P5，未自动 Commit。
