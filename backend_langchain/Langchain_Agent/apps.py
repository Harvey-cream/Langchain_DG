"""应用启动时预热 RAG 单例（嵌入模型 + 各 Chroma 客户端），避免首次对话才加载。"""

from __future__ import annotations

import logging
import os
import threading

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class LangchainAgentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "Langchain_Agent"
    label = "langchain_agent"

    def ready(self) -> None:
        # Django debug 自动重载时，父进程也会执行 ready()；仅在子进程执行预热，避免重复加载 MCP。
        if os.environ.get("RUN_MAIN") not in {"true", "1"} and os.environ.get("DJANGO_ENV") == "debug":
            return
        if os.environ.get("SKIP_RAG_STARTUP_WARMUP", "").lower() in ("1", "true", "yes"):
            logger.info("Langchain_Agent: SKIP_RAG_STARTUP_WARMUP set, skip RAG warmup")
            return

        def _warm() -> None:
            try:
                from Langchain_Agent.tools import warmup_rag_singletons
                from common.skill_router import warmup_skill_phrase_cache
                from common.agent import warmup_agent_executors

                warmup_rag_singletons()
                logger.info("Langchain_Agent: RAG singletons warmup finished")
                warmup_skill_phrase_cache()
                logger.info("Langchain_Agent: skill phrase cache warmup finished")
                warmup_agent_executors()
                logger.info("Langchain_Agent: agent executors warmup finished")
            except Exception:
                logger.exception(
                    "Langchain_Agent: startup warmup failed (RAG / skill phrases / agents; "
                    "first request will retry)"
                )

        # 不阻塞 migrate / collectstatic；后台线程加载
        threading.Thread(target=_warm, name="rag-warmup", daemon=True).start()
