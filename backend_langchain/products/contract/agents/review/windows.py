"""Existing lossless Review V2 windowing and bounded source packing."""

import json
from collections.abc import Iterator, Sequence
from products.contract.domain.document import CanonicalContractClause
from .state import ReviewWindow

MAX_REVIEW_INPUT_CHARS = 24000
MAX_TARGET_CHARS = 14000
MAX_CLAUSE_SLICE = 8000
MAX_TARGETS = 8


def encode(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def review_windows(
    clauses: Sequence[CanonicalContractClause],
    metadata: dict,
    our_party: str,
    *,
    policies=(),
    reserve_chars=0,
    party_role="",
    contract_type="",
) -> Iterator[ReviewWindow]:
    """Lossless source slices; bound serialized input including contextual clauses."""
    if not clauses:
        raise ValueError("Review V2 缺少 Canonical Clause")
    context = {
        key: str(metadata.get(key, ""))[:800]
        for key in ("summary", "amount", "duration", "payment_terms")
    }
    context["parties"] = [str(p)[:255] for p in metadata.get("parties", [])[:8]]
    policy_input = [
        {
            "policy_id": p["id"],
            **{
                k: p[k]
                for k in ("version", "name", "requirement", "severity", "category")
            },
        }
        for p in policies
    ]
    base = dict(
        our_party=our_party,
        business_scene={"party_role": party_role, "contract_type": contract_type},
        metadata=context,
        policies=policy_input,
        context_clauses=[],
        references=[],
    )
    target_budget = min(
        MAX_TARGET_CHARS,
        MAX_REVIEW_INPUT_CHARS - len(encode(base)) - reserve_chars - 800,
    )
    if target_budget < 1024:
        raise ValueError("适用企业规则超过单轮上下文预算，请精简规则范围或内容")
    parts = []
    for clause in clauses:
        if not clause.original_text.strip():
            raise ValueError("Canonical Clause 原文为空")
        start = 0
        while start < len(clause.original_text):
            end = min(start + MAX_CLAUSE_SLICE, len(clause.original_text))
            part = dict(
                clause_id=str(clause.id),
                title=clause.title,
                clause_type=clause.clause_type,
                sequence=clause.sequence,
                original_text=clause.original_text[start:end],
                source_offset=start,
            )
            # Quotes/control characters expand in JSON; raw character count alone is insufficient.
            while len(encode([part])) > target_budget and end - start > 1:
                end = start + (end - start) // 2
                part["original_text"] = clause.original_text[start:end]
            parts.append(part)
            start = end
    groups, group = [], []
    for part in parts:
        if group and (
            len(group) == MAX_TARGETS or len(encode(group + [part])) > target_budget
        ):
            groups.append(group)
            group = []
        group.append(part)
    if group:
        groups.append(group)
    for targets in groups:
        payload = {**base, "targets": targets, "context_clauses": []}
        target_ids = {item["clause_id"] for item in targets}
        positions = [item["sequence"] for item in targets]
        related_types = {
            "payment": {"delivery", "acceptance", "termination", "breach"},
            "delivery": {"payment", "acceptance", "termination"},
            "acceptance": {"payment", "delivery", "termination"},
            "termination": {"payment", "delivery", "breach"},
            "breach": {"payment", "termination", "delivery"},
        }
        wanted_types = set().union(
            *(related_types.get(t["clause_type"], set()) for t in targets)
        )

        def related(clause):
            return (
                clause.clause_type in wanted_types
                or bool(wanted_types)
                and any(
                    word in clause.original_text.casefold()
                    for word in ("退款", "退还", "refund")
                )
            )

        candidates = sorted(
            (c for c in clauses if str(c.id) not in target_ids),
            key=lambda c: (
                not related(c),
                min(abs(c.sequence - p) for p in positions),
                c.sequence,
            ),
        )
        # Give distant business dependencies a slot before nearby duplicate types.
        first_by_type = {}
        for candidate in candidates:
            if related(candidate):
                first_by_type.setdefault(candidate.clause_type, candidate)
        priority_ids = {c.id for c in first_by_type.values()}
        candidates = list(first_by_type.values()) + [
            c for c in candidates if c.id not in priority_ids
        ]
        for clause in candidates:
            if len(payload["context_clauses"]) >= 4:
                break
            if (
                not related(clause)
                and min(abs(clause.sequence - p) for p in positions) > 1
                and clause.clause_type
                not in {
                    "payment",
                    "delivery",
                    "acceptance",
                    "breach",
                    "termination",
                }
            ):
                continue
            extra = dict(
                clause_id=str(clause.id),
                title=clause.title,
                clause_type=clause.clause_type,
                original_text=clause.original_text,
            )
            proposed = {
                **payload,
                "context_clauses": payload["context_clauses"] + [extra],
            }
            if len(encode(proposed)) <= MAX_REVIEW_INPUT_CHARS - reserve_chars:
                payload = proposed
        if len(encode(payload)) > MAX_REVIEW_INPUT_CHARS:
            raise ValueError("Review V2 输入窗口超过限制")
        yield payload
