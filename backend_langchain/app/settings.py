"""应用唯一配置入口：加载 env/settings_*.yaml，支持 ${VAR:-default}，供全项目读取。"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
CONF_DIR = BASE_DIR / "env"

# 唯一环境变量文件：仓库根 .env（cp .env.example .env）
load_dotenv(BASE_DIR.parent / ".env")

logger = logging.getLogger(__name__)

_ENV_REF = re.compile(r"\$\{([^}:]+)(?::-([^}]*))?\}")

_PRODUCTION_ENVS = frozenset({"production", "pro", "prod"})
_ENV_YAML: dict[str, str] = {
    "debug": "settings_debug.yaml",
    "dev": "settings_debug.yaml",
    "local": "settings_debug.yaml",
    "production": "settings_pro.yaml",
    "pro": "settings_pro.yaml",
    "prod": "settings_pro.yaml",
    "test": "settings_test.yaml",
    "room_pro": "settings_room_pro.yaml",
}


def _interpolate_string(value: str) -> str:
    def _repl(match: re.Match[str]) -> str:
        var = match.group(1).strip()
        default = match.group(2) if match.group(2) is not None else ""
        env_val = os.environ.get(var)
        if env_val is not None and str(env_val).strip() != "":
            return str(env_val).strip()
        return default

    return _ENV_REF.sub(_repl, value)


def _interpolate_tree(data: Any) -> Any:
    if isinstance(data, str):
        return _interpolate_string(data)
    if isinstance(data, dict):
        return {k: _interpolate_tree(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_interpolate_tree(v) for v in data]
    return data


def _load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    raw = data if isinstance(data, dict) else {}
    return _interpolate_tree(raw)


def resolve_app_env() -> str:
    raw = os.environ.get("APP_ENV", "").strip().lower()
    if raw:
        return raw
    legacy = os.environ.get("DJANGO_ENV", "").strip().lower()
    if legacy:
        logger.warning("DJANGO_ENV 已废弃，请改用 APP_ENV（当前仍按 DJANGO_ENV=%s 加载）", legacy)
        return legacy
    return "debug"


APP_ENV = resolve_app_env()
is_production = APP_ENV in _PRODUCTION_ENVS

print(f"[env] APP_ENV={APP_ENV}", flush=True)
logger.info("当前环境: %s", APP_ENV)


def _load_config() -> dict:
    yaml_name = _ENV_YAML.get(APP_ENV, "settings_debug.yaml")
    file_path = CONF_DIR / yaml_name
    if not file_path.is_file():
        if yaml_name in ("settings_test.yaml", "settings_room_pro.yaml"):
            fallback = CONF_DIR / "settings_debug.yaml"
            if fallback.is_file():
                logger.warning("缺少配置文件 %s，回退使用 %s", file_path, fallback)
                file_path = fallback
    if not file_path.is_file():
        raise FileNotFoundError(
            f"没有可用的配置文件: {file_path}（可从 env/{yaml_name.replace('.yaml', '.example.yaml')} 复制）"
        )
    logger.info("加载配置: %s", file_path)
    return _load_yaml(file_path)


_CONFIG = _load_config()
_APP_CONFIG = _CONFIG.get("app") or _CONFIG.get("django") or {}


def get_config() -> dict:
    return _CONFIG


def cfg_get(path: str, default: Any = None) -> Any:
    cur: Any = _CONFIG
    if not path:
        return default
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return default if cur is None else cur


def _section(name: str) -> dict[str, Any]:
    block = _CONFIG.get(name)
    return block if isinstance(block, dict) else {}


def llm_config() -> dict[str, str]:
    llm = _section("llm")
    return {
        "base_url": str(llm.get("base_url") or llm.get("agent_base_url") or "").strip(),
        "api_key": str(llm.get("api_key") or llm.get("agent_api_key") or "").strip(),
        "model": str(llm.get("model") or llm.get("agent_model") or "").strip(),
    }


def dashscope_config() -> dict[str, Any]:
    ds = _section("dashscope")
    dim = ds.get("embedding_dimensions", 1024)
    try:
        dim_int = int(dim)
    except (TypeError, ValueError):
        dim_int = 1024
    batch = ds.get("embedding_batch_size", 10)
    try:
        batch_int = int(batch)
    except (TypeError, ValueError):
        batch_int = 10
    return {
        "api_key": str(ds.get("api_key") or "").strip(),
        "embedding_model": str(ds.get("embedding_model") or "text-embedding-v3").strip(),
        "rerank_model": str(ds.get("rerank_model") or "qwen3-rerank").strip() or "qwen3-rerank",
        "embedding_dimensions": dim_int,
        "embedding_base_url": str(
            ds.get("embedding_base_url") or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        ).strip(),
        "embedding_batch_size": max(1, min(batch_int, 10)),
    }


def rag_config() -> dict[str, Any]:
    rag = _section("rag")
    rewrite_enabled = rag.get("query_rewrite_enabled")
    if rewrite_enabled is None:
        rewrite_enabled = True
    return {
        "collection": str(rag.get("collection") or "knowledge").strip() or "knowledge",
        "recall_k": int(rag.get("recall_k") or 40),
        "rerank_top_k": int(rag.get("rerank_top_k") or 5),
        "max_distance": float(rag.get("max_distance") if rag.get("max_distance") is not None else 0.65),
        "query_rewrite_enabled": bool(rewrite_enabled),
        "query_rewrite_max_questions": int(rag.get("query_rewrite_max_questions") or 4),
        "query_rewrite_context_turns": int(rag.get("query_rewrite_context_turns") or 2),
        "docs_agent": str(rag.get("docs_agent") or "docs1").strip() or "docs1",
        "docs_interview": str(rag.get("docs_interview") or "docs2").strip() or "docs2",
        "chunk_size": int(rag.get("chunk_size") or 600),
        "chunk_overlap": int(rag.get("chunk_overlap") or 80),
        "hf_embedding_model": str(rag.get("hf_embedding_model") or "BAAI/bge-large-zh-v1.5").strip(),
        "hf_embedding_batch_size": int(rag.get("hf_embedding_batch_size") or 32),
    }


def redis_url() -> str:
    redis_cfg = _section("redis")
    if redis_cfg.get("host"):
        password = redis_cfg.get("password")
        auth = f":{password}@" if password else ""
        port = redis_cfg.get("port") if redis_cfg.get("port") is not None else 6379
        db = redis_cfg.get("db") if redis_cfg.get("db") is not None else 0
        return f"redis://{auth}{redis_cfg['host']}:{port}/{db}"
    return os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")


# --- MySQL（yaml 已含 ${MYSQL_PASSWORD} 等插值）---
_mysql = _section("mysql")
MYSQL_USER = str(_mysql.get("user") or "root")
MYSQL_PASSWORD = str(_mysql.get("password") or "root")
MYSQL_HOST = str(_mysql.get("host") or "localhost")
MYSQL_PORT = str(_mysql.get("port") or "3306")
MYSQL_DATABASE = str(_mysql.get("database") or "langchain")

DATABASE_URL = (
    f"mysql+asyncmy://{MYSQL_USER}:{MYSQL_PASSWORD}"
    f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}?charset=utf8mb4"
)

# --- 应用 ---
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"

DEBUG = (
    _APP_CONFIG.get("debug")
    if isinstance(_APP_CONFIG.get("debug"), bool)
    else APP_ENV not in _PRODUCTION_ENVS
)
SECRET_KEY = str(_APP_CONFIG.get("secret_key") or "change-me-in-production")

_hosts = _APP_CONFIG.get("allowed_hosts")
ALLOWED_HOSTS = (
    [str(h).strip() for h in _hosts if str(h).strip()]
    if isinstance(_hosts, list)
    else ["*"]
)

# HuggingFace 镜像（建库脚本 / debug 嵌入）
os.environ.setdefault("HF_ENDPOINT", os.environ.get("HF_ENDPOINT") or "https://hf-mirror.com")
