from __future__ import annotations

from datetime import date, datetime


def format_datetime(dt: datetime | date | str | None) -> str:
    if not dt:
        return ""
    if isinstance(dt, str):
        return dt
    if isinstance(dt, date) and not isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d")
    return dt.strftime("%Y-%m-%d %H:%M:%S")
