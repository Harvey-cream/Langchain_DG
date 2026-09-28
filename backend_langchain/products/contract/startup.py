import logging

from sqlalchemy import inspect, text

from common.database import engine

logger = logging.getLogger(__name__)


def _contract_runtime_tables_exist(sync_conn) -> bool:
    tables = set(inspect(sync_conn).get_table_names())
    return {"contract_versions", "contract_analysis_runs"}.issubset(tables)


async def recover_interrupted_contract_reviews() -> None:
    """服务重启后把未完成的合同分析标记为失败，不创建或修改表结构。"""
    async with engine.begin() as conn:
        if not await conn.run_sync(_contract_runtime_tables_exist):
            logger.warning("Contract Schema 尚未迁移，跳过中断任务恢复；请先运行 alembic upgrade head")
            return
        interrupted = "('pending','parsing','analyzing')"
        await conn.execute(text("UPDATE contract_versions SET status='failed' WHERE id IN (SELECT version_id FROM contract_analysis_runs " f"WHERE status IN {interrupted})"))
        await conn.execute(text("UPDATE contract_analysis_runs SET status='failed', error='服务重启中断了分析，请重新分析', " "finished_at=COALESCE(finished_at, CURRENT_TIMESTAMP) " f"WHERE status IN {interrupted}"))
