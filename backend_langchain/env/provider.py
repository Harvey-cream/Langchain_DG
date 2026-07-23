"""已废弃：请使用 app.settings。保留此模块仅为兼容旧 import。"""
from __future__ import annotations

import warnings

from app.settings import (
    APP_ENV,
    CONF_DIR,
    cfg_get,
    is_production,
    redis_url,
    resolve_app_env,
)

__all__ = [
    "Settings",
    "RedisArgs",
    "load_yaml",
    "settings_conf",
    "APP_ENV",
    "is_production",
]


def load_yaml(file_path):
    from pathlib import Path

    from app.settings import _load_yaml

    return _load_yaml(Path(file_path))


class RedisArgs:
    host = None
    port = None
    db = None
    password = None


class Settings:
    """兼容壳：委托 app.settings。"""

    def __init__(self) -> None:
        warnings.warn(
            "env.provider.Settings 已废弃，请直接使用 app.settings",
            DeprecationWarning,
            stacklevel=2,
        )
        self.env = APP_ENV
        self.config = _get_config_snapshot()
        self.postgres_config = (
            self.config.get("postgres") or self.config.get("database") or {}
        )
        redis_cfg = self.config.get("redis")
        self.redis_config = None
        if isinstance(redis_cfg, dict) and redis_cfg:
            conf = RedisArgs()
            conf.host = redis_cfg.get("host")
            conf.port = redis_cfg.get("port")
            conf.db = redis_cfg.get("db")
            conf.password = redis_cfg.get("password")
            self.redis_config = conf
        app_cfg = self.config.get("app") or self.config.get("django") or {}
        self.yaml_secret_key = app_cfg.get("secret_key")
        self.yaml_debug = app_cfg.get("debug")
        hosts = app_cfg.get("allowed_hosts")
        self.yaml_allowed_hosts = (
            [str(h).strip() for h in hosts if str(h).strip()]
            if isinstance(hosts, list)
            else None
        )
        self.llm_config = self.config.get("llm") if isinstance(self.config.get("llm"), dict) else {}

    @property
    def redis_url(self) -> str:
        return redis_url()

    def cfg_get(self, path: str, default=None):
        return cfg_get(path, default)

    def apply_llm_env(self) -> None:
        """已废弃：配置由 settings_*.yaml + ${ENV} 直接加载。"""
        warnings.warn("apply_llm_env 已废弃", DeprecationWarning, stacklevel=2)


def _get_config_snapshot() -> dict:
    from app.settings import get_config

    return get_config()


_SETTINGS: Settings | None = None


def settings_conf() -> Settings:
    global _SETTINGS
    if _SETTINGS is None:
        _SETTINGS = Settings()
    return _SETTINGS
