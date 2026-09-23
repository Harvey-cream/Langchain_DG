from __future__ import annotations

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import User
from app.auth.jwt_token import verify_token


async def get_current_user(
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    user_id = verify_token(authorization)
    if not user_id:
        return None
    # Close the authentication read transaction before endpoint use cases open
    # their own explicit transaction on the request-scoped session.
    async with db.begin():
        result = await db.execute(select(User).where(User.user_id == user_id))
        return result.scalar_one_or_none()


async def require_user(user: User | None = Depends(get_current_user)) -> User:
    from fastapi import HTTPException

    if not user:
        raise HTTPException(status_code=401, detail="认证失败，请重新登录")
    return user
