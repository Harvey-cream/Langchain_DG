"""The single Review Agent entry point: typed data in, graph result out."""

from dataclasses import asdict
import asyncio
from time import perf_counter

from common.config.config import (
    get_qwen_chat_model,
    dashscope_model_name,
    dashscope_rerank_model,
)
from products.contract.domain.review import REVIEW_PROMPT_VERSION
from products.contract.retrieval import settings
from .graph import build_review_graph
from .llm import ReviewLLM
from .state import ReviewGraphResult, ReviewLimits, ReviewRuntime
from .tools import REVIEW_TOOLS


class ReviewAgent:
    def __init__(self, model=None, *, retrieval_factory=None, limits=None):
        self.model = model
        self.retrieval_factory = retrieval_factory
        self.limits = limits if limits is not None else ReviewLimits.from_env()
        self.graph = build_review_graph()

    async def review(
        self,
        clauses,
        *,
        metadata,
        our_party="",
        policies=(),
        user_id=None,
        version_id=None,
        party_role="",
        contract_type="",
        timeout_seconds=240,
    ) -> ReviewGraphResult:
        if not clauses:
            raise ValueError("Review V2 缺少 Canonical Clause")
        trace = dict(
            prompt_version=REVIEW_PROMPT_VERSION,
            graph_version="review-graph-v1",
            limits=asdict(self.limits),
            windows=[],
            model_calls=[],
            tool_calls=[],
        )
        trace["retrieval"] = dict(
            enabled=self.retrieval_factory is not None,
            dense="pgvector",
            lexical="BM25",
            fusion="RRF",
            embedding_model=dashscope_model_name(),
            rerank_model=dashscope_rerank_model(),
            **settings(),
        )
        model = (
            self.model
            if self.model is not None
            else get_qwen_chat_model(temperature=0.1)
        )
        context = ReviewRuntime(
            ReviewLLM(model, trace, self.limits.model_timeout),
            self.limits,
            self.retrieval_factory,
            trace,
        )
        started = perf_counter()
        try:
            if self.limits.react_enabled:
                if type(user_id) is not int or user_id <= 0:
                    raise ValueError("Review ReAct 需要服务端提供明确的用户权限范围")
                context.llm.bind_tools(REVIEW_TOOLS)
            output = await asyncio.wait_for(
                self.graph.ainvoke(
                    dict(
                        version_id=version_id or clauses[0].version_id,
                        user_id=user_id,
                        clauses=tuple(clauses),
                        metadata=metadata,
                        our_party=our_party,
                        party_role=party_role,
                        contract_type=contract_type,
                        policies=list(policies),
                    ),
                    context=context,
                    config={"recursion_limit": self.limits.recursion_limit},
                ),
                timeout=timeout_seconds,
            )
            return ReviewGraphResult(
                output["result"],
                output["used_references"],
                output["retrieval_events"],
                trace,
                output["quality_report"],
                output["findings"],
            )
        except BaseException as exc:
            # Per-invocation trace survives failure/timeout without shared reviewer state.
            exc.review_trace = trace
            raise
        finally:
            trace["elapsed_seconds"] = round(perf_counter() - started, 3)


__all__ = ["ReviewAgent", "ReviewGraphResult", "ReviewLimits"]
