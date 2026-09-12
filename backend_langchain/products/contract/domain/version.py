from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from .errors import InvalidContractVersion


@dataclass(slots=True)
class ContractVersion:
    id: UUID | None
    contract_id: UUID
    number: int
    source_key: str
    filename: str
    status: str = "created"
    created_at: datetime | None = None

    @classmethod
    def create(
        cls,
        *,
        contract_id: UUID,
        number: int,
        source_key: str,
        filename: str,
    ) -> "ContractVersion":
        if number < 1:
            raise InvalidContractVersion("version number must be positive")
        if not source_key.strip():
            raise InvalidContractVersion("version source key is required")
        if not filename.strip():
            raise InvalidContractVersion("version filename is required")
        return cls(
            id=uuid4(),
            contract_id=contract_id,
            number=number,
            source_key=source_key.strip(),
            filename=filename.strip(),
        )

    @staticmethod
    def next_number(existing_numbers: list[int]) -> int:
        return max(existing_numbers, default=0) + 1
