"""Deterministic Review gate, not a second agent or a legal correctness evaluator."""

import re
import unicodedata
from dataclasses import dataclass
from uuid import UUID

from products.contract.schemas.analysis import ReviewResult, validate_findings

QUALITY_GATE_VERSION = "review-quality-v1"


class ReviewQualityError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class VerifiedReview:
    result: ReviewResult
    report: dict


def _normalized(value: str) -> str:
    return " ".join(unicodedata.normalize("NFD", value).split())


def locate_excerpt(source: str, excerpt: str) -> dict:
    """Exact span, or canonical Unicode/whitespace equivalence with a source map.

    No fuzzy similarity, punctuation deletion, word joining, number conversion,
    negation removal or compatibility (NFKC) normalization is allowed.
    """
    if not excerpt.strip():
        raise ReviewQualityError("evidence_grounding", "原文证据不能为空白")
    start = source.find(excerpt)
    if start >= 0:
        return dict(start_char=start, end_char=start + len(excerpt), match="exact")
    text, spans, index = [], [], 0
    while index < len(source):
        end = index + 1
        while end < len(source) and unicodedata.category(source[end]).startswith("M"):
            end += 1
        for char in unicodedata.normalize("NFD", source[index:end]):
            if char.isspace():
                if text and text[-1] == " ":
                    spans[-1] = (spans[-1][0], end)
                else:
                    text.append(" ")
                    spans.append((index, end))
            else:
                text.append(char)
                spans.append((index, end))
        index = end
    normalized, wanted, offset = "".join(text), _normalized(excerpt), 0
    while wanted:
        found = normalized.find(wanted, offset)
        if found < 0:
            break
        right = found + len(wanted)
        # Never match only half of a decomposed Unicode grapheme.
        if (not found or spans[found - 1] != spans[found]) and (
            right == len(spans) or spans[right - 1] != spans[right]
        ):
            return dict(
                start_char=spans[found][0],
                end_char=spans[right - 1][1],
                match="unicode_whitespace",
            )
        offset = found + 1
    raise ReviewQualityError(
        "evidence_grounding", "证据不能定位到真实原文；不接受模糊匹配或改写"
    )


def _context_index(
    records,
    key,
    *,
    owner_id=None,
    policies=False,
    clauses=(),
    party_role="",
    contract_type=""
):
    result = {}
    code = "policy_grounding" if policies else "rag_citation"
    for record in records:
        try:
            identifier = str(UUID(str(record[key])))
            if identifier in result:
                raise ValueError("duplicate context id")
            if policies:
                if type(record["version"]) is not int or record["version"] < 1:
                    raise ValueError("invalid policy version")
                if record.get("severity") not in ("high", "medium", "low"):
                    raise ValueError("invalid policy severity")
            if owner_id is not None:
                if record["owner_id"] != owner_id:
                    raise ValueError("wrong owner")
                if policies:
                    if (
                        not record["enabled"]
                        or record["archived"]
                        or record["applicable_party_role"]
                        and record["applicable_party_role"] != party_role
                        or record["applicable_contract_types"]
                        and contract_type not in record["applicable_contract_types"]
                    ):
                        raise ValueError("policy outside frozen scope")
                else:
                    UUID(record["document_id"])
                    for field in ("document_version", "index_generation"):
                        if type(record[field]) is not int or record[field] < 1:
                            raise ValueError("invalid document version")
                    if (
                        not record["chunk_text"].strip()
                        or not record["clause_ids"]
                        or not set(record["clause_ids"]).issubset(clauses)
                    ):
                        raise ValueError("invalid reference scope")
        except (KeyError, ValueError, TypeError) as exc:
            raise ReviewQualityError(
                code, "审查上下文的来源、归属、版本或适用范围非法"
            ) from exc
        result[identifier] = record
    return result


def verify_review(
    raw_result,
    clauses,
    version_id,
    *,
    policies=(),
    references=(),
    owner_id=None,
    party_role="",
    contract_type="",
    deduplicate=True
) -> VerifiedReview:
    try:
        if isinstance(raw_result, ReviewResult):
            raw_result = raw_result.model_dump(mode="python")
        if isinstance(raw_result, dict) and "risks" not in raw_result:
            raise ValueError("risks must be explicitly supplied")
        parsed = ReviewResult.model_validate(raw_result)
    except ValueError as exc:
        raise ReviewQualityError(
            "schema", "风险输出字段、等级或协议不符合要求"
        ) from exc
    by_id = {clause.id: clause for clause in clauses}
    if len(by_id) != len(clauses) or any(
        clause.version_id != version_id for clause in clauses
    ):
        raise ReviewQualityError("clause_grounding", "审查条款重复或跨版本")
    policy_by_id = _context_index(
        policies,
        "id",
        owner_id=owner_id,
        policies=True,
        party_role=party_role,
        contract_type=contract_type,
    )
    reference_by_id = _context_index(
        references, "chunk_id", owner_id=owner_id, clauses={str(k) for k in by_id}
    )
    verified, checks, normalized, duplicates, warnings, keys = [], [], [], [], [], {}
    for input_index, risk in enumerate(parsed.risks):
        clause = by_id.get(risk.clause_id)
        if clause is None or any(key not in by_id for key in risk.related_clause_ids):
            raise ReviewQualityError("clause_grounding", "风险关联不存在或跨版本的条款")
        if (
            len(set(risk.related_clause_ids)) != len(risk.related_clause_ids)
            or risk.clause_id in risk.related_clause_ids
        ):
            raise ReviewQualityError("clause_grounding", "关联条款重复或自引用")
        locator = locate_excerpt(clause.original_text, risk.evidence)
        changes = {
            "evidence": clause.original_text[
                locator["start_char"] : locator["end_char"]
            ]
        }
        kind = re.sub(
            r"[\s-]+",
            "_",
            unicodedata.normalize("NFC", risk.risk_type).strip().casefold(),
        )
        notes = []
        if (
            len(kind) > 64
            or not kind
            or not all(char.isalnum() or char == "_" for char in kind)
            or not any(char.isalnum() for char in kind)
        ):
            kind = "other"
            notes.append("风险分类无法安全规范化，已归为 other，原分类保留在校验记录中")
        changes["risk_type"] = kind
        citations, source_checks = [], []
        for citation in risk.reference_citations:
            reference = reference_by_id.get(str(citation.chunk_id))
            if reference is None or str(risk.clause_id) not in reference.get(
                "clause_ids", []
            ):
                raise ReviewQualityError(
                    "rag_citation", "引用未提供或不属于本条款上下文的知识库片段"
                )
            try:
                position = locate_excerpt(
                    reference["chunk_text"], citation.source_excerpt
                )
            except ReviewQualityError as exc:
                raise ReviewQualityError(
                    "rag_citation", "参考引用片段不能定位到实际召回原文"
                ) from exc
            citations.append(
                citation.model_copy(
                    update={
                        "source_excerpt": reference["chunk_text"][
                            position["start_char"] : position["end_char"]
                        ]
                    }
                )
            )
            source_checks.append({"chunk_id": str(citation.chunk_id), **position})
        changes["reference_citations"] = citations
        risk = risk.model_copy(update=changes)
        # Source-preserving normalization can expand whitespace. model_copy does
        # not revalidate nested limits, so validate the actual saved shape again.
        try:
            risk = ReviewResult.model_validate(
                {"risks": [risk.model_dump(mode="python")]}
            ).risks[0]
        except ValueError as exc:
            raise ReviewQualityError(
                "schema", "定位后的真实证据或引用超过协议限制，请使用更短的真实片段"
            ) from exc
        try:
            validate_findings(
                ReviewResult(risks=[risk]),
                clauses,
                version_id,
                policies=policies,
                references=references,
            )
        except ValueError as exc:
            code = (
                "policy_grounding"
                if "规则" in str(exc)
                else "rag_citation" if "资料" in str(exc) else "consistency"
            )
            raise ReviewQualityError(code, str(exc)) from exc
        if re.search(
            r"已(?:正式)?(?:批准|修改合同|替换合同)|最终合同已|正式合同修改结果",
            risk.reason + "\n" + risk.recommendation,
        ):
            raise ReviewQualityError(
                "unapproved_revision",
                "Review 只能输出待确认建议，不能宣称已批准或执行正式修改",
            )
        if re.search(
            r"contract_?change", risk.reason + "\n" + risk.recommendation, re.IGNORECASE
        ):
            raise ReviewQualityError(
                "unapproved_revision",
                "本阶段不存在可引用的 ContractChange，Review 不能生成或引用正式修改对象",
            )
        assessment = "review_hint"
        if re.search(
            r"违法|依法无效|构成犯罪|法律禁止|违反.{0,16}(?:法律|条例)|法律规定",
            risk.reason + "\n" + risk.recommendation,
        ):
            assessment = "insufficient_legal_basis"
            notes.append(
                "包含未经核实的法律判断；来源校验不证明违法，仅作为待法务复核的提示"
            )
        if citations:
            notes.append("历史案例、模板和参考资料不是天然权威法律依据")
        if len(_normalized(risk.evidence)) < 4:
            notes.append("原文证据片段较短，请结合完整条款复核")
        original = parsed.risks[input_index].model_dump(mode="json")
        if risk.model_dump(mode="json") != original:
            normalized.append({"input_index": input_index, "original": original})
        key = (str(risk.clause_id), kind, _normalized(risk.evidence))
        candidates = keys.setdefault(key, [])
        duplicate = next(
            (i for i in candidates if _same_finding(verified[i], risk)), None
        )
        if deduplicate and duplicate is not None:
            duplicates.append(
                {
                    "input_index": input_index,
                    "kept_index": duplicate,
                    "rule": "same_clause_type_evidence_and_consistent_content",
                    "original": original,
                }
            )
            continue
        if deduplicate and candidates:
            notes.append(
                "同条款、同类型和同证据出现不同判断或建议，无法确定为重复，已保留变体"
            )
            for index in candidates:
                checks[index]["notes"] = list(
                    dict.fromkeys(checks[index]["notes"] + notes[-1:])
                )
            warnings.append("存在疑似重复的不同判断，已保留而未静默合并")
        check = dict(
            clause_id=str(risk.clause_id),
            risk_type=kind,
            evidence=risk.evidence,
            reason=risk.reason,
            recommendation=risk.recommendation,
            evidence_locator=locator,
            related_clause_ids=[str(k) for k in risk.related_clause_ids],
            policy_versions=[
                {"id": str(k), "version": policy_by_id[str(k)]["version"]}
                for k in risk.policy_ids
            ],
            citations=source_checks,
            assessment=assessment,
            notes=notes,
        )
        candidates.append(len(verified))
        verified.append(risk)
        checks.append(check)
    report = dict(
        version=QUALITY_GATE_VERSION,
        status="passed",
        version_id=str(version_id),
        input_count=len(parsed.risks),
        verified_count=len(verified),
        duplicate_count=len(duplicates),
        clause_ids=[str(k) for k in by_id],
        finding_checks=checks,
        duplicates=duplicates,
        normalizations=normalized,
        warnings=list(dict.fromkeys(warnings)),
        limitation="仅验证来源、协议和内部一致性，不证明风险判断或法律结论正确；建议未经人工批准",
    )
    return VerifiedReview(ReviewResult(risks=verified), report)


def _same_finding(first, second):
    return (
        first.risk_level == second.risk_level
        and _normalized(first.reason) == _normalized(second.reason)
        and _normalized(first.recommendation) == _normalized(second.recommendation)
        and set(first.related_clause_ids) == set(second.related_clause_ids)
        and set(first.policy_ids) == set(second.policy_ids)
        and {
            (c.chunk_id, _normalized(c.source_excerpt))
            for c in first.reference_citations
        }
        == {
            (c.chunk_id, _normalized(c.source_excerpt))
            for c in second.reference_citations
        }
    )
