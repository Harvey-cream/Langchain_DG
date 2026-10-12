# P4 第一批：Review V2 / RiskFinding

> 历史阶段记录。当前 Review 编排已完成后续 LangGraph 重构；现行入口、节点图和 197 项后端验收见 [P4-review-graph.md](./P4-review-graph.md)。下文“没有引入 LangGraph”描述第一批当时的范围。

实现日期：2026-10-08。范围：P4.1–P4.5。接口和 HTTP 查询保持在 `products/contract/api.py`，共享事务保持在 `db.py`；没有恢复 Service / Store / Repository，也没有引入 LangGraph、Planner 或新 Agent。

后续状态：本文件记录第一批当时的验收，不代表当前环境仍被 PostgreSQL 阻断。第二批已恢复真实数据库/OSS 联调，并补齐 [Policy 和 RAG](./P4-policy-rag.md)；第三批增加确定性 Gate 和真实文档/审查模型样例验收，最新实现与验收见 [P4-quality-gate.md](./P4-quality-gate.md)。

## 各阶段实际实现

- P4.1：`schemas/analysis.py` 新增 `RiskFinding`、`ReviewResult` 和 `validate_findings`。禁止额外字段、空白证据/原因/建议、非法风险等级；允许零个风险、同一条款多个不同风险。只有 `high / medium / low`。
- P4.2：`agents/review_agent.py` 的 `LangChainContractReviewer.review(clauses, metadata=..., our_party=...)` 消费真实 Canonical Clause。输入按序分组，最大 8 个目标片段、目标 JSON 约 14,000 字符、完整输入 JSON 最多 24,000 字符；超长单条款逐段无损提供，保留同一个 clause_id 和 source_offset。最多携带 4 个附近/付款/交付/验收/违约/解除相关条款；只有完整条款能放进预算时才加入上下文。摘要等上下文限制长度，目标条款原文不丢字符。预算为序列化字符数，不是精确 token 数。
- P4.2 立场：上传 multipart `our_party` 或 analyze JSON `our_party` 是用户明确提供的签约主体/甲乙方角色，每次 Run 独立保存。P3 parties 提供候选及上下文，留空不推断我方身份，按中立立场审查。模型仅给出待确认的审查建议。
- P4.3：`review_workflow.py` 在 Facts ensure 后调用 V2；`db.complete_run` 锁 Version 和 Run，验证 Run 的 Version 和所有风险的 Canonical Clause/证据/相关条款。只写风险、Run 结果和展示指针，短事务一起提交。相同结果的重复提交直接返回；不能覆盖已完成结果；迟到的失败不能改坏成功记录，成功/失败都按 Version → Run 的顺序加锁。重试复用 P3 Facts。
- P4.4：现有 analysis/analysis-runs/select API 保留地址，增加 review_version、our_party、facts、canonical_clauses，V2 风险输出 clause_id/risk_type/evidence/recommendation/related_clause_ids。原有 evidence_text/suggestion 等字段保留。前端展示 Version 摘要、双方、金额、期限、付款条件、Canonical Clause 原文，并在条款下展示本次风险；支持主/相关条款原文抽屉、覆盖率提示、空风险结果、失败后查看已发布事实、历史选择和手机布局。
- P4.5：历史 Run 由迁移标记为 v1，保留旧 result JSON、contract_clauses 和风险的旧 clause_id 外键。新 ORM/API Run 使用 v2，停止写入旧 Clause 表。读取历史 Run 保留其源文本快照，不猜测旧 Clause 和 Canonical Clause 的映射。排序优先 attempt，避免同一时间戳随机 UUID 让旧 Run 被当作最新任务。

## 输入输出

V1：`document_text -> ContractAnalysis(summary/parties/clauses/risks)`。

V2：`CanonicalContractClause[] + P3 metadata + our_party -> ReviewResult(risks=[])`。

```python
class RiskFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    clause_id: UUID
    risk_type: str                 # 1..64 字符，不能为空白
    risk_level: Literal["high", "medium", "low"]
    evidence: str                  # 主关联条款中逐字一致的连续原文
    reason: str
    recommendation: str
    related_clause_ids: list[UUID] # 默认 []，最多 8 条，必须存在于同 Version

class ReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    risks: list[RiskFinding]        # 允许 []
```

本批没有增加 policy_ids/reference_ids 或对应表，留待第二批需求确定后接入。

## 真实调用链与数据关系

```text
upload / analyze API
  -> 创建 V2 AnalysisRun，提交后 BackgroundTasks(execute_analysis)
  -> db.claim_run，原子领取
  -> DocumentIntelligencePipeline.ensure，读取/生成并原子发布 Version Facts
  -> db.mark_analyzing
  -> Reviewer.review(facts.clauses, facts.metadata, our_party)
       -> review_windows -> Structured Output -> 窗口引用/逐字证据校验 -> 合并去重
  -> 工作流 validate_findings
  -> db.complete_run，重新检查持久化条款，原子提交结果/风险/选择记录
失败 -> 先回滚当前事务 -> db.fail_run，保留已发布的 Facts 和历史成功结果

ContractVersion
  |- DocumentContent / DocumentBlock[] / CanonicalClause[] / DocumentFacts
  |- AnalysisRun V1 -> Legacy Clause[] -> Legacy Risk（原 clause_id）
  |- AnalysisRun V2 #1 -> Risk[] -> Canonical Clause（canonical_clause_id）
  |- AnalysisRun V2 #2 -> Risk[] -> 同一套 Canonical Clause
  `- ReviewSelection -> 当前选择的成功 Run
```

API 的 V2 `clause_id` 对应数据库 `canonical_clause_id`。数据库原 `clause_id` 仅用于历史 V1；CheckConstraint 禁止一条风险同时占用两种条款外键。相关条款用 JSON 存储，写入前检查 ID、Version、重复引用和自引用。API 所有版本查询/重试/历史选择先验证用户、合同、版本归属。

## P3 原文拼接修复

DocumentBlock 新增 `join_previous`。Parser 仅对同一原始段落/表格的续块设置 True；`join_block_text` 对连续续块直接拼接，对独立来源仍使用两个换行。Grounding、Validation、持久化与 schema audit 使用相同规则。新 DOCX 正文也不再在续块之间插入人工段落序号。

迁移对已有 Blocks 设置 False，保留已有 Canonical 原文和历史 Review 快照，不猜测旧切块边界，也不自动覆盖已发布 Facts。已发布的旧解析资产要重建仍需显式迁移。

## Alembic

`0006_review_v2` 继承 `0005_document_facts`：

- AnalysisRun：review_version、our_party。
- ContractRisk：canonical_clause_id 外键/索引、risk_type、related_clause_ids、互斥来源 CheckConstraint。
- DocumentBlock：join_previous。

新增列有兼容默认值，不删除或重新映射历史数据。已有 V2 Run 时 downgrade 会明确拒绝，防止丢失协议和身份；空库/仅 V1 库可做安全往返验证。部署先 upgrade，再发布读取新列的代码。

## 修改文件

新增：

- `backend_langchain/alembic/versions/0006_review_v2.py`
- `backend_langchain/tests/contract/test_review_v2.py`
- `backend_langchain/common/docs/P4-review-v2.md`

修改后端：

- `products/contract/agents/review_agent.py`
- `products/contract/api.py`、`db.py`、`models.py`
- `products/contract/schemas/analysis.py`、`schemas/api.py`
- `products/contract/domain/document.py`、`domain/review.py`
- `products/contract/workflows/review_workflow.py`
- `products/contract/document/contract_parser.py`
- `products/contract/document_intelligence/clauses.py`、`validation.py`
- `scripts/contract/audit_contract_schema.py`
- `scripts/contract/test_contract_demo_live.py`
- `scripts/contract/test_document_facts_concurrency.py`
- `tests/contract/test_demo.py`、`test_document_parser.py`、`test_document_pipeline.py`、`test_review_behavior.py`、`test_schema_management.py`

修改前端：

- `src/products/contract/types.ts`、`api.ts`
- `src/products/contract/hooks/useContractWorkspace.ts`
- `src/products/contract/ContractListPage.tsx`、`ContractVersionPage.tsx`
- `src/products/contract/components/AnalysisResult.tsx`、`AnalysisHistory.tsx`
- `src/products/contract/contract.css`
- `tests/contract.spec.ts`

文档：根目录 README.md / README.en.md、common/docs/contract-demo.md、P3-document-intelligence-v2.md。

## 本轮实际验收

Python 使用现有 `.venv-py312`，3.12.10；模型使用 fake Structured Output，不调用付费模型。Windows 沙箱内 asyncio socketpair 和本机测试服务器卡住，沙箱外执行正常。

| 验收 | 实际结果 |
|---|---|
| Contract pytest | 94 passed，包括 SQLite 真实事务、并发领取、失败状态保护、V1 迁移数据保持、upgrade/check/downgrade 往返、V2 数据降级保护、ASGI API |
| Backend compileall / Contract 独立 imports | 通过 |
| Frontend TypeScript + Vite build | 通过 |
| Contract 前端 ESLint / git diff --check | 通过 |
| Playwright | 13 passed；8 个既有场景及 5 个 V2 工作台场景，使用模拟 HTTP API |
| 本地 PostgreSQL alembic upgrade head | 失败，localhost:5433 无服务，连接超时 |
| 本地 PostgreSQL alembic check | 同一数据库连接阻断，尚未通过 |
| PostgreSQL 临时库迁移 / 并发验收脚本 | 在连接数据库阶段阻断，未完成实际数据库验收 |
| 真实 OSS 上传 / 真实模型质量评估 | 本轮未执行 |

已尝试启动现有 Docker Desktop，但其日志记录 Ingest listener 的 `sailor-ingest.sock` 无法访问，Docker 引擎没有起来。本次没有重置 Docker 或改动其数据。PostgreSQL 恢复后需运行后端 `alembic upgrade head` / `alembic check`、`scripts.contract.test_contract_migration_postgres`、`scripts.contract.test_document_facts_concurrency`；后者包含真实行锁下的 V2 并发重试、原子领取、重复发布及迟到失败测试场景，本轮未实际跑到这些场景。真实 OSS 验收使用已适配 V2 的 `scripts.contract.test_contract_demo_live --mock-review`。

P4.6、Policy、RAG、Revision、HITL、正式 Worker 没有在本批实现；没有自动提交 Git Commit。
