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

```bash
cd backend_langchain
pip install -r requirements-dev.txt
export DASHSCOPE_API_KEY=sk-...
python Scripts/build_rag_knowledge.py
```

构建完成后 `docker compose` 挂载 `./backend_langchain/Langchain_knowledge/chroma`。
