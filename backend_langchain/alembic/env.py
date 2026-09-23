from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from app.settings import DATABASE_URL
from infrastructure.db.base import Base

# Register every table in the shared metadata. Autogenerate is filtered to Contract.
import app.models  # noqa: F401,E402
import infrastructure.db.models.analysis  # noqa: F401,E402
import infrastructure.db.models.contract  # noqa: F401,E402
import infrastructure.db.models.customer  # noqa: F401,E402
import infrastructure.db.models.review  # noqa: F401,E402
import infrastructure.db.models.version  # noqa: F401,E402


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

CONTRACT_TABLE_NAMES = frozenset(
    {
        "contract_customers",
        "contracts",
        "contract_versions",
        "contract_version_contents",
        "contract_analysis_runs",
        "contract_clauses",
        "contract_risks",
        "contract_review_selections",
    }
)
target_metadata = Base.metadata


def _database_url() -> str:
    configured = config.get_main_option("sqlalchemy.url").strip()
    return os.environ.get("ALEMBIC_DATABASE_URL", "").strip() or configured or DATABASE_URL


def _sync_url(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)


def _include_object(obj, name, type_, reflected, compare_to) -> bool:
    if type_ == "table":
        return name in CONTRACT_TABLE_NAMES
    table = getattr(obj, "table", None)
    return table is None or table.name in CONTRACT_TABLE_NAMES


def run_migrations_offline() -> None:
    context.configure(
        url=_sync_url(_database_url()),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=_include_object,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=_include_object,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = _sync_url(_database_url())
    connect_args = {"connect_timeout": 5} if url.startswith("postgresql") else {}
    engine = create_engine(url, poolclass=NullPool, connect_args=connect_args)
    with engine.connect() as connection:
        _run_migrations(connection)
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
