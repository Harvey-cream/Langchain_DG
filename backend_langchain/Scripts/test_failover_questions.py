"""用 20 条真实用户问题压测多模型兜底链（gemini -> luna -> claude）。

在 backend_langchain 目录运行：
    python -m scripts.test_failover_questions                 # 顺序跑全部 20 条
    python -m scripts.test_failover_questions --dry-run       # 只打印问题，不发请求
    python -m scripts.test_failover_questions --limit 5       # 只跑前 5 条
    python -m scripts.test_failover_questions --streaming     # 走流式路径（agent/sse 同款）

说明：直接用 config.config.get_qwen_chat_model，不依赖 HTTP/DB/鉴权。
每条问题都会统计发生了几次兜底、最终由哪个模型作答，用于验证 luna 偶发
400 是否被自动吸收。
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
import time
from typing import Any

# Windows 控制台默认 GBK，中文/emoji 会抛 UnicodeEncodeError 并污染结果统计
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:
        pass

# 20 条覆盖不同产品线 / 长度 / 语言的真实用户问题
USER_QUESTIONS: list[str] = [
    "你好，自我介绍一下你能做什么。",
    "用一句话解释什么是 RAG（检索增强生成）。",
    "Python 的 asyncio 和多线程有什么区别？各适合什么场景？",
    "写一个快速排序的 Python 实现，并加上注释。",
    "什么是向量数据库？pgvector 在 RAG 里起什么作用？",
    "请按面试回答结构解释 MySQL InnoDB 的 MVCC 原理。",
    "面试题：Java HashMap 的扩容机制是怎样的？",
    "面试被问到“你项目里最难的技术点”，应该如何组织回答？",
    "面试中如何回答“你的职业规划是什么”？",
    "解释 Redis 缓存穿透、击穿、雪崩的区别与应对方案。",
    "一份采购合同通常需要包含哪些核心条款？",
    "合同里常见的风险条款有哪些？请分类说明。",
    "如何判断一份合同是否属于“格式条款”？",
    "帮我写一段合同“违约责任”条款的示例文本。",
    "What is a vector embedding? Answer in English, concise.",
    "先给一句话结论，再分三点展开：如何做好代码评审（Code Review）。",
    "请用表格对比 PostgreSQL 与 MySQL 在事务、索引、扩展能力上的差异。",
    "我有一份 20 页的软件采购合同，想快速提取关键条款，你会怎么处理？",
    "如果模型返回的内容不完整或中途报错，系统应该怎么保证用户体验？",
    "用 JSON 输出 {\"name\": \"张三\", \"age\": 30}，并解释每个字段的含义。",
]

_MODEL_RE = re.compile(r"model=(\S+) failed")


class _FallbackCollector(logging.Handler):
    """收集 config.failover 的 WARNING，用于统计兜底次数与失败模型。"""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())

    def failed_models(self) -> list[str]:
        return [m.group(1) for msg in self.messages if (m := _MODEL_RE.search(msg))]


def _install_collector() -> _FallbackCollector:
    collector = _FallbackCollector()
    logger = logging.getLogger("config.failover")
    logger.addHandler(collector)
    logger.setLevel(logging.WARNING)
    return collector


def _preview(text: str, limit: int = 60) -> str:
    flat = " ".join(text.split())
    return flat[:limit] + ("…" if len(flat) > limit else "")


def _invoke_once(llm: Any, question: str, *, streaming: bool) -> str:
    from langchain_core.messages import HumanMessage

    messages = [HumanMessage(content=question)]
    if streaming:
        async def _drain() -> str:
            parts: list[str] = []
            async for chunk in llm.astream(messages):
                content = getattr(chunk, "content", chunk)
                if isinstance(content, str):
                    parts.append(content)
            return "".join(parts)

        return asyncio.run(_drain())

    response = llm.invoke(messages)
    content = getattr(response, "content", response)
    return content if isinstance(content, str) else str(content)


def run(args: argparse.Namespace) -> int:
    questions = USER_QUESTIONS[: args.limit] if args.limit else USER_QUESTIONS

    if args.dry_run:
        print(f"共 {len(questions)} 条用户问题：")
        for i, q in enumerate(questions, 1):
            print(f"{i:>2}. {q}")
        return 0

    from config.config import get_qwen_chat_model

    collector = _install_collector()
    try:
        llm = get_qwen_chat_model(temperature=args.temperature, streaming=args.streaming)
    except Exception as exc:  # noqa: BLE001
        print(f"构建 LLM 失败：{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    labels = list(getattr(llm, "labels", [getattr(llm, "model_name", "single")]))

    print(f"兜底链：{' -> '.join(labels)}    （流式={args.streaming}）\n")

    ok = fell_back = failed = 0
    for i, question in enumerate(questions, 1):
        collector.messages.clear()
        started = time.perf_counter()
        try:
            answer = _invoke_once(llm, question, streaming=args.streaming)
            elapsed = time.perf_counter() - started
            failed_models = collector.failed_models()
            if failed_models:
                fell_back += 1
                answered_by = labels[min(len(failed_models), len(labels) - 1)]
                status = f"OK(兜底→{answered_by})"
            else:
                ok += 1
                status = "OK"
            print(f"{i:>2}. [{status}] {elapsed:5.1f}s  {_preview(question)}")
            print(f"      答：{_preview(answer, 80)}")
            if failed_models:
                print(f"      失败模型：{', '.join(failed_models)}")
        except Exception as exc:  # noqa: BLE001
            elapsed = time.perf_counter() - started
            failed += 1
            print(f"{i:>2}. [FAIL] {elapsed:5.1f}s  {_preview(question)}")
            print(f"      {type(exc).__name__}: {_preview(str(exc), 120)}")

    total = len(questions)
    print(
        f"\n汇总：{total} 条 | 首模型直出 {ok} | 兜底成功 {fell_back} | 失败 {failed}"
    )
    return 1 if failed else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="用 20 条用户问题压测多模型兜底链")
    parser.add_argument("--limit", type=int, default=0, help="只跑前 N 条（0=全部）")
    parser.add_argument("--dry-run", action="store_true", help="只打印问题，不发请求")
    parser.add_argument("--streaming", action="store_true", help="走流式路径")
    parser.add_argument("--temperature", type=float, default=0.3)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
