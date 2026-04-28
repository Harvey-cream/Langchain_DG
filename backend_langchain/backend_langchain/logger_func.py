from __future__ import annotations

import logging
import time
from typing import Any, Callable
from uuid import uuid4


def make_trace_event_logger(
    logger: logging.Logger,
    *,
    log_key: str,
    trace_prefix: str = "stream",
) -> Callable[..., None]:
    """
    生成统一格式的 trace 事件日志函数。

    使用示例：
        trace_event = make_trace_event_logger(logger, log_key="chat_stream_trace")
        trace_event("request_enter", user_id=1)
    """
    trace_start = time.perf_counter()
    trace_id = f"{trace_prefix}-{uuid4().hex[:10]}"

    def _trace_event(event: str, **extra: Any) -> None:
        elapsed_ms = int((time.perf_counter() - trace_start) * 1000)
        fields = {
            "trace_id": trace_id,
            "event": event,
            "elapsed_ms": elapsed_ms,
            **extra,
        }
        logger.info("%s %s", log_key, fields)

    return _trace_event


def call_trace_callback(
    trace_cb: Callable[..., None] | None,
    event: str,
    *,
    logger: logging.Logger | None = None,
    **extra: Any,
) -> bool:
    """
    安全调用 trace 回调：统一吞异常并可选写 debug。
    返回是否调用成功。
    """
    if not trace_cb:
        return False
    try:
        trace_cb(event, **extra)
        return True
    except Exception:
        if logger is not None:
            logger.debug("trace_cb(%s) failed", event, exc_info=True)
        return False


def _log_event(
    logger: logging.Logger,
    level: str,
    event: str,
    *,
    exc_info: bool = False,
    **fields: Any,
) -> None:
    payload = {"event": event, **fields}
    log = getattr(logger, level, logger.info)
    log("%s %s", event, payload, exc_info=exc_info)


def log_info_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    _log_event(logger, "info", event, **fields)


def log_warning_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    _log_event(logger, "warning", event, **fields)


def log_error_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    _log_event(logger, "error", event, **fields)


def log_exception_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    _log_event(logger, "error", event, exc_info=True, **fields)
