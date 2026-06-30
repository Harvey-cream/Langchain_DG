"""
企业级 MCP 接入：用 LangChain 官方 MultiServerMCPClient 从远端/子进程加载工具，与自建 RAG 工具一并交给 ReAct Agent。

配置优先级（后者覆盖前者仅当未提供时回退）：
1. MCP_SERVERS_CONFIG：JSON 文件路径（绝对路径，或相对 backend_langchain 根目录）。
2. MCP_SERVERS_JSON：整段 JSON 字符串，结构与 MultiServerMCPClient 一致。
3. 若以上均未设置：自动读取 backend_langchain/MCP/mcp_servers.json（存在则加载）。

请将 MCP/mcp_servers.example.json 复制为 MCP/mcp_servers.json，写入真实 Token（该文件已 .gitignore）。
Authorization 必须是 "Bearer ghp_xxxx" 这种形式，不要把令牌包在 < > 里，否则远端会 400。
GitHub 远程 MCP文档：https://github.com/github/github-mcp-server/blob/main/docs/remote-server.md
Gitee：https://help.gitee.com/ai-productivity/mcp-server
transport 常用：streamable_http、stdio、sse。

依赖：requirements.txt 已含 langchain-mcp-adapters、mcp；需与 langchain-core 1.x 对齐。

文档：https://docs.langchain.com/oss/python/langchain/mcp
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_mcp_tools_cache: list[Any] | None = None
_mcp_load_attempted = False
_mcp_lock = threading.Lock()
_DEFAULT_MCP_CONFIG = "MCP/mcp_servers.json"


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read_connections() -> dict[str, dict[str, Any]] | None:
    path_raw = (os.getenv("MCP_SERVERS_CONFIG") or "").strip()
    json_raw = (os.getenv("MCP_SERVERS_JSON") or "").strip()
    data: Any = None
    if path_raw:
        p = Path(path_raw)
        if not p.is_file():
            p = _backend_root() / path_raw
        if not p.is_file():
            logger.warning("MCP_SERVERS_CONFIG 文件不存在: %s", path_raw)
            return None
        data = json.loads(p.read_text(encoding="utf-8"))
    elif json_raw:
        data = json.loads(json_raw)
    else:
        default_path = _backend_root() / _DEFAULT_MCP_CONFIG
        if default_path.is_file():
            data = json.loads(default_path.read_text(encoding="utf-8"))
            logger.info("MCP：已加载默认配置 %s", default_path)
        else:
            return None
    if not isinstance(data, dict) or not data:
        logger.warning("MCP 配置须为非空 JSON 对象（服务器名 -> 连接参数）")
        return None
    return data


async def _async_load_tools(connections: dict[str, dict[str, Any]]) -> list[Any]:
    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient(connections)
    return await client.get_tools()


def _store_mcp_tools(tools: list[Any], *, conn_count: int = 0) -> list[Any]:
    global _mcp_tools_cache, _mcp_load_attempted
    _mcp_tools_cache = tools
    _mcp_load_attempted = True
    if tools and conn_count:
        logger.info(
            "MCP MultiServer：已从 %d 个服务端加载 %d 个工具",
            conn_count,
            len(tools),
        )
    return list(tools)


def _load_mcp_tools_in_new_loop() -> list[Any]:
    """在无运行中 event loop 的线程里同步加载（内部使用 asyncio.run）。"""
    with _mcp_lock:
        if _mcp_load_attempted:
            return list(_mcp_tools_cache or [])
        conns = _read_connections()
        if not conns:
            return _store_mcp_tools([])
    try:
        tools = asyncio.run(_async_load_tools(conns))
        with _mcp_lock:
            if _mcp_load_attempted:
                return list(_mcp_tools_cache or [])
            return _store_mcp_tools(tools, conn_count=len(conns))
    except ImportError:
        logger.warning(
            "MCP：未安装 langchain-mcp-adapters / mcp，或 langchain-core 版本过低；"
            "请执行 pip install -r requirements.txt"
        )
        with _mcp_lock:
            if _mcp_load_attempted:
                return list(_mcp_tools_cache or [])
            return _store_mcp_tools([])
    except Exception:
        logger.exception("MCP：从服务端拉取工具失败")
        with _mcp_lock:
            if _mcp_load_attempted:
                return list(_mcp_tools_cache or [])
            return _store_mcp_tools([])


async def aload_mcp_tools_once() -> list[Any]:
    """异步加载 MCP 工具（FastAPI lifespan 等 async 上下文应优先调用）。"""
    with _mcp_lock:
        if _mcp_load_attempted:
            return list(_mcp_tools_cache or [])
        conns = _read_connections()
        if not conns:
            return _store_mcp_tools([])

    try:
        tools = await _async_load_tools(conns)
        with _mcp_lock:
            if _mcp_load_attempted:
                return list(_mcp_tools_cache or [])
            return _store_mcp_tools(tools, conn_count=len(conns))
    except ImportError:
        logger.warning(
            "MCP：未安装 langchain-mcp-adapters / mcp，或 langchain-core 版本过低；"
            "请执行 pip install -r requirements.txt"
        )
        with _mcp_lock:
            if _mcp_load_attempted:
                return list(_mcp_tools_cache or [])
            return _store_mcp_tools([])
    except Exception:
        logger.exception("MCP：从服务端拉取工具失败")
        with _mcp_lock:
            if _mcp_load_attempted:
                return list(_mcp_tools_cache or [])
            return _store_mcp_tools([])


def load_mcp_tools_once() -> list[Any]:
    """进程内只加载一次；未配置或依赖缺失时返回空列表。"""
    with _mcp_lock:
        if _mcp_load_attempted:
            return list(_mcp_tools_cache or [])

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return _load_mcp_tools_in_new_loop()

    # 已在 async 请求里且尚未预加载：放到独立线程跑 asyncio.run，避免嵌套 loop。
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_load_mcp_tools_in_new_loop).result()

