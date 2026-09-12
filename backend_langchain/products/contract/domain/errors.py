class ContractDomainError(ValueError):
    """Base error for invalid Contract business state."""


class InvalidContractVersion(ContractDomainError):
    pass
