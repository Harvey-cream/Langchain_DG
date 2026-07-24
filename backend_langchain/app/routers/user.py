from __future__ import annotations

import hashlib
import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import require_user
from app.models import User, ensure_display_tag
from app.response import fail, ok
from app.utils import format_datetime
from app.auth.jwt_token import create_token
from app.auth.sm2 import request_handler

router = APIRouter(prefix="/api/user", tags=["user"])

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class RegisterBody(BaseModel):
    name: str = ""
    email: str = ""
    password: str = ""


class LoginBody(BaseModel):
    email: str = ""
    password: str = ""


class UpdateUserBody(BaseModel):
    username: str = ""


@router.post("/register/")
async def register(body: RegisterBody, db: AsyncSession = Depends(get_db)):
    try:
        username = body.name.strip()
        email = body.email.strip()
        try:
            password = request_handler.decrypt(body.password)
        except Exception as e:
            return fail(f"密码解密失败：{str(e)}")
        if not username:
            return fail("用户名不能为空")
        if not email:
            return fail("邮箱不能为空")
        if not _EMAIL_RE.match(email):
            return fail("请输入有效的邮箱地址")
        if not password:
            return fail("密码不能为空")
        if len(password) < 6:
            return fail("密码长度不能少于6位")
        exists = await db.execute(select(User).where(User.email == email))
        if exists.scalar_one_or_none():
            return fail("该邮箱已被注册")
        hashed = hashlib.sha256(password.encode()).hexdigest()
        user = User(username=username, email=email, password=hashed)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        await ensure_display_tag(db, user)
        return ok(
            "注册成功",
            {
                "user_id": user.user_id,
                "username": user.username,
                "email": user.email,
                "display_tag": user.display_tag,
                "created_at": format_datetime(user.created_at),
            },
        )
    except Exception as e:
        return fail(f"注册失败：{str(e)}")


@router.post("/login/")
async def login(body: LoginBody, db: AsyncSession = Depends(get_db)):
    try:
        email = body.email.strip()
        try:
            password = request_handler.decrypt(body.password)
        except Exception as e:
            return fail(f"密码解密失败：{str(e)}")
        if not email:
            return fail("邮箱不能为空")
        if not _EMAIL_RE.match(email):
            return fail("请输入有效的邮箱地址")
        if not password:
            return fail("密码不能为空")
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user:
            return fail("邮箱或密码错误")
        hashed = hashlib.sha256(password.encode()).hexdigest()
        if user.password != hashed:
            return fail("邮箱或密码错误")
        await ensure_display_tag(db, user)
        token = create_token(user.user_id)
        return ok(
            "登录成功",
            {
                "token": token,
                "user": {
                    "user_id": user.user_id,
                    "username": user.username,
                    "email": user.email,
                    "display_tag": user.display_tag,
                },
            },
        )
    except Exception as e:
        return fail(f"登录失败：{str(e)}")


@router.get("/info/")
async def user_info(user: User = Depends(require_user), db: AsyncSession = Depends(get_db)):
    await ensure_display_tag(db, user)
    return ok(
        "获取成功",
        {
            "user_id": user.user_id,
            "username": user.username,
            "email": user.email,
            "display_tag": user.display_tag,
            "created_at": format_datetime(user.created_at),
        },
    )


@router.put("/info/update/")
async def update_user_info(
    body: UpdateUserBody,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        username = body.username.strip()
        if username:
            user.username = username
            await db.commit()
            await db.refresh(user)
        await ensure_display_tag(db, user)
        return ok(
            "更新成功",
            {
                "user_id": user.user_id,
                "username": user.username,
                "email": user.email,
                "display_tag": user.display_tag,
                "updated_at": format_datetime(user.updated_at),
            },
        )
    except Exception as e:
        return fail(f"更新失败：{str(e)}")
