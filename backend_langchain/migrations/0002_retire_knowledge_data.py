"""Retire Knowledge product data. Apply explicitly with the project's migration runner.

Phase D：Knowledge 产品退休后，`agent_documents` / `agent_web_sources` 不再有任何
ORM 模型与 API 引用。此处把它们改名归档（可回滚），不从数据库删除任何行。

`rag_embeddings` 保持 KEEP：按 plan「不直接 DROP；先按 corpus 统计、备份、迁移和回滚」，
本脚本只输出 corpus 行数供审查，不删除 `corpus in ('agent','user')` 的知识库向量。

用 psql / 项目迁移运行器显式执行后，验证：
    SELECT corpus, count(*) FROM rag_embeddings GROUP BY corpus ORDER BY corpus;
"""

RETIRE_KNOWLEDGE_DATA_SQL = """
-- 1) 归档 Knowledge 专属业务表（改名即停用，数据完整保留，可回滚）
ALTER TABLE IF EXISTS agent_documents RENAME TO agent_documents_archive;
ALTER TABLE IF EXISTS agent_web_sources RENAME TO agent_web_sources_archive;

-- 2) rag_embeddings 知识库 corpus 统计（仅审查，不删除）
-- SELECT corpus, count(*) AS rows FROM rag_embeddings GROUP BY corpus ORDER BY corpus;

-- 回滚：
-- ALTER TABLE IF EXISTS agent_documents_archive RENAME TO agent_documents;
-- ALTER TABLE IF EXISTS agent_web_sources_archive RENAME TO agent_web_sources;
"""
