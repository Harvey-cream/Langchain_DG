from __future__ import annotations

from products.contract.schemas.analysis import ContractAnalysis


def _compact(value: str) -> str:
    return "".join(value.split())


def validate_evidence(document_text: str, result: ContractAnalysis) -> bool:
    """Every quoted clause and risk must be a non-empty substring of the source."""
    source = _compact(document_text)
    evidence = [clause.original_text for clause in result.clauses]
    evidence.extend(risk.original_text for risk in result.risks)
    if not all(item.strip() and _compact(item) in source for item in evidence):
        return False
    clause_count = len(result.clauses)
    return all(
        risk.clause_sequence is None
        or 1 <= risk.clause_sequence <= clause_count
        for risk in result.risks
    )
