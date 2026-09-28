# P3 执行总结

完成日期：2026-09-24。运行环境：现有 `.venv-py312`（Python 3.12.10）、本地 Docker PostgreSQL、真实 OSS。LLM 使用 mock/fake structured output，没有调用付费模型。

P2 的 Router → Service → Store/OSS/Dispatcher → Handler → Workflow 边界保持；新增一个 `DocumentIntelligencePipeline`，Document Facts 与 Review V1 并存。

## P3.1 Parser V2

- `products/contract/document/contract_parser.py`：`parse_contract(filename, data, version_id=...) -> ParsedDocument`。
- `OssContractDocumentParser.parse(context)` 返回同一个 ParsedDocument 类型；全文保留给 Review V1。
- ParsedDocument 包含 Version ID、全文、Blocks、真实 PDF page_count、parser_name 和 parser_version=v2。
- PDF 使用 pdfplumber，一次逐页提取后按文本行产生有序 Block，保留真实页码；扫描件明确失败。
- DOCX 保持正文段落/表格顺序；标题样式标记为 heading。表格以单元格 Tab、行换行序列化，按 XML 物理单元格遍历，避免合并单元格重复。DOCX page/page_count=None。
- Block UUID5 由 Version、parser_version、序号、类型、页码、文本生成。超长段落/表格按最多 10,000 字符精确切片，不丢字符、不纠错、不截断文档。
- 保留 20 MB、100 页 PDF、8 万字符的原有限制，不新增 OCR 或布局引擎。
- 本阶段累计 40 个 Contract 测试通过；后续补充了合并单元格和长段落测试。

## P3.2 DocumentBlock

- 新表 `contract_document_blocks`：id、version_id、sequence、text、type、page、created_at。
- `UNIQUE(version_id, sequence)`；Version 外键级联删除。
- 复用 `contract_version_contents`，不创建第二套 Content 表。
- Store 不自行 commit/rollback。同一套解析结果复用；已发布 Block 不隐式替换。
- 验证真实事务中的唯一约束、重复保存、级联删除、Content/Blocks 一起回滚。本阶段累计 42 个测试通过。

## P3.3 Section Detection

- `document_intelligence/sections.py`：规则支持第一条/第二条、第一章、一、二、1.、1、1.1、1.2 和 DOCX heading。
- 标题之间的连续 paragraph/table 保持源顺序；Section 是内存中间模型，不新增表。
- 没有可靠标题时调用局部 LLM fallback，使用 Pydantic `SectionExtraction`。
- 每个窗口最多 40 Blocks、约 12,000 字符（含 ID 等的字符余量估算，不是精确 token 预算）。不把长合同全文直接送入文档提取模型。
- fallback 必须按原顺序完整覆盖窗口，未知/重复/漏掉/错序 Block 均报错，最多两次尝试。
- 本阶段累计 49 个测试通过。

## P3.4 Clause Extraction

- `schemas/document.py`：`ClauseCandidate(title, clause_type, source_block_ids)`；`ClauseExtraction` 使用 Pydantic Structured Output。
- `extra=forbid`，不接受 LLM 提供的 original_text。未知类型归 other，也接受 unknown。
- Prompt 明确文档是不可信数据；禁止执行文档指令、编造 ID、补写原文、风险判断和建议。
- 使用 fake LLM 覆盖正常/多个条款、未知类型、非法 ID、重复 ID、错序和空输出。
- 本阶段累计 55 个测试通过。

## P3.5 Original Text Grounding

- `ground_candidates` 只通过真实 Block 重建原文。
- 先验证引用顺序，再按 sequence 排序；固定 `BLOCK_JOIN = "\n\n"`。
- 不 strip、不改标点、不纠错。Block 内的空格、Tab、换行逐字保留。
- Canonical ID 为确定性 UUID5；pages 仅由真实 source blocks 收集，DOCX 不伪造页码。
- 本阶段累计 56 个测试通过。

## P3.6 Validation / Coverage

- `document_intelligence/validation.py` 检查 Block 存在、同一 Version、序号、重复引用、Clause 非空、原文精确一致、页码来源以及跨 Clause 重复引用。
- 有意义 Block 定义：包含至少一个 `isalnum()` 字符（包含中文）；标题和表格也计入，纯空白/标点不计。
- Coverage = 被引用的有意义 Block 数 / 全部有意义 Block 数；分母为零时定义为 1.0。
- 任何未完整覆盖均生成 diagnostic，不设置任意失败阈值。非法 grounding 则失败，Clause 提取最多两次尝试。
- 本阶段累计 66 个测试通过。

## P3.7 Canonical ContractClause

- 新模型 `CanonicalContractClauseModel` / 新表 `contract_document_clauses`，归属 Version，完全没有 run_id。
- 字段：id、version_id、sequence、title、clause_type、original_text、source_block_ids、pages、intelligence_version、created_at。
- PostgreSQL source_block_ids 使用 JSONB；写入前从真实持久化 Blocks 再验证存在性、归属、顺序、原文和页码。
- `UNIQUE(version_id, sequence)`。重复处理复用同一套 Clause，不追加副本。
- 保留旧 `contract_clauses`、`contract_risks`、Run JSON、selection；Migration 不自动推断或迁移历史 Canonical Clause。
- 本阶段累计 67 个测试通过；最终补充了历史 Run/Clause/Risk 在 upgrade/downgrade 前后完全一致的测试。

## P3.8 Version-level Facts

- `DocumentIntelligencePipeline.ensure(context)` 负责缓存读取、Parser、Section、Clause、Grounding、Metadata 和原子发布。
- 新表 `contract_document_facts`：Version 主键、parser_version、intelligence_version、content_hash、extracted_metadata、Coverage 计数/比例、warnings、created_at。
- Metadata 只有 summary、parties、amount、duration、payment_terms。按局部窗口提取，程序按顺序去重合并，先 shadow persist；Review V1/前端仍读取原协议。
- 所有 Parser/OSS/LLM 调用均在事务外。发布时锁 Version，将 Content、Blocks、Canonical Clauses、Facts 完成标记放在同一短事务内。
- 缓存命中不再调用 Parser/文档 LLM。并发发布者返回首个已提交的完整事实集合。
- 旧 Version 在下一次显式分析时可 lazy reparse；不批量回填。更新旧 Content 前，将尚无源快照的历史成功 Run 绑定到旧正文，避免旧审查结果展示新解析文本。
- 当前 Contract 测试 67 passed，包含 PDF/DOCX 全链路、失败回滚、低 Coverage 持久化、Retry/History/Select、Risk→Legacy Clause 外键等。

# 最终 Document Intelligence 调用链

```text
ContractRouter
  -> contract_db 函数 / OSS
  -> BackgroundTasks.add_task(execute_analysis, run_id)
       -> run_contract_review
            -> contract_db.claim_run [短事务]
            -> DocumentIntelligencePipeline.ensure
                 -> contract_db.get_document_facts [短事务]
                 -> 缓存缺失:
                      OssContractDocumentParser
                        -> parse_contract -> ParsedDocument
                      detect_sections [规则 / 局部 LLM]
                      extract_validated_candidates [局部 LLM]
                      ground_candidates + validate_clauses
                      metadata [局部 LLM + 确定性合并]
                      contract_db.save_document_facts [原子短事务]
            -> contract_db.mark_analyzing [短事务]
            -> Review V1(document_text) [事务外]
            -> contract_db.complete_run [短事务]
```

# 最终数据关系

```text
Contract
  `-- ContractVersion
        |-- source file / OSS
        |-- ContractVersionContent                 1:1
        |-- ContractDocumentBlock[]                1:N
        |-- CanonicalContractClause[]              1:N
        |     `-- source_block_ids -> 同 Version Blocks
        |-- ContractDocumentFacts                  1:1
        |     `-- shadow metadata / coverage / versions
        |-- AnalysisRun[]                          1:N
        |     |-- 原协议 result JSON / source snapshot
        |     |-- Legacy ContractClause[]
        |     `-- ContractRisk[] -> Legacy Clause
        `-- ContractReviewSelection                1:1
              `-- 当前选中的成功 AnalysisRun
```

# LLM 使用位置

确定性：Parser、ID/序号、标题规则、窗口切分、source resolution、原文拼接、grounding、coverage、Metadata 合并、存储与幂等。

LLM：无可靠标题的 Section fallback、局部 Clause 分类/来源提取、局部 Metadata 提取，以及保持原样的 Review V1。

没有新增 Agent、Agent Runtime、LangGraph、Worker 或消息队列。

# Grounding 机制

`source_block_ids -> 查询真实 DocumentBlock -> 验证 Version/顺序/重复 -> 按 sequence 拼接 text -> Canonical.original_text`。

LLM Schema 不提供 original_text 字段；Pipeline 与持久化边界分别校验来源，保存后读取 Facts 也复核原文与 Coverage。此机制约束原文来源，不声称可以确定性证明 LLM 标题、分类或 Metadata 的语义绝对正确。

# Coverage

以有意义 Block 为单位，而不是按字符数或条款类型打分。未覆盖的正文能降低比例并留下 warnings；不因低覆盖率直接拒绝事实发布。零条 Clause、非法来源和伪造原文仍是错误。

# 幂等策略

同一 Version 的当前 parser_version/intelligence_version 已完成时直接 reuse。发布前锁定 Version，再次查缓存；即使两个 Pipeline 同时计算，后提交者也返回已发布结果。

一旦发布，当前实现不隐式覆盖不同版本的事实；未来改变 Parser/Intelligence 版本需要显式迁移。普通 Retry Analysis 只创建新的 Review Run，不重复生成 Blocks/Canonical Clauses。

# Database Migration

| Revision | 内容 | 状态 |
|---|---|---|
| 0003_document_blocks | Version-owned Blocks | 本地开发库已升级 |
| 0004_canonical_document_clauses | 独立 Canonical Clauses | 本地开发库已升级 |
| 0005_document_facts | Facts/Metadata/Coverage 完成标记 | 当前 head |

空 PostgreSQL 测试库完成 upgrade → check → audit → downgrade base → re-upgrade → check → audit；测试库随后删除。仅在临时库验证完整 downgrade，未回退用户的开发数据库。

本地开发库 `alembic check` 无新迁移操作，schema audit `ok=true`、issues/warnings 均为空。P3 只新增表，没有启动 DDL 或历史 Clause 回填。

# Backward Compatibility

Review V1 的 Prompt、ContractAnalysis Schema、analysis API 和前端字段保持。Reviewer 仍接收 document_text，仍生成旧版 clauses/risks。Risk 外键继续指向 Run-level Clause。

新 Facts 与 Review 结果分开保存；Review 失败可以保留已完成的 Facts，Retry 可复用。查看旧 Run 时优先读取该 Run 的源文本快照。

# Regression

后端命令在 backend_langchain 下使用 `.venv-py312/Scripts/python.exe`：

| 实际执行 | 结果 |
|---|---|
| `-m pytest tests/contract -q` | 77 passed |
| `-m compileall -q products/contract common alembic` | 通过 |
| 独立 import Pipeline / Job Handler / Router | 通过 |
| `-m scripts.contract.test_contract_api_smoke` | 18 项全部通过 |
| `-m scripts.contract.test_contract_migration_postgres` | 空 PostgreSQL 迁移往返与 audit/check 通过 |
| `-m scripts.contract.test_document_facts_concurrency` | 两个并发发布者只生成一套相同事实，通过 |
| `-m scripts.contract.test_contract_demo_live --mock-review` | 真实 OSS + PostgreSQL + PDF/DOCX + Review Clause/Risk + Retry/History/Select，通过 |
| `-m alembic upgrade head` / `-m alembic check` | 本地开发库已升级，无 Schema 漂移 |
| `-m scripts.contract.audit_contract_schema` | ok=true，无 issues/warnings |
| 前端 `npm run build` | TypeScript + Vite 通过 |
| 前端 `npm run test:contract` | 8 passed |

Playwright 首次沙箱运行用例通过但服务器清理未退出，沙箱外重跑正常退出（8 passed）。真实链路只使用合成合同；临时数据库、测试记录和对应 OSS 文件均清理。LLM 为 fake/mock，未做真实模型质量评估。

# Remaining Technical Debt

仅记录 P4 以后：Review Agent 收缩、RiskFinding V2、ContractPolicy、RAG、Revision/HITL、Diff、Negotiation、MQ Worker、Harness/Eval。本轮没有实现这些能力。
