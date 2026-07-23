# Langchain_knowledge

- **docs1 / docs2**：源文档，随 git 提交
- **向量库**：写入 PostgreSQL `rag_embeddings`（pgvector）；部署后执行 `Scripts/build_rag_knowledge.py`

## 目录约定

```
docs1/<domain>/**/*.md   → 超级智能体（agent）
docs2/<domain>/**/*.pdf  → 面试助手（interview）
```

向量存在 Postgres 业务库同库表 `rag_embeddings`（DashScope text-embedding-v3，1024 维）。

## 服务器构建向量库

`.env` 中配置好 `DASHSCOPE_API_KEY` 与 Postgres 后，在仓库根目录：

```bash
# 方式 1：容器内建库
docker compose run --rm backend python Scripts/build_rag_knowledge.py

# 方式 2：宿主机（backend_langchain 目录，已 pip install -r requirements.txt）
cd backend_langchain
python Scripts/build_rag_knowledge.py
```
