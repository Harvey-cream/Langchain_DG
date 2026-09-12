"""端到端测试 FastAPI 与面试 Agent SSE 链路。

推荐用法（在 backend_langchain 目录执行）：

    python -m scripts.test_e2e_api --register

LLM、PostgreSQL 和 checkpoint 都必须由正在运行的后端提供。
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Iterator

DEFAULT_TIMEOUT = 60.0


@dataclass
class TestState:
    token: str = ""
    user_id: int | None = None
    interview_conversation_id: int | None = None
    failures: list[str] = field(default_factory=list)


def _httpx() -> Any:
    try:
        import httpx
    except ImportError as exc:
        raise RuntimeError(
            "缺少 httpx，请使用运行后端的 Python 执行：pip install -r requirements.txt"
        ) from exc
    return httpx


def _password_payload(password: str) -> str:
    """调用后端同一套 SM2 配置，兼容前端的 C1C2C3 模式。"""
    try:
        from app.auth.sm2 import request_handler
    except ImportError as exc:
        raise RuntimeError(
            "无法导入 app.auth.sm2，请在 backend_langchain 目录和后端虚拟环境中运行"
        ) from exc
    return request_handler.encrypt(password)


def _json(response: httpx.Response) -> dict[str, Any]:
    try:
        value = response.json()
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"HTTP {response.status_code} 返回非 JSON：{response.text[:300]}"
        ) from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"HTTP {response.status_code} 返回结构异常：{value!r}")
    return value


def _assert_success(response: httpx.Response, action: str) -> dict[str, Any]:
    body = _json(response)
    if response.status_code >= 400 or not body.get("success"):
        raise RuntimeError(
            f"{action} 失败：HTTP {response.status_code} "
            f"code={body.get('code')} msg={body.get('msg')}"
        )
    return body


def _data(body: dict[str, Any], action: str) -> dict[str, Any]:
    value = body.get("data")
    if not isinstance(value, dict):
        raise RuntimeError(f"{action} 缺少 data：{body!r}")
    return value


def _sse_events(response: httpx.Response) -> Iterator[dict[str, Any]]:
    """解析 data: JSON SSE；忽略空行和注释，保留服务端事件顺序。"""
    for line in response.iter_lines():
        if not line or not line.startswith("data:"):
            continue
        raw = line[5:].strip()
        if not raw:
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"SSE data 不是 JSON：{raw[:300]}") from exc
        if isinstance(value, dict):
            yield value


def _print_event(event: dict[str, Any]) -> None:
    event_type = str(event.get("type") or "unknown")
    if event_type == "delta":
        text = str(event.get("text") or "").replace("\n", " ")
        print(f"    delta: {text[:100]}")
    elif event_type == "status":
        print(f"    status: {event.get('text')}")
    elif event_type == "error":
        print(f"    ERROR: {event.get('message')}")
    else:
        print(f"    event: {event_type}")


def _stream_chat(
    client: httpx.Client,
    path: str,
    *,
    message: str,
    conversation_id: int | None = None,
) -> tuple[list[dict[str, Any]], str]:
    payload: dict[str, Any] = {"message": message, "attachments": []}
    if conversation_id is not None:
        payload["conversation_id"] = conversation_id

    events: list[dict[str, Any]] = []
    with client.stream("POST", path, json=payload, timeout=None) as response:
        if response.status_code >= 400:
            raise RuntimeError(
                f"{path} HTTP {response.status_code}: {response.read().decode(errors='replace')[:500]}"
            )
        for event in _sse_events(response):
            events.append(event)
            _print_event(event)

    errors = [str(item.get("message") or "") for item in events if item.get("type") == "error"]
    if errors:
        raise RuntimeError(f"{path} SSE 返回 error：{' | '.join(errors)}")
    reply = "".join(str(item.get("text") or "") for item in events if item.get("type") == "delta")
    if not reply and not any(item.get("type") == "interrupt" for item in events):
        raise RuntimeError(f"{path} 没有 delta 或 interrupt 事件")
    if not any(item.get("type") == "done" for item in events):
        raise RuntimeError(f"{path} 缺少 done 事件")
    return events, reply


def _auth(
    client: httpx.Client,
    *,
    email: str,
    password: str,
    register: bool,
    username: str,
) -> tuple[str, int | None]:
    encrypted = _password_payload(password)
    if register:
        body = client.post(
            "/api/user/register/",
            json={"name": username, "email": email, "password": encrypted},
        )
        if body.status_code >= 400 or not _json(body).get("success"):
            print("  [INFO] 自动注册未成功，继续尝试登录（账号可能已存在）")

    response = client.post(
        "/api/user/login/",
        json={"email": email, "password": encrypted},
    )
    data = _data(_assert_success(response, "登录"), "登录")
    token = str(data.get("token") or "").strip()
    if not token:
        raise RuntimeError("登录成功但响应中没有 token")
    user = data.get("user") or {}
    user_id = user.get("user_id") if isinstance(user, dict) else None
    return token, int(user_id) if user_id is not None else None


def _assert_conversation(
    client: httpx.Client,
    path: str,
    conversation_id: int,
    *,
    label: str,
) -> None:
    response = client.get(path, params={"conversation_id": conversation_id})
    data = _data(_assert_success(response, f"{label}会话查询"), f"{label}会话查询")
    messages = data.get("messages")
    if not isinstance(messages, list) or not messages:
        raise RuntimeError(f"{label}会话查询没有消息")
    print(f"  {label}会话查询通过：messages={len(messages)}")


def run(args: argparse.Namespace) -> int:
    state = TestState()

    email = args.email or os.getenv("E2E_EMAIL", "")
    password = args.password or os.getenv("E2E_PASSWORD", "")
    if not email:
        email = f"e2e_{int(time.time())}_{secrets.token_hex(3)}@example.com"
    if not password:
        password = f"E2e-{secrets.token_urlsafe(12)}"
    username = args.username or f"e2e_{int(time.time())}"

    headers: dict[str, str] = {}
    with _httpx().Client(
        base_url=args.base_url.rstrip("/"),
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
    ) as client:
        health = client.get("/health")
        if health.status_code != 200:
            raise RuntimeError(f"健康检查失败：HTTP {health.status_code} {health.text[:300]}")
        print("[1/3] health 通过")

        token, state.user_id = _auth(
            client,
            email=email,
            password=password,
            register=args.register,
            username=username,
        )
        state.token = token
        headers["Authorization"] = f"Bearer {token}"
        client.headers.update(headers)
        _assert_success(client.get("/api/user/info/"), "用户信息")
        print(f"[2/3] 登录通过：user_id={state.user_id} email={email}")

        print("[3/3] 测试面试 Agent SSE")
        events, _ = _stream_chat(
            client,
            "/api/interview/chat/stream/",
            message=args.interview_message,
        )
        meta = next((item for item in events if item.get("type") == "meta"), {})
        state.interview_conversation_id = int(meta["conversation_id"])
        _assert_conversation(
            client,
            "/api/interview/chat/",
            state.interview_conversation_id,
            label="面试",
        )

    print("\n端到端测试全部通过。")
    print(f"账号：{email}，面试会话：{state.interview_conversation_id}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="测试面试 Agent SSE 全流程")
    parser.add_argument("--base-url", default=os.getenv("E2E_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--email", help="已有账号邮箱，也可用 E2E_EMAIL")
    parser.add_argument("--password", help="明文密码，也可用 E2E_PASSWORD；仅用于本次测试")
    parser.add_argument("--username", help="自动注册用户名")
    parser.add_argument("--register", action="store_true", help="先尝试注册账号，再登录")
    parser.add_argument("--interview-message", default="请解释一下 Python asyncio 和多线程的区别，按面试回答结构输出。")
    return parser.parse_args()


def main() -> int:
    try:
        return run(parse_args())
    except KeyboardInterrupt:
        print("\n用户中断测试", file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001
        print(f"\n端到端测试失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
