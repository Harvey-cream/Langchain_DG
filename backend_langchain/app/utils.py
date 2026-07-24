from __future__ import annotations

from datetime import date, datetime, timezone


def utc_now_naive() -> datetime:
    """UTC 时刻，无 tzinfo（匹配 PG TIMESTAMP WITHOUT TIME ZONE / asyncpg）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def format_datetime(dt: datetime | date | str | None) -> str:
    if not dt:
        return ""
    if isinstance(dt, str):
        return dt
    if isinstance(dt, date) and not isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d")
    return dt.strftime("%Y-%m-%d %H:%M:%S")
