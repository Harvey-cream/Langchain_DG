"""应用启动时预热 RAG 单例与两个 Agent 图，避免首次对话才加载。"""

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
        if os.environ.get("RUN_MAIN") not in {"true", "1"} and os.environ.get("DJANGO_ENV") == "debug":
            return
        if os.environ.get("SKIP_RAG_STARTUP_WARMUP", "").lower() in ("1", "true", "yes"):
            logger.info("Langchain_Agent: SKIP_RAG_STARTUP_WARMUP set, skip warmup")
            return

        def _warm() -> None:
            try:
                from Langchain_Agent.tools import warmup_all_tool_singletons
                from common.agent import warmup_agent_executors
                from common.skill_router import warmup_skill_phrase_cache

                warmup_all_tool_singletons()
                logger.info("Langchain_Agent: RAG singletons warmup finished")
                warmup_skill_phrase_cache()
                logger.info("Langchain_Agent: skill phrase cache warmup finished")
                warmup_agent_executors()
                logger.info("Langchain_Agent: agent executors warmup finished")
            except Exception:
                logger.exception(
                    "Langchain_Agent: startup warmup failed (first request will retry)"
                )

        threading.Thread(target=_warm, name="agent-warmup", daemon=True).start()
