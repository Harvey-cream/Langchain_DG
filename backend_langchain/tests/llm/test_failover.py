"""FailoverLLM 顺序兜底单测（无网络，全部用桩对象替代真实 LLM）。

运行（在 backend_langchain 目录）：
    python -m tests.llm.test_failover
也可用 pytest（若已安装）。
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config.failover import FailoverLLM  # noqa: E402


class _ErrA(Exception):
    pass


class _ErrB(Exception):
    pass


class _StubModel:
    """模拟 ChatOpenAI 的最小鸭子类型：invoke/ainvoke/astream + bind_tools/with_structured_output。"""

    def __init__(
        self,
        name: str,
        *,
        error: Exception | None = None,
        error_after_chunks: bool = False,
    ):
        self.name = name
        self.error = error
        self.error_after_chunks = error_after_chunks
        self.invoke_calls = 0
        self.astream_calls = 0
        self.bind_invoked = 0
        self.structured_invoked = 0
        self.bind_kwargs: dict | None = None
        self.structured_kwargs: dict | None = None

    def _maybe_raise(self) -> None:
        if self.error is not None:
            raise self.error

    def invoke(self, input, config=None, **kwargs):
        self.invoke_calls += 1
        self._maybe_raise()
        return f"{self.name}:ok"

    async def ainvoke(self, input, config=None, **kwargs):
        self.invoke_calls += 1
        self._maybe_raise()
        return f"{self.name}:ok"

    async def astream(self, input, config=None, **kwargs):
        self.astream_calls += 1
        if self.error is not None and not self.error_after_chunks:
            raise self.error
        for i in range(2):
            yield f"{self.name}:c{i}"
        if self.error is not None and self.error_after_chunks:
            raise self.error

    def bind_tools(self, tools, **kwargs):
        self.bind_kwargs = dict(kwargs)
        return _BoundRunnable(self)

    def with_structured_output(self, schema, **kwargs):
        self.structured_kwargs = dict(kwargs)
        return _StructuredRunnable(self)


class _BoundRunnable:
    def __init__(self, model: _StubModel):
        self.model = model

    def invoke(self, input, config=None, **kwargs):
        self.model.bind_invoked += 1
        if self.model.error is not None:
            raise self.model.error
        return f"{self.model.name}:bound"

    async def ainvoke(self, input, config=None, **kwargs):
        return self.invoke(input, config, **kwargs)


class _StructuredRunnable:
    def __init__(self, model: _StubModel):
        self.model = model

    def invoke(self, input, config=None, **kwargs):
        self.model.structured_invoked += 1
        if self.model.error is not None:
            raise self.model.error
        return f"{self.model.name}:structured"

    async def ainvoke(self, input, config=None, **kwargs):
        return self.invoke(input, config, **kwargs)


# --- 兜底行为 ---------------------------------------------------------------


def test_invoke_falls_over_to_next_model():
    a = _StubModel("primary", error=_ErrA("400 模型已停用"))
    b = _StubModel("backup")
    llm = FailoverLLM([a, b], labels=["primary", "backup"])
    assert llm.invoke("hi") == "backup:ok"
    # 主模型只被调用一次
    assert a.invoke_calls == 1 and b.invoke_calls == 1


def test_all_fail_raises_last_exception_type():
    a = _StubModel("primary", error=_ErrA("boom-a"))
    b = _StubModel("backup", error=_ErrB("boom-b"))
    llm = FailoverLLM([a, b])
    try:
        llm.invoke("hi")
    except _ErrB as exc:  # 必须是最后一个模型的异常类型
        assert "boom-b" in str(exc)
    else:
        raise AssertionError("expected the last model's _ErrB")
    assert a.invoke_calls == 1 and b.invoke_calls == 1


def test_ainvoke_falls_over_to_next_model():
    a = _StubModel("primary", error=_ErrA("nope"))
    b = _StubModel("backup")
    llm = FailoverLLM([a, b])
    assert asyncio.run(llm.ainvoke("hi")) == "backup:ok"
    assert a.invoke_calls == 1 and b.invoke_calls == 1


def test_bind_tools_falls_over_and_passes_kwargs():
    a = _StubModel("primary", error=_ErrA("400"))
    b = _StubModel("backup")
    llm = FailoverLLM([a, b], labels=["primary", "backup"])
    bound = llm.bind_tools([object()], tool_choice="auto", parallel_tool_calls=False)
    assert bound.invoke("hi") == "backup:bound"
    # kwargs 原样透传到每个模型
    assert a.bind_kwargs == {"tool_choice": "auto", "parallel_tool_calls": False}
    assert b.bind_kwargs == {"tool_choice": "auto", "parallel_tool_calls": False}
    assert a.bind_invoked == 1 and b.bind_invoked == 1


def test_with_structured_output_falls_over_and_passes_kwargs():
    a = _StubModel("primary", error=_ErrA("400"))
    b = _StubModel("backup")
    llm = FailoverLLM([a, b])
    structured = llm.with_structured_output(object, method="function_calling", strict=True)
    assert structured.invoke("hi") == "backup:structured"
    assert a.structured_kwargs == {"method": "function_calling", "strict": True}
    assert b.structured_kwargs == {"method": "function_calling", "strict": True}
    assert a.structured_invoked == 1 and b.structured_invoked == 1


def test_astream_falls_over_only_before_first_chunk():
    a = _StubModel("primary", error=_ErrA("400"))
    b = _StubModel("backup")
    llm = FailoverLLM([a, b])

    async def collect():
        return [chunk async for chunk in llm.astream("hi")]

    assert asyncio.run(collect()) == ["backup:c0", "backup:c1"]
    assert a.astream_calls == 1 and b.astream_calls == 1


def test_astream_does_not_fall_back_after_chunks_emitted():
    a = _StubModel("primary", error=_ErrA("mid-stream"), error_after_chunks=True)
    b = _StubModel("backup")
    llm = FailoverLLM([a, b])

    async def collect():
        return [chunk async for chunk in llm.astream("hi")]

    try:
        asyncio.run(collect())
    except _ErrA:
        pass
    else:
        raise AssertionError("expected _ErrA (no fallback after first chunk)")
    assert b.astream_calls == 0


# --- 链解析与工厂 -----------------------------------------------------------


def test_chain_dedup_and_order():
    from config.config import _resolve_model_chain

    assert _resolve_model_chain(
        {"model": "m1", "fallback_models": ["m2", "m3"]}
    ) == ["m1", "m2", "m3"]
    # 主模型重复出现在兜底里 → 只留一次；兜底内部重复也去重
    assert _resolve_model_chain(
        {"model": "m1", "fallback_models": ["m2", "m1", "m3", "m2"]}
    ) == ["m1", "m2", "m3"]
    # 空兜底 → 单模型
    assert _resolve_model_chain({"model": "m1", "fallback_models": []}) == ["m1"]
    # 空主模型 → 报错
    try:
        _resolve_model_chain({"model": "  ", "fallback_models": ["m2"]})
    except RuntimeError:
        pass
    else:
        raise AssertionError("empty primary model must raise")


def _patch_llm_config(**overrides):
    import config.config as cfg

    payload = {
        "base_url": "https://example.invalid/v1",
        "api_key": "test-key",
        "model": "solo-model",
        "fallback_models": [],
    }
    payload.update(overrides)
    original = cfg.llm_config
    cfg.llm_config = lambda: payload  # type: ignore[assignment]
    return cfg, original


def test_factory_degrades_to_single_model_without_fallbacks():
    cfg, original = _patch_llm_config()
    try:
        llm = cfg.get_qwen_chat_model(temperature=0.0)
    finally:
        cfg.llm_config = original
    # 无兜底 → 原生实例，行为与改造前一致
    assert not isinstance(llm, FailoverLLM)
    assert getattr(llm, "model_name", None) == "solo-model"


def test_factory_builds_ordered_failover_chain():
    cfg, original = _patch_llm_config(
        model="gpt-5.6-luna",
        fallback_models=["claude-sonnet-4-6", "gemini-3.7-flash"],
    )
    try:
        llm = cfg.get_qwen_chat_model(temperature=0.3, streaming=True)
    finally:
        cfg.llm_config = original
    assert isinstance(llm, FailoverLLM)
    assert llm.labels == ["gpt-5.6-luna", "claude-sonnet-4-6", "gemini-3.7-flash"]


if __name__ == "__main__":
    _tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for _fn in _tests:
        _fn()
    print(f"FailoverLLM checks passed ({len(_tests)} tests)")
