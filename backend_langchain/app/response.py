from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse


def ok(msg: str = "操作成功", data: Any = None) -> JSONResponse:
    body: dict[str, Any] = {"code": 0, "msg": msg, "success": True}
    if data is not None:
        body["data"] = data
    return JSONResponse(body)


def fail(msg: str, *, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        {"code": 1, "msg": msg, "success": False},
        status_code=status_code,
    )
