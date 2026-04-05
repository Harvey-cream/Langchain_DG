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
        if os.environ.get("SKIP_RAG_STARTUP_WARMUP", "").lower() in ("1", "true", "yes"):
            logger.info("Langchain_Agent: SKIP_RAG_STARTUP_WARMUP set, skip RAG warmup")
            return

        def _warm() -> None:
            try:
                from Langchain_Agent.tools import warmup_rag_singletons

                warmup_rag_singletons()
                logger.info("Langchain_Agent: RAG singletons warmup finished")
            except Exception:
                logger.exception("Langchain_Agent: RAG warmup failed (first request will retry)")

        # 不阻塞 migrate / collectstatic；后台线程加载
        threading.Thread(target=_warm, name="rag-warmup", daemon=True).start()
