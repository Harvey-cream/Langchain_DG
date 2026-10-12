"""Only the two Review model calls: optional decisions and strict risk generation."""

import asyncio
from time import perf_counter

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from products.contract.quality import ReviewQualityError, verify_review
from products.contract.schemas.analysis import ReviewResult
from . import prompts
from .state import ReviewState
from .windows import encode, MAX_REVIEW_INPUT_CHARS


class ReviewLLM:
    def __init__(self, model, trace: dict, timeout: float):
        self.model, self.trace, self.timeout = model, trace, timeout
        self.structured = model.with_structured_output(
            ReviewResult, method="function_calling", include_raw=True
        )
        self.decision = None

    def bind_tools(self, tools):
        try:
            self.decision = self.model.bind_tools(tools, tool_choice="auto")
        except (AttributeError, NotImplementedError, TypeError) as exc:
            raise ValueError(
                "Review ReAct 模型不支持 Tool Calling；请配置支持工具的模型，或明确关闭 ReAct"
            ) from exc

    async def invoke(self, runnable, messages, *, phase, window, attempt=1):
        call = dict(phase=phase, window=window, attempt=attempt, status="failed")
        self.trace["model_calls"].append(call)
        started = perf_counter()
        try:
            response = await asyncio.wait_for(runnable.ainvoke(messages), self.timeout)
            raw = response.get("raw") if isinstance(response, dict) else response
            metadata = getattr(raw, "response_metadata", {}) or {}
            label = (
                metadata.get("model_name")
                or metadata.get("model")
                or getattr(runnable, "last_successful_model", None)
            )
            label = label or getattr(self.model, "model_name", None)
            call["model"] = label if isinstance(label, str) else None
            usage = getattr(raw, "usage_metadata", None) or metadata.get("token_usage")
            if isinstance(usage, dict):
                call["usage"] = {k: v for k, v in usage.items() if type(v) is int}
            call["status"] = "returned"
            return response, call
        except TimeoutError as exc:
            raise ValueError("Review 模型调用超时") from exc
        finally:
            call["elapsed_seconds"] = round(perf_counter() - started, 3)

    async def decide(self, state: ReviewState) -> AIMessage:
        if self.decision is None:
            raise ValueError("Review ReAct 未绑定工具，不能假装执行自主决策")
        history = state["messages"]
        payload = encode(state["current_window"])
        history_size = sum(len(encode(m.model_dump(mode="json"))) for m in history)
        if len(payload) + history_size > MAX_REVIEW_INPUT_CHARS:
            raise ValueError("Review 决策上下文超过字符预算")
        response, call = await self.invoke(
            self.decision,
            [
                SystemMessage(content=prompts.DECISION_INSTRUCTIONS),
                HumanMessage(content=payload),
                *history,
            ],
            phase="decide",
            window=state["window_index"],
        )
        if not isinstance(response, AIMessage) or response.invalid_tool_calls:
            call["status"] = "rejected"
            raise ValueError("Review 决策模型未返回有效 AIMessage / Tool Calls")
        call["status"] = "passed"
        # We only need the calls or a short completion signal, not free-form reasoning.
        return response.model_copy(
            update={
                "content": "需要补充资料" if response.tool_calls else "资料收集完成"
            }
        )

    async def generate(self, state: ReviewState) -> ReviewResult:
        payload, error = state["current_window"], None
        for attempt in range(1, 3):
            messages = [
                SystemMessage(content=prompts.REVIEW_INSTRUCTIONS),
                HumanMessage(content=encode(payload)),
            ]
            if error is not None:
                messages.append(
                    HumanMessage(
                        content=f"上次质量校验失败（{error.code}）：{error}。请使用当前提供的真实原文与 ID 重新输出，不编造来源或正式修改。"
                    )
                )
            # Service/transport failures are not malformed model output and must
            # not consume the structured-output repair attempt.
            response, call = await self.invoke(
                self.structured,
                messages,
                phase="generate",
                window=state["window_index"],
                attempt=attempt,
            )
            try:
                if isinstance(response, dict) and "parsed" in response:
                    if (
                        response.get("parsing_error") is not None
                        or response["parsed"] is None
                    ):
                        raise ReviewQualityError("schema", "Structured Output 无效")
                    response = response["parsed"]
                if (
                    isinstance(response, ReviewResult)
                    and "risks" not in response.model_fields_set
                ):
                    raise ReviewQualityError(
                        "schema", "必须明确返回 risks；无风险时返回空列表"
                    )
                verified = verify_review(
                    response,
                    state["clauses"],
                    state["version_id"],
                    policies=state["policies"],
                    references=state["current_references"],
                    owner_id=state["user_id"],
                    party_role=state["party_role"],
                    contract_type=state["contract_type"],
                    deduplicate=False,
                )
                allowed = {
                    c["clause_id"]
                    for c in payload["targets"] + payload["context_clauses"]
                }
                for risk in verified.result.risks:
                    excerpts = [
                        c["original_text"]
                        for c in payload["targets"]
                        if c["clause_id"] == str(risk.clause_id)
                    ]
                    if not any(risk.evidence in text for text in excerpts):
                        raise ReviewQualityError(
                            "evidence_grounding", "证据不在当前窗口目标条款中"
                        )
                    if any(str(key) not in allowed for key in risk.related_clause_ids):
                        raise ReviewQualityError(
                            "clause_grounding", "引用了当前窗口未提供的关联条款"
                        )
                call["status"] = "passed"
                if verified.report["normalizations"]:
                    call["normalizations"] = verified.report["normalizations"]
                return verified.result
            except ValueError as exc:
                error = (
                    exc
                    if isinstance(exc, ReviewQualityError)
                    else ReviewQualityError("schema", str(exc))
                )
                if call is not None:
                    call.update(status="rejected", error_code=error.code)
        raise ReviewQualityError(
            error.code, f"Review V2 两次输出均未通过质量校验: {error}"
        ) from error
