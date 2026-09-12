"""Contract workflow boundary; concrete review workflow is planned for a later phase."""
from typing import Protocol


class ContractWorkflow(Protocol):
    async def run(self, **kwargs): ...
