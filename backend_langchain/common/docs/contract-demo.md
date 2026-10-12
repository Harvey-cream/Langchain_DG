# Contract Demo v0.2

长期架构基线：按真实职责保留 Router / Domain / Workflow / Agent / Infrastructure 边界，不为每个用例额外创建 Service、Port 和 Store；合同版本不可变，业务事实在 PostgreSQL，文件在 OSS，向量检索使用 pgvector。

本次实现：PDF/DOCX 上传、版本创建、后台文本解析、AI 结构化审查、结果与原文持久化、双栏工作台、版本选择、失败重试；同一合同版本只解析一次，每次重新分析保留独立记录，并可切换回任意历史成功结果。

## 运行

1. 安装 backend_langchain/requirements.txt；使用 Python 3.12。
2. 根 .env 配置 PostgreSQL、OSS 和 LLM_AGENT_API_KEY / LLM_AGENT_BASE_URL / LLM_AGENT_MODEL。不要提交密钥。
3. 按 README 准备 env/settings_pro.yaml。生产使用 APP_ENV=production。
4. 前端执行 npm ci 和 npm run build。
5. docker compose up -d --build，然后打开 /contracts。

合同表由 Alembic 管理；首次运行或部署新版前在后端目录执行 `python -m alembic upgrade head`。应用启动不创建或修改合同表。当前 head 为 `0008_contract_knowledge`，历史数据保留，不能直接删除历史记录。

## 展示与验证

登录 → 上传合同 → 选择客户或新建客户 → 开始分析 → 查看原文、摘要、金额、期限、义务、风险和修改建议。刷新后保留结果；上传新版本保留历史；重新分析保留独立分析记录。

可运行：python -m unittest discover -s tests/contract -p test_demo.py -v

## Demo 边界

- 最多 20 MB、100 页 PDF、8 万字符；不静默截断，扫描件提示改用文字版。
- P3 持久化 Version 文档事实；Review V2 分组读取真实 Canonical Clause 并只输出 RiskFinding，不重新提取条款。不接旧 docs1 知识库；P4.7 使用独立的用户私有参考文档表。我方身份、业务角色和合同类型可在上传或重新分析时填写；留空不推断身份，带适用范围的规则不会自动套用。
- BackgroundTasks 单 API 进程；任务使用原子状态抢占避免重复执行，版本状态与分析状态同步。启动时把中断任务和对应版本标记失败，用户可重试。下一步替换成 Redis Worker 和任务租约。
- HTTP 用例编排和只由接口使用的 ORM 查询直接位于 `products/contract/api.py`；后台审查与 Document Facts 共用的复杂事务保留在 `products/contract/db.py`。合同审查编排位于 `products/contract/workflows/review_workflow.py`，Parser / Reviewer / OSS 仍保留真实的外部能力边界；`products/contract/document/contract_jobs.py` 只负责组装后台分析依赖。
- 尚未支持自动导出、人工确认、Diff、邮件与谈判；分析结果不代表人工最终决策。
- 原合同只保存在私有 OSS，API 的原文与分析查询检查合同归属。

## 上线验收

前端构建、解析器测试通过后，还需用部署环境的 PostgreSQL / OSS / LLM 做真实上传与刷新验收。由维护者自行部署到目标服务器。

前端格式：`npm run format:contract`；浏览器回归：`npm run test:contract`（默认使用本机 Edge）。浏览器测试使用模拟 API，独立于下面的真实服务联调。

真实服务联调：`python -m scripts.contract.test_contract_demo_live`。会用虚构合同调用 OSS、PostgreSQL 和已配置的模型，并清理自己创建的记录和文件。加 `--mock-review` 可在保留真实数据库/OSS 的同时模拟模型结果，验证并发版本、无效文件、重试及用户隔离。

## Phase 0 基线（2026-09-18）

- 分析任务通过数据库原子更新领取，同一运行记录不会被重复执行。
- 合同版本同步记录 pending / parsing / analyzing / completed / failed 状态。
- 后台异常先回滚失败事务，再可靠写入失败状态和完成时间。
- 服务重启会同时结束中断的运行记录和对应版本，随后可人工重试。
- HTTP 与预留 HTTPS 配置均允许 20 MB 合同及 multipart 开销。

## Phase 1 分析资产化（2026-09-22）

- 解析文本按 `contract_version_id` 缓存。重新分析复用缓存，不重复下载和解析原文件。
- 每次分析创建新的 `contract_analysis_runs` 记录；旧的原始 JSON 结果、条款和风险均不覆盖。
- 成功结果自动成为当前展示记录；`contract_review_selections` 只保存展示指针，用户可切换到任意历史成功分析。
- AI 输出关键条款与风险的结构化关系，条款引用和风险证据必须能在合同原文中找到，否则自动重试一次后失败。
- 新增分析历史查询和选择接口；失败或进行中的记录保留在历史中，但不能被选为当前结果。

## Phase 1 验证记录（2026-09-22）

- 12 项后端解析、证据校验和工作流单元测试通过。
- TypeScript、Vite 生产构建和合同范围 ESLint 通过。
- 7 项 Playwright 浏览器场景通过，新增历史成功分析切换且不删除其他记录的回归测试。
- 部署前仍需在可用的 PostgreSQL / OSS 环境执行 `python -m scripts.contract.test_contract_demo_live --mock-review`，再用真实模型做一次完整上传验收。

## Demo 验证记录（2026-09-15）

- TypeScript 检查和 Vite 生产构建通过。
- 合同前端统一 Prettier 格式，分析轮询与结果展示已拆成 hook 和组件。
- 6 项 Playwright 浏览器场景通过：搜索与刷新、上传弹窗、轮询、重试、移动端布局、上传报错；移动端返回文字已补回归。
- 7 项解析/引用校验测试、5 项原合同领域检查、10 项模型故障转移测试通过。
- 真实 DOCX → OSS → PostgreSQL → 已配置 LLM → 持久化分析通过，测试合同返回 7 条风险；验证再次查询和用户隔离。
- 模拟模型、真实数据库及 OSS 的追加测试通过：无效文件拒绝、两个并发上传依次创建 V2/V3、重新分析。
- 测试仅使用虚构数据，创建的测试记录和 OSS 文件已清理。

部署仍需在目标服务器安装新增后端依赖并重新构建后端镜像；不要只替换前端 dist。Demo 限单进程，扫描件/OCR 与正式持久化 Worker 留待下一阶段；超长合同的最小分组审查已在 P4 第一批实现。

## P4 第一批（2026-10-08）

当前工作台展示 Version Facts / Canonical Clause 和独立 Run 的 V2 风险；V1 历史结果按原协议查询。版本条款随历史 Run 切换保持不变，风险可以打开关联条款原文。完整实现、数据关系、迁移和验收限制见 [P4-review-v2.md](./P4-review-v2.md)。上面的 Phase 0/1 和 Demo 验证记录是历史结果，不代表本次 P4 的真实模型质量验收。

## P4 第二批（2026-10-08）

`/contracts/policies` 管理当前用户的企业规则；`/contracts/knowledge` 上传、分类、重试、重建与删除私有 PDF/DOCX。Review 按条款组执行 pgvector + BM25 → RRF → 真实 Rerank；结果区分企业规则、一般模型判断和参考资料，历史结果保留当时版本及引用片段。空知识库不调用检索模型；已有知识库的模型故障会明确失败，不冒充完成 Hybrid Retrieval。

根 `.env` 需要 `DASHSCOPE_API_KEY`；Top-K、粗召回数、精排数、超时和 BM25 容量见 `.env.example`。业务库升级到 `0008_contract_knowledge` 后发布代码和前端。

真实检索验收：`python -m scripts.contract.test_contract_knowledge_live`（临时 PG 库 + 虚构 PDF/DOCX + 真实 OSS/Embedding/Rerank，自动清理）。`--models-only` 仅测试真实模型调用，不能代替完整链路验收。最新测试记录和限制见 [P4-policy-rag.md](./P4-policy-rag.md)。

## P4 第三批（2026-10-08）

Review 输出先通过 `quality.verify_review`：真实当前 Version 条款、可定位原文、适用规则版本和实际提供的 RAG 引用；窗口最多两次尝试，最终仍无效则失败，不发布伪成功结果。发布时 `db.complete_run` 再用数据库事实校验并保守去重，来源快照与报告、风险/展示指针一起提交，不覆盖旧 Facts 或历史依据。当前 Prompt=`review-v2-graph-v1`，Gate=`review-quality-v1`，迁移 head 仍为 `0008_contract_knowledge`，Graph 重构没有新 DDL。

### P4 Review Graph 架构优化

当前唯一审查入口是 `products/contract/agents/review/ReviewAgent`。每窗固定基础 RAG，然后由真实模型按需调用 `search_knowledge` / `get_related_clauses`，再执行 Structured Output 和 Gate。默认每窗最多 2 轮、4 次只读工具；显式设置 `CONTRACT_REVIEW_REACT_ENABLED=false` 可运行固定流程。Workflow 不再通过闭包保存来源，Graph 返回实际提供的引用，再由发布事务统一保存。节点图、字段、扩展方式、成本及 197 项后端 / 21 项浏览器回归见 [本轮完整报告](P4-review-graph.md)。

结果页展示来源校验、法律依据未核实、确定重复数量、相关条款和部分/空检索限制；没有新 Gate 记录的历史结果不追认为通过。来源真实不等于模型风险判断或法律结论正确，建议仍需人工确认。

全链路真实样例：`python -m scripts.contract.test_contract_knowledge_live --review`。在临时数据库通过实际 FastAPI 路由调用真实 OSS、PDF/DOCX Parser、Document Intelligence、Embedding、Hybrid Retrieval、Rerank、Review、Gate 和持久化；只注入测试身份与数据库 factory，不模拟模型。验收还覆盖 Policy/索引更新后新审查、Facts 复用和删除后的历史来源。虚构数据/原件及临时库自动清理。

本批后端 167 项、浏览器 21 项、前端构建、合同线 ESLint、真实 PostgreSQL 迁移/并发及服务联调通过。全项目 ESLint 尚有面试线存量 3 错误/2 警告，未扩大范围修改。完整九项验收和限制见 [P4-quality-gate.md](./P4-quality-gate.md)；不自动 Commit，不进入 P5。
