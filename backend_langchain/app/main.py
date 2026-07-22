"""FastAPI 应用入口。"""
from __future__ import annotations

import asyncio
import logging
import logging.config
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.db import init_db_tables
from app.routers import api, documents, interview, user
from app.settings import MEDIA_ROOT
from common.agent import close_checkpointer, init_checkpointer, warmup_agent_executors
from logging_config import LOGGING

logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db_tables()
    logger.info("database tables ready")
    await init_checkpointer()

    async def _startup_bg() -> None:
        # MCP / warmup 放到后台，避免阻塞会话列表等轻量 API（热重载时尤其明显）
        try:
            from MCP.mcp_multiserver import aload_mcp_tools_once

            await aload_mcp_tools_once()
        except Exception:
            logger.exception("MCP startup preload failed (will retry on first tool build)")
        if os.environ.get("SKIP_RAG_STARTUP_WARMUP", "").lower() not in ("1", "true", "yes"):
            try:
                from Langchain_Agent.tools import warmup_all_tool_singletons
                from common.skill_router import warmup_skill_phrase_cache

                await asyncio.to_thread(warmup_all_tool_singletons)
                await asyncio.to_thread(warmup_skill_phrase_cache)
                await asyncio.to_thread(warmup_agent_executors)
                logger.info("startup warmup finished")
            except Exception:
                logger.exception("startup warmup failed (first request will retry)")
        else:
            logger.info("SKIP_RAG_STARTUP_WARMUP set, skip warmup")

    bg = asyncio.create_task(_startup_bg())
    yield
    bg.cancel()
    try:
        await bg
    except asyncio.CancelledError:
        pass
    await close_checkpointer()


app = FastAPI(title="Lanchain DG", lifespan=lifespan)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        return JSONResponse(
            {"code": 2, "msg": exc.detail, "success": False},
            status_code=401,
        )
    return JSONResponse(
        {"code": 1, "msg": exc.detail, "success": False},
        status_code=exc.status_code,
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(MEDIA_ROOT)), name="media")

app.include_router(user.router)
app.include_router(api.router)
app.include_router(documents.router)
app.include_router(interview.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
