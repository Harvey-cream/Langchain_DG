from uuid import UUID, uuid4

from products.contract.domain.contract import Contract
from products.contract.domain.customer import Customer
from products.contract.domain.errors import InvalidContractVersion
from products.contract.domain.version import ContractVersion


def test_contract_identity_is_stable_and_unique():
    c = Contract.create(user_id=1, customer_id=1, title="Test Contract")
    assert c.title == "Test Contract"
    assert isinstance(c.id, UUID)
    # 稳定身份：同一实体 id 不变；不同合同 id 不同
    assert c.id == c.id
    other = Contract.create(user_id=1, customer_id=1, title="Another")
    assert other.id != c.id
    # 归属：合同持有创建者 user_id
    assert c.user_id == 1


def test_contract_requires_title():
    for bad in ("", "   "):
        try:
            Contract.create(user_id=1, customer_id=1, title=bad)
        except ValueError:
            continue
        raise AssertionError("empty title must be rejected")


def test_customer_validates_name_and_email():
    ok = Customer.create(user_id=1, name=" Acme ", email=" a@b.com ")
    assert ok.name == "Acme" and ok.email == "a@b.com"
    for name, email in (("", "a@b.com"), ("Acme", "bad"), ("Acme", "")):
        try:
            Customer.create(user_id=1, name=name, email=email)
        except ValueError:
            continue
        raise AssertionError(f"invalid customer accepted: {name!r},{email!r}")


def test_version_numbers_are_monotonic():
    c = Contract.create(user_id=1, customer_id=1, title="T")
    v1 = ContractVersion.create(contract_id=c.id, number=1, source_key="k1", filename="f1.pdf")
    v2 = ContractVersion.create(contract_id=c.id, number=2, source_key="k2", filename="f2.pdf")

    assert ContractVersion.next_number([]) == 1
    assert ContractVersion.next_number([v1.number]) == 2
    assert ContractVersion.next_number([v2.number, v1.number]) == 3
    # 追加只增：新版本号严格大于所有已有版本号
    n = ContractVersion.next_number([v1.number, v2.number])
    assert n > v2.number and n > v1.number


def test_version_rejects_invalid_input():
    c = Contract.create(user_id=1, customer_id=1, title="T")
    for kwargs in (
        {"number": 0, "source_key": "k", "filename": "f"},
        {"number": -1, "source_key": "k", "filename": "f"},
        {"number": 1, "source_key": "  ", "filename": "f"},
        {"number": 1, "source_key": "k", "filename": "  "},
    ):
        try:
            ContractVersion.create(contract_id=c.id, **kwargs)
        except InvalidContractVersion:
            continue
        raise AssertionError(f"invalid version accepted: {kwargs}")
    # 非法版本号是领域错误（ValueError 子类）
    assert issubclass(InvalidContractVersion, ValueError)
    _ = uuid4()


if __name__ == "__main__":
    test_contract_identity_is_stable_and_unique()
    test_contract_requires_title()
    test_customer_validates_name_and_email()
    test_version_numbers_are_monotonic()
    test_version_rejects_invalid_input()
    print("Contract domain rules passed")
