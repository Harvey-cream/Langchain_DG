"""Phase E：Contract API 冒烟测试（进程内 ASGI + 真实 PostgreSQL）。

覆盖 Customer / Contract / ContractVersion 主路径、用户隔离与校验错误。
不经过 SM2 登录：直接用 app.auth.jwt_token.create_token 签 token。

用法（backend_langchain，PostgreSQL 已在 docker 运行）：
    POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433 SKIP_RAG_STARTUP_WARMUP=1 \
        .venv-py312/Scripts/python.exe scripts/test_contract_api_smoke.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("APP_ENV", "debug")
os.environ.setdefault("SKIP_RAG_STARTUP_WARMUP", "1")

import httpx  # noqa: E402
from sqlalchemy import delete, select  # noqa: E402

from app.auth.jwt_token import create_token  # noqa: E402
from app.db import SessionLocal, init_db_tables  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from infrastructure.db.models import (  # noqa: E402
    ContractModel,
    ContractVersionModel,
    CustomerModel,
)

_failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  PASS {name}")
    else:
        print(f"  FAIL {name} {detail}")
        _failures.append(name)


async def _ensure_two_users(session) -> tuple[int, int]:
    rows = (await session.execute(select(User.user_id).order_by(User.user_id).limit(2))).scalars().all()
    ids = list(rows)
    created: list[User] = []
    while len(ids) < 2:
        i = len(ids)
        u = User(username=f"smoke_user_{i}", email=f"smoke_contract_{os.getpid()}_{i}@example.test",
                 password="x")
        session.add(u)
        await session.flush()
        created.append(u)
        ids.append(u.user_id)
    await session.commit()
    return ids[0], ids[1], created


async def _cleanup(session, *, customer_ids, contract_ids, temp_users) -> None:
    if contract_ids:
        await session.execute(delete(ContractVersionModel).where(ContractVersionModel.contract_id.in_(contract_ids)))
        await session.execute(delete(ContractModel).where(ContractModel.id.in_(contract_ids)))
    if customer_ids:
        await session.execute(delete(CustomerModel).where(CustomerModel.id.in_(customer_ids)))
    for u in temp_users:
        await session.delete(u)
    await session.commit()


async def main() -> int:
    await init_db_tables()

    async with SessionLocal() as session:
        user_a, user_b, temp_users = await _ensure_two_users(session)

    token_a = create_token(user_a)
    token_b = create_token(user_b)
    hdr_a = {"Authorization": f"Bearer {token_a}"}
    hdr_b = {"Authorization": f"Bearer {token_b}"}

    created_customers: list[int] = []
    created_contracts: list[str] = []

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://smoke") as c:
        # 0) health
        r = await c.get("/health")
        check("health 200", r.status_code == 200, f"got {r.status_code}")

        # 1) 未认证
        r = await c.get("/api/customers")
        check("customers unauthenticated -> 401", r.status_code == 401, f"got {r.status_code}")

        # 2) 创建客户
        r = await c.post("/api/customers", json={"name": "Smoke Co", "email": "smoke@example.test"}, headers=hdr_a)
        body = r.json()
        check("create customer 200+success", r.status_code == 200 and body.get("success"), f"{r.status_code} {body}")
        cust = body.get("data") or {}
        customer_id = cust.get("id")
        created_customers.append(customer_id)
        check("customer has id", isinstance(customer_id, int), repr(customer_id))

        # 3) 客户列表包含刚建的
        r = await c.get("/api/customers", headers=hdr_a)
        ids = [x["id"] for x in (r.json().get("data") or {}).get("customers", [])]
        check("list customers contains new", customer_id in ids, repr(ids))

        # 4) 创建合同
        r = await c.post("/api/contracts", json={"customer_id": customer_id, "title": "Smoke Contract"}, headers=hdr_a)
        body = r.json()
        check("create contract 200+success", r.status_code == 200 and body.get("success"), f"{r.status_code} {body}")
        contract = body.get("data") or {}
        contract_id = contract.get("id")
        created_contracts.append(contract_id)
        check("contract has uuid id", isinstance(contract_id, str) and len(contract_id) == 36, repr(contract_id))

        # 5) 创建合同不存在客户 -> 404
        r = await c.post("/api/contracts", json={"customer_id": 2_000_000_000, "title": "Ghost"}, headers=hdr_a)
        check("contract w/ missing customer -> 404", r.status_code == 404, f"got {r.status_code}")

        # 6) 空白标题 -> 400（Pydantic min_length=1 放行，Domain strip 后拒绝）
        r = await c.post("/api/contracts", json={"customer_id": customer_id, "title": "   "}, headers=hdr_a)
        check("contract blank title -> 400", r.status_code == 400, f"got {r.status_code}")

        # 7) 版本号单调递增：1、2
        r = await c.post(f"/api/contracts/{contract_id}/versions",
                         json={"source_key": "oss://k/v1.pdf", "filename": "v1.pdf"}, headers=hdr_a)
        n1 = (r.json().get("data") or {}).get("number")
        check("first version number == 1", r.status_code == 200 and n1 == 1, f"{r.status_code} n={n1}")

        r = await c.post(f"/api/contracts/{contract_id}/versions",
                         json={"source_key": "oss://k/v2.pdf", "filename": "v2.pdf"}, headers=hdr_a)
        n2 = (r.json().get("data") or {}).get("number")
        check("second version number == 2 (monotonic)", r.status_code == 200 and n2 == 2, f"{r.status_code} n={n2}")

        # 8) 版本列表有序 [1,2]
        r = await c.get(f"/api/contracts/{contract_id}/versions", headers=hdr_a)
        nums = [v["number"] for v in (r.json().get("data") or {}).get("versions", [])]
        check("versions listed as [1,2]", nums == [1, 2], repr(nums))

        # 9) 取单个合同
        r = await c.get(f"/api/contracts/{contract_id}", headers=hdr_a)
        check("get contract 200", r.status_code == 200 and r.json().get("success"), f"got {r.status_code}")

        # 10) 用户隔离：B 看不到 A 的客户/合同
        r = await c.get(f"/api/customers/{customer_id}", headers=hdr_b)
        check("B get A customer -> 404", r.status_code == 404, f"got {r.status_code}")

        r = await c.get(f"/api/contracts/{contract_id}", headers=hdr_b)
        check("B get A contract -> 404", r.status_code == 404, f"got {r.status_code}")

        r = await c.get(f"/api/contracts/{contract_id}/versions", headers=hdr_b)
        check("B list A versions -> 404", r.status_code == 404, f"got {r.status_code}")

        r = await c.get("/api/customers", headers=hdr_b)
        ids_b = [x["id"] for x in (r.json().get("data") or {}).get("customers", [])]
        check("B customer list excludes A's", customer_id not in ids_b, repr(ids_b))

        # 11) B 建自己的客户成功（隔离非权限整体失效）
        r = await c.post("/api/customers", json={"name": "B Co", "email": "b@example.test"}, headers=hdr_b)
        b_cust = (r.json().get("data") or {}).get("id")
        created_customers.append(b_cust)
        check("B create own customer 200", r.status_code == 200 and isinstance(b_cust, int), f"{r.status_code}")

    async with SessionLocal() as session:
        await _cleanup(session, customer_ids=created_customers,
                       contract_ids=created_contracts, temp_users=temp_users)

    print()
    if _failures:
        print(f"{len(_failures)} 项失败: {', '.join(_failures)}")
        return 1
    print("Contract API 冒烟测试全部通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
