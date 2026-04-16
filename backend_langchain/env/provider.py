from __future__ import annotations

import logging
import os
from pathlib import Path

import yaml

CONF_DIR = Path(__file__).resolve().parent

__all__ = ["Settings", "RedisArgs", "load_yaml", "settings_conf"]

logger = logging.getLogger(__name__)


def load_yaml(file_path: str | Path) -> dict:
    with open(file_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


class RedisArgs:
    host = None
    port = None
    db = None
    password = None


class Settings:
    """从 env/*.yaml 加载配置；Django settings 中环境变量优先覆盖。"""

    def __init__(self) -> None:
        self.env = os.environ.get("DJANGO_ENV", "debug").strip()
        # 启动时固定打印，避免日志级别为 WARNING 时看不到环境信息。
        print(f"[env] DJANGO_ENV={self.env}", flush=True)
        logger.info("当前环境: %s", self.env)

        self._settings_debug = "settings_debug.yaml"
        self._settings_pro = "settings_pro.yaml"
        self._settings_test = "settings_test.yaml"
        self._settings_room_pro = "settings_room_pro.yaml"

        self.config = self._load_config()

        self.mysql_config = self._load_database_config()
        self.redis_config = self._load_redis_config()

        django_cfg = self.config.get("django") or {}
        self.yaml_secret_key = django_cfg.get("secret_key")
        self.yaml_debug = django_cfg.get("debug")
        _hosts = django_cfg.get("allowed_hosts")
        if isinstance(_hosts, list):
            self.yaml_allowed_hosts = [
                str(h).strip() for h in _hosts if str(h).strip()
            ]
        else:
            self.yaml_allowed_hosts = None

        self.llm_config = (
            self.config["llm"]
            if isinstance(self.config.get("llm"), dict)
            else {}
        )

    def _yaml_name_for_env(self) -> str:
        name = {
            "debug": self._settings_debug,
            "dev": self._settings_debug,
            "local": self._settings_debug,
            "production": self._settings_pro,
            "pro": self._settings_pro,
            "prod": self._settings_pro,
            "test": self._settings_test,
            "room_pro": self._settings_room_pro,
        }.get(self.env.lower(), self._settings_debug)
        return name

    def _load_config(self) -> dict:
        name = self._yaml_name_for_env()
        file_path = CONF_DIR / name
        if not file_path.is_file():
            if name in (self._settings_test, self._settings_room_pro):
                fallback = CONF_DIR / self._settings_debug
                if fallback.is_file():
                    logger.warning("缺少配置文件 %s，回退使用 %s", file_path, fallback)
                    file_path = fallback
        if not file_path.is_file():
            raise FileNotFoundError(f"没有可用的配置文件: {CONF_DIR / name}")
        return load_yaml(file_path)

    def _load_database_config(self):
        ret = self.config.get("mysql") or self.config.get("database")
        if ret is None:
            return {}
        return ret

    def _load_redis_config(self):
        ret = self.config.get("redis")
        if not ret:
            return None
        conf = RedisArgs()
        conf.host = ret.get("host")
        conf.port = ret.get("port")
        conf.db = ret.get("db")
        conf.password = ret.get("password")
        return conf

    @property
    def redis_url(self) -> str:
        conf = self.redis_config
        if not conf or conf.host is None:
            return os.environ.get("CELERY_BROKER_URL", "redis://lanchain_redis:6379/0")
        auth = f":{conf.password}@" if conf.password else ""
        port = conf.port if conf.port is not None else 6379
        db = conf.db if conf.db is not None else 0
        return f"redis://{auth}{conf.host}:{port}/{db}"

    def cfg_get(self, path: str, default=None):
        """点号路径，如 django.secret_key、mysql.host。"""
        cur: object = self.config
        if not path:
            return default
        for part in path.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur if cur is not None else default

    def apply_llm_env(self) -> None:
        """将 yaml 中 llm 段写入 os.environ（不覆盖已有变量）。"""
        mapping = {
            "agent_base_url": "LLM_AGENT_BASE_URL",
            "agent_api_key": "LLM_AGENT_API_KEY",
            "agent_model": "LLM_AGENT_MODEL",
        }
        for yk, ek in mapping.items():
            yv = self.llm_config.get(yk)
            if yv is not None and str(yv).strip() != "":
                os.environ.setdefault(ek, str(yv))


_SETTINGS: Settings | None = None


def settings_conf() -> Settings:
    global _SETTINGS
    if _SETTINGS is None:
        _SETTINGS = Settings()
    return _SETTINGS


if __name__ == "__main__":
    sp = settings_conf()
    print(sp.mysql_config)
