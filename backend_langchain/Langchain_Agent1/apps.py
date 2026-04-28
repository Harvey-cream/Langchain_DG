import logging
import os
import threading

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class LangchainAgent1Config(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "Langchain_Agent1"
    label = "langchain_agent1"

    def ready(self) -> None:
        # Django debug 自动重载时，父进程也会执行 ready()；仅在子进程执行预热，避免重复加载。
        if os.environ.get("RUN_MAIN") not in {"true", "1"} and os.environ.get("DJANGO_ENV") == "debug":
            return
        if os.environ.get("SKIP_RAG_STARTUP_WARMUP", "").lower() in ("1", "true", "yes"):
            logger.info("Langchain_Agent1: SKIP_RAG_STARTUP_WARMUP set, skip interview RAG warmup")
            return

        def _warm() -> None:
            try:
                from Langchain_Agent1.tools import warmup_interview_rag_singletons

                warmup_interview_rag_singletons()
                logger.info("Langchain_Agent1: interview RAG singletons warmup finished")
            except Exception:
                logger.exception("Langchain_Agent1: interview RAG warmup failed (first request will retry)")

        threading.Thread(target=_warm, name="interview-rag-warmup", daemon=True).start()
