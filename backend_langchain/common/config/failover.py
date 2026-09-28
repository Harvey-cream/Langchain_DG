"""LLM 顺序兜底：主模型调用失败时自动顺延到下一个模型。

为什么不用 langchain 自带的 ``.with_fallbacks()``：
它返回的 ``RunnableWithFallbacks`` **没有** ``bind_tools`` /
``with_structured_output``，本项目在工具调用 / 结构化输出调用点会直接
``AttributeError``。因此这里用一个只暴露所需方法的小包装类。

约定：任一模型抛异常只跳过它；全部失败才抛出**最后一个**异常，且
**保留原异常类型**（上层可能按 SDK 异常类型分流）。
"""
from __future__ import annotations

import logging
from typing import Any, AsyncIterator, Optional, Sequence

logger = logging.getLogger(__name__)


def _label(model: Any) -> str:
    for attr in ("model_name", "model"):
        name = getattr(model, attr, None)
        if isinstance(name, str) and name:
            return name
    return type(model).__name__


class _FailoverRunnable:
    """对一组签名相同的 Runnable 做顺序兜底（invoke / ainvoke / astream）。"""

    def __init__(self, runnables: Sequence[Any], labels: Sequence[str]):
        if not runnables:
            raise ValueError("fallback chain is empty")
        self._runnables = list(runnables)
        self._labels = list(labels)

    def _warn(self, index: int, exc: BaseException) -> None:
        logger.warning(
            "model=%s failed (%s: %s), trying next",
            self._labels[index],
            type(exc).__name__,
            exc,
        )

    def invoke(self, input: Any, config: Optional[Any] = None, **kwargs: Any) -> Any:
        last: BaseException | None = None
        for index, runnable in enumerate(self._runnables):
            try:
                if config is None:
                    return runnable.invoke(input, **kwargs)
                return runnable.invoke(input, config, **kwargs)
            except Exception as exc:  # noqa: BLE001 — 有意兜底所有模型异常
                last = exc
                self._warn(index, exc)
        assert last is not None
        raise last

    async def ainvoke(self, input: Any, config: Optional[Any] = None, **kwargs: Any) -> Any:
        last: BaseException | None = None
        for index, runnable in enumerate(self._runnables):
            try:
                if config is None:
                    return await runnable.ainvoke(input, **kwargs)
                return await runnable.ainvoke(input, config, **kwargs)
            except Exception as exc:  # noqa: BLE001
                last = exc
                self._warn(index, exc)
        assert last is not None
        raise last

    async def astream(
        self, input: Any, config: Optional[Any] = None, **kwargs: Any
    ) -> AsyncIterator[Any]:
        # 仅在「尚未产出任何 chunk」时允许顺延；已开始输出则不能回退（否则重复输出）。
        last: BaseException | None = None
        for index, runnable in enumerate(self._runnables):
            emitted = False
            try:
                stream = (
                    runnable.astream(input, **kwargs)
                    if config is None
                    else runnable.astream(input, config, **kwargs)
                )
                async for chunk in stream:
                    emitted = True
                    yield chunk
                return
            except Exception as exc:  # noqa: BLE001
                if emitted:
                    raise
                last = exc
                self._warn(index, exc)
        assert last is not None
        raise last


class FailoverLLM:
    """持有有序模型列表；invoke / bind_tools / with_structured_output 均按序兜底。

    与 ChatOpenAI 保持鸭子类型兼容，因此调用方（业务节点 / 图 / 工具）无需改动，
    既可直接 ``invoke/ainvoke/astream``，也可链式 ``bind_tools(...)`` /
    ``with_structured_output(...)``。
    """

    def __init__(self, models: Sequence[Any], labels: Optional[Sequence[str]] = None):
        models = [m for m in models if m is not None]
        if not models:
            raise ValueError("FailoverLLM requires at least one model")
        self._models = list(models)
        self._labels = list(labels) if labels is not None else [_label(m) for m in models]
        self._runner = _FailoverRunnable(self._models, self._labels)

    @property
    def models(self) -> list[Any]:
        return list(self._models)

    @property
    def labels(self) -> list[str]:
        return list(self._labels)

    def invoke(self, input: Any, config: Optional[Any] = None, **kwargs: Any) -> Any:
        return self._runner.invoke(input, config, **kwargs)

    async def ainvoke(self, input: Any, config: Optional[Any] = None, **kwargs: Any) -> Any:
        return await self._runner.ainvoke(input, config, **kwargs)

    def astream(
        self, input: Any, config: Optional[Any] = None, **kwargs: Any
    ) -> AsyncIterator[Any]:
        return self._runner.astream(input, config, **kwargs)

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> _FailoverRunnable:
        bound = [model.bind_tools(tools, **kwargs) for model in self._models]
        return _FailoverRunnable(bound, self._labels)

    def with_structured_output(self, schema: Any, **kwargs: Any) -> _FailoverRunnable:
        # kwargs（含 method=... / strict=... 等）原样透传给每个模型
        structured = [model.with_structured_output(schema, **kwargs) for model in self._models]
        return _FailoverRunnable(structured, self._labels)
