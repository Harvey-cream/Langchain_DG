"""Run the Contract Alembic baseline against a disposable PostgreSQL database."""
from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import psycopg
from alembic import command
from alembic.config import Config
from psycopg import sql
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import URL

from app.models import User
from app.settings import (
    POSTGRES_DATABASE,
    POSTGRES_HOST,
    POSTGRES_PASSWORD,
    POSTGRES_PORT,
    POSTGRES_USER,
)
from scripts.audit_contract_schema import HEAD_REVISION, REQUIRED_COLUMNS, audit


def _url(database: str) -> URL:
    return URL.create(
        "postgresql+psycopg",
        username=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        host=POSTGRES_HOST,
        port=int(POSTGRES_PORT),
        database=database,
    )


def _psycopg_url(database: str) -> str:
    return _url(database).set(drivername="postgresql").render_as_string(hide_password=False)


def _drop_database(admin, database_name: str) -> None:
    admin.execute(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        "WHERE datname = %s AND pid <> pg_backend_pid()",
        (database_name,),
    )
    admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database_name)))


def main() -> int:
    database_name = f"contract_migration_test_{uuid4().hex[:12]}"
    admin_url = _psycopg_url(POSTGRES_DATABASE)
    print(f"creating disposable database {database_name}", flush=True)
    with psycopg.connect(admin_url, autocommit=True, connect_timeout=5) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))

    engine = create_engine(_url(database_name), connect_args={"connect_timeout": 5})
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option(
        "sqlalchemy.url", _url(database_name).render_as_string(hide_password=False)
    )
    try:
        # users remains legacy-owned and is the only prerequisite of Contract tables.
        print("creating legacy users prerequisite", flush=True)
        User.__table__.create(engine)
        print("running alembic upgrade head", flush=True)
        command.upgrade(config, "head")
        print("auditing migrated schema", flush=True)
        with engine.connect() as conn:
            report = audit(conn)
        if not report["ok"]:
            raise AssertionError(report)
        if report["stamped_revision"] != HEAD_REVISION:
            raise AssertionError(report)

        print("running alembic downgrade base", flush=True)
        command.downgrade(config, "base")
        remaining = set(inspect(engine).get_table_names())
        contract_tables = set(REQUIRED_COLUMNS)
        if remaining & contract_tables:
            raise AssertionError(f"downgrade left Contract tables: {remaining & contract_tables}")
        if "users" not in remaining:
            raise AssertionError("downgrade removed the legacy-owned users table")
        print("PostgreSQL Contract migration upgrade/audit/downgrade: passed")
        return 0
    finally:
        engine.dispose()
        print(f"dropping disposable database {database_name}", flush=True)
        with psycopg.connect(admin_url, autocommit=True, connect_timeout=5) as admin:
            _drop_database(admin, database_name)


if __name__ == "__main__":
    raise SystemExit(main())
