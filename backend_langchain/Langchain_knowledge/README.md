# Langchain_knowledge

- **docs1 / docs2**：源文档，随 git 提交
- **chroma**：向量库构建产物，勿提交；部署后在服务器执行 `Scripts/build_rag_knowledge.py`

## 目录约定

```
docs1/<domain>/**/*.md   → 超级智能体（agent）
docs2/<domain>/**/*.pdf  → 面试助手（interview）
chroma/                  → DashScope text-embedding-v3（1024 维），git 忽略
```

## 服务器构建向量库

`.env` 中配置好 `DASHSCOPE_API_KEY` 后，在仓库根目录：

```bash
# 方式 1：容器内建库（backend 未运行或已 docker compose down）
docker compose run --rm backend python Scripts/build_rag_knowledge.py

# 方式 2：宿主机（backend_langchain 目录，已 pip install -r requirements.txt）
cd backend_langchain
python Scripts/build_rag_knowledge.py
```

构建完成后 `docker compose` 挂载 `./backend_langchain/Langchain_knowledge/chroma`。
