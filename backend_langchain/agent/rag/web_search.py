"""强制联网搜索：用户开启「联网搜索」时直接调百炼 WebSearch MCP，不经模型判断。"""
from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass

from backend_langchain.logger_func import log_exception_event, log_info_event
from config.config import dashscope_api_key

logger = logging.getLogger(__name__)

_MCP_URL = "https://dashscope.aliyuncs.com/api/v1/mcps/WebSearch/mcp"
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_URL_RE = re.compile(r"https?://[^\s\]\)\"'<>]+")


@dataclass(frozen=True)
class WebSource:
    title: str
    url: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def parse_web_sources(text: str, *, limit: int = 8) -> list[WebSource]:
    """从搜索结果文本里尽量抽出标题+链接。"""
    sources: list[WebSource] = []
    seen: set[str] = set()
    raw = text or ""

    for title, url in _MD_LINK_RE.findall(raw):
        u = url.rstrip(".,;）)")
        if u in seen:
            continue
        seen.add(u)
        sources.append(WebSource(title=(title.strip() or u), url=u))
        if len(sources) >= limit:
            return sources

    for url in _URL_RE.findall(raw):
        u = url.rstrip(".,;）)")
        if u in seen:
            continue
        seen.add(u)
        sources.append(WebSource(title=u, url=u))
        if len(sources) >= limit:
            break
    return sources


def format_web_context(text: str, sources: list[WebSource]) -> str:
    body = (text or "").strip()
    if not body and not sources:
        return ""
    lines = ["【联网参考（用户已开启联网搜索，系统已强制检索；勿编造未出现的链接）】"]
    if sources:
        lines.append("来源：")
        for i, s in enumerate(sources, 1):
            lines.append(f"{i}. {s.title} — {s.url}")
    if body:
        lines.append("")
        lines.append(body)
    return "\n".join(lines)


async def forced_web_search(query: str) -> tuple[str, list[WebSource]]:
    """调用百炼 WebSearch MCP；返回 (原始结果文本, 来源列表)。失败时返回空。"""
    q = (query or "").strip()
    if not q:
        return "", []

    api_key = (dashscope_api_key() or "").strip()
    if not api_key:
        log_info_event(logger, "forced_web_search_skip", reason="no_dashscope_api_key")
        return "", []

    try:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client
    except ImportError:
        log_exception_event(logger, "forced_web_search_import_failed")
        return "", []

    try:
        headers = {"Authorization": f"Bearer {api_key}"}
        async with streamablehttp_client(_MCP_URL, headers=headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listed = await session.list_tools()
                tools = list(listed.tools or [])
                if not tools:
                    log_info_event(logger, "forced_web_search_no_tools")
                    return "", []

                tool = next(
                    (t for t in tools if "search" in (t.name or "").lower()),
                    tools[0],
                )
                result = await session.call_tool(tool.name, {"query": q})
                parts: list[str] = []
                for block in result.content or []:
                    text = getattr(block, "text", None)
                    if text:
                        parts.append(str(text))
                raw = "\n".join(parts).strip()
                sources = parse_web_sources(raw)
                log_info_event(
                    logger,
                    "forced_web_search_ok",
                    tool=tool.name,
                    chars=len(raw),
                    sources=len(sources),
                )
                return raw, sources
    except Exception:  # noqa: BLE001
        log_exception_event(logger, "forced_web_search_failed", query=q[:80])
        return "", []
