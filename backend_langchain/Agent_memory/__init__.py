"""
Agent_memory：会话历史压缩。

模块分区：
- memory_trim.py   — Turn 域（切分、完整性、按轮裁剪）
- token_budget.py  — Token 域（估算 token，供触发判定）
- memory.py        — 主编排（Turn OR Token 触发 → 共用摘要与写回）
- memory_summary.py — 共用（LLM rolling 摘要）
- memory_persist.py — 共用（异步落 Postgres）
"""
