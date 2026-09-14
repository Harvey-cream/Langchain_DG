# Contract Demo v0.1

长期架构基线：Product / Application / Workflow / Agent / Runtime / Harness / Infrastructure 分层；合同版本不可变，业务事实在 PostgreSQL，文件在 OSS，向量检索使用 pgvector。后续逐步实现 Clause、Policy、HITL、Diff、DOCX Patch、邮件与谈判。

本次实现：PDF/DOCX 上传、版本创建、后台文本解析、AI 结构化审查、结果与原文持久化、双栏工作台、版本选择、失败重试。

## 运行

1. 安装 backend_langchain/requirements.txt；使用 Python 3.12。
2. 根 .env 配置 PostgreSQL、OSS 和 LLM_AGENT_API_KEY / LLM_AGENT_BASE_URL / LLM_AGENT_MODEL。不要提交密钥。
3. 按 README 准备 env/settings_pro.yaml。生产使用 APP_ENV=production。
4. 前端执行 npm ci 和 npm run build。
5. docker compose up -d --build，然后打开 /contracts。

应用启动自动创建 contract_analysis_runs 表和版本唯一索引。若旧版本数据有重复 (contract_id, number)，启动会报错，应先审核并修复重复数据，不能直接删除历史记录。

## 展示与验证

登录 → 上传合同 → 选择客户或新建客户 → 开始分析 → 查看原文、摘要、金额、期限、义务、风险和修改建议。刷新后保留结果；上传新版本保留历史；重新分析保留独立分析记录。

可运行：python -m unittest discover -s tests/contract -p test_demo.py -v

## Demo 边界

- 最多 20 MB、100 页 PDF、8 万字符；不静默截断，扫描件提示改用文字版。
- 通过已配置的模型服务分析全文；通用商业审查，不接旧 docs1 知识库。
- BackgroundTasks 单 API 进程；启动时把中断任务标记失败，用户重试。不要使用多 worker 或多副本。下一步替换成 Redis Worker 和任务租约。
- 当前执行适配器集中在 infrastructure/document/contract_jobs.py；下一步将事务用例提取为 Application service 与 Repository/Job ports。
- 尚未支持自动导出、人工确认、Diff、邮件与谈判；分析结果不代表人工最终决策。
- 原合同只保存在私有 OSS，API 的原文与分析查询检查合同归属。

## 上线验收

前端构建、解析器测试通过后，还需用部署环境的 PostgreSQL / OSS / LLM 做真实上传与刷新验收。由维护者自行部署到目标服务器。

前端格式：`npm run format:contract`；浏览器回归：`npm run test:contract`（默认使用本机 Edge）。浏览器测试使用模拟 API，独立于下面的真实服务联调。

真实服务联调：`python -m scripts.test_contract_demo_live`。会用虚构合同调用 OSS、PostgreSQL 和已配置的模型，并清理自己创建的记录和文件。加 `--mock-review` 可在保留真实数据库/OSS 的同时模拟模型结果，验证并发版本、无效文件、重试及用户隔离。

## 本次验证记录（2026-09-15）

- TypeScript 检查和 Vite 生产构建通过。
- 合同前端统一 Prettier 格式，分析轮询与结果展示已拆成 hook 和组件。
- 6 项 Playwright 浏览器场景通过：搜索与刷新、上传弹窗、轮询、重试、移动端布局、上传报错；移动端返回文字已补回归。
- 7 项解析/引用校验测试、5 项原合同领域检查、10 项模型故障转移测试通过。
- 真实 DOCX → OSS → PostgreSQL → 已配置 LLM → 持久化分析通过，测试合同返回 7 条风险；验证再次查询和用户隔离。
- 模拟模型、真实数据库及 OSS 的追加测试通过：无效文件拒绝、两个并发上传依次创建 V2/V3、重新分析。
- 测试仅使用虚构数据，创建的测试记录和 OSS 文件已清理。

部署仍需在目标服务器安装新增后端依赖并重新构建后端镜像；不要只替换前端 dist。Demo 限单进程，扫描件/OCR、超长合同分批分析与正式持久化 Worker 留待下一阶段。
