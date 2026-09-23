from __future__ import annotations

from uuid import UUID

from fastapi import BackgroundTasks


class FastApiBackgroundJobDispatcher:
    """当前进程内适配器；未来 MQ 实现只需替换这一边界。"""

    def __init__(self, background_tasks: BackgroundTasks):
        self.background_tasks = background_tasks

    async def dispatch_analysis(self, run_id: UUID) -> None:
        from infrastructure.document.contract_jobs import execute_analysis

        self.background_tasks.add_task(execute_analysis, run_id)
