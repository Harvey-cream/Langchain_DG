"""应用配置：复用 env/*.yaml，环境变量优先。"""
from __future__ import annotations

import os
from pathlib import Path

from common.extend import apply_hf_mirror_default
from env.provider import settings_conf

BASE_DIR = Path(__file__).resolve().parent.parent
_S = settings_conf()
_S.apply_llm_env()
apply_hf_mirror_default()


def _env_first(env_name: str, yaml_path: str, default=None):
    v = os.environ.get(env_name)
    if v is not None and str(v).strip() != "":
        return v
    got = _S.cfg_get(yaml_path)
    return default if got is None else got


MYSQL_USER = _env_first("MYSQL_USER", "mysql.user", "root")
MYSQL_PASSWORD = _env_first("MYSQL_PASSWORD", "mysql.password", "root")
MYSQL_HOST = _env_first("MYSQL_HOST", "mysql.host", "localhost")
MYSQL_PORT = str(_env_first("MYSQL_PORT", "mysql.port", "3306"))
MYSQL_DATABASE = _env_first("MYSQL_DATABASE", "mysql.database", "langchain")

DATABASE_URL = (
    f"mysql+asyncmy://{MYSQL_USER}:{MYSQL_PASSWORD}"
    f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}?charset=utf8mb4"
)

MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"

_allowed = os.environ.get("APP_ALLOWED_HOSTS", os.environ.get("DJANGO_ALLOWED_HOSTS", "")).strip()
if _allowed:
    ALLOWED_HOSTS = [h.strip() for h in _allowed.split(",") if h.strip()]
else:
    _hosts = _S.cfg_get("django.allowed_hosts")
    ALLOWED_HOSTS = (
        [str(h).strip() for h in _hosts if str(h).strip()]
        if isinstance(_hosts, list)
        else ["*"]
    )
