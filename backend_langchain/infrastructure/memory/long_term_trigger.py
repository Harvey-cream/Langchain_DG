"""Memory Trigger：规则过滤，避免每轮启动 Memory Agent。"""
from __future__ import annotations

import os
import re

# 明确表达长期偏好 / 目标 / 约束 / 记忆指令
_POSITIVE = re.compile(
    r"(记住|别忘|不要忘记|以后|默认|我喜欢|我不喜欢|偏好|习惯|"
    r"我的目标|我想|我打算|请用|别用|不要用|称呼我|叫我|"
    r"技术栈|岗位|方向是|我是做|我主攻)",
    re.I,
)

# 明显无长期价值
_NEGATIVE = re.compile(
    r"^(好的?|嗯+|哦+|继续|谢谢|感谢|收到|ok|okay|yes|no|是的?|不是|"
    r"可以|行|加油|你好|在吗)[\s!！。.~…]*$",
    re.I,
)


def _min_chars() -> int:
    raw = (os.getenv("MEMORY_TRIGGER_MIN_CHARS", "16") or "16").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 16


def memory_agent_enabled() -> bool:
    raw = (os.getenv("MEMORY_AGENT_ENABLED", "1") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


# 读侧：引用既往偏好 / 习惯（与写侧正向互补）
_RETRIEVE_HINT = re.compile(
    r"(按我|根据我|我之前|上次|习惯|偏好|别忘|记住的|我说过|我提过)",
    re.I,
)


def should_retrieve_memory(user_text: str) -> bool:
    """读侧 Trigger：有偏好/习惯信号才检索长期记忆。"""
    user = (user_text or "").strip()
    if not user:
        return False
    if _NEGATIVE.match(user):
        return False
    if _POSITIVE.search(user) or _RETRIEVE_HINT.search(user):
        return True
    if len(user) < _min_chars():
        return False
    return "我" in user and len(user) >= _min_chars()


def should_run_memory_agent(*, user_text: str, assistant_text: str = "") -> bool:
    """有长期价值才返回 True。先看用户话，必要时扫助手摘要句。"""
    user = (user_text or "").strip()
    if not user:
        return False
    if _NEGATIVE.match(user):
        return False
    if _POSITIVE.search(user):
        return True
    if len(user) < _min_chars():
        return False
    # 较长且含「我」的陈述更可能含画像信息
    if "我" in user and len(user) >= _min_chars():
        return True
    asst = (assistant_text or "").strip()
    if asst and _POSITIVE.search(asst[:500]):
        return True
    return False
