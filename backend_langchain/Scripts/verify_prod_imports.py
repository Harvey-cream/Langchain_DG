"""验证生产运行时依赖是否齐全（含建库所需 langchain-community 等）。

用法（backend_langchain 目录）：
    APP_ENV=production .venv\\Scripts\\python.exe scripts\\verify_prod_imports.py
    .venv\\Scripts\\python.exe scripts\\verify_prod_imports.py --list-installed-mb
"""
from __future__ import annotations

import argparse
import importlib
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# 模拟 Docker 生产环境
os.environ.setdefault("APP_ENV", "production")
os.environ.setdefault("SKIP_RAG_STARTUP_WARMUP", "1")

# (模块路径, 说明)
PROD_IMPORTS: list[tuple[str, str]] = [
    ("app.main", "FastAPI 入口"),
    ("app.settings", "配置"),
    ("app.db", "数据库"),
    ("app.routers.api", "Agent 路由"),
    ("app.routers.interview", "面试路由"),
    ("app.routers.user", "用户路由"),
    ("agent.graph_factory", "LangGraph"),
    ("agent.stream", "SSE 流式"),
    ("agent.rag.rag", "pgvector RAG"),
    ("agent.rag.embedding", "DashScope 嵌入"),
    ("agent.rag.skill_router", "Skill 路由"),
    ("agent.rag.retrieval_planner", "检索规划器"),
    ("agent.rag.rerank", "DashScope 精排"),
    ("agent.runtime.runtime_knowledge", "知识库 Agent 运行时"),
    ("agent.runtime.runtime_interview", "面试 Agent 运行时"),
    ("agent.tools.knowledge", "工具装配"),
    ("agent.tools.interview", "面试工具装配"),
    ("agent.tools.schema_tools", "内置工具 schema"),
    ("agent.hitl.human_loop", "PDF interrupt 解析"),
    ("agent.hitl.pdf_export_render", "PDF 渲染"),
    ("agent.mcp.mcp_multiserver", "MCP 客户端"),
    ("app.auth.jwt_token", "JWT RS256"),
    ("app.auth.sm2", "SM2 登录解密"),
    ("config.config", "LLM 配置"),
]

# 生产明确不需要、仅本地 HuggingFace 嵌入才用的包
DEV_ONLY_PACKAGES = frozenset(
    {
        "torch",
        "sentence_transformers",
    }
)

# 可从 requirements 去掉、由其它包自动拉取的顶层包
REDUNDANT_TOP_LEVEL = frozenset(
    {
        "cffi",
        "pycparser",
        "cryptography",  # PyJWT[crypto] 会拉
        "typing_extensions",
        "tzdata",
        "numpy",
        "python_multipart",
    }
)


def _mb(dist_name: str) -> float | None:
    try:
        import importlib.metadata as md

        dist = md.distribution(dist_name)
        total = 0
        for f in dist.files or ():
            try:
                total += (dist.locate_file(f)).stat().st_size
            except OSError:
                pass
        return total / (1024 * 1024)
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list-installed-mb", action="store_true", help="列出关键已装包体积")
    args = parser.parse_args()

    print(f"APP_ENV={os.environ.get('APP_ENV')}")
    failed: list[str] = []

    for mod, label in PROD_IMPORTS:
        try:
            importlib.import_module(mod)
            print(f"  OK  {mod} ({label})")
        except Exception as e:
            print(f"  FAIL {mod} ({label}): {type(e).__name__}: {e}")
            failed.append(mod)

    # PDF：fpdf2 写入 + 中文字体
    try:
        from fpdf import FPDF  # noqa: F401

        print("  OK  fpdf2 (PDF)")
    except Exception as e:
        print(f"  FAIL fpdf2: {e}")
        failed.append("pdf_deps")

    if args.list_installed_mb:
        print("\n关键包体积 (MB):")
        import importlib.metadata as md

        names = {d.metadata["Name"] for d in md.distributions()}
        heavy = [
            "pgvector",
            "asyncpg",
            "psycopg",
            "langchain-community",
            "numpy",
            "sqlalchemy",
            "langchain-core",
            "langgraph",
            "fpdf2",
            "dashscope",
        ]
        for pkg in heavy:
            if pkg not in names:
                continue
            sz = _mb(pkg)
            if sz is not None:
                print(f"  {pkg:28} {sz:8.1f} MB")

        dev_present = sorted(DEV_ONLY_PACKAGES & {n.replace("-", "_") for n in names})
        # normalize: check import names
        for pkg in DEV_ONLY_PACKAGES:
            try:
                importlib.import_module(pkg)
                dev_present.append(pkg)
            except ImportError:
                pass
        dev_present = sorted(set(dev_present))
        if dev_present:
            print(f"\n[WARN] 生产环境不应安装: {', '.join(dev_present)}")

    if failed:
        print(f"\n失败 {len(failed)} 项: {', '.join(failed)}")
        return 1
    print("\n全部生产导入通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
