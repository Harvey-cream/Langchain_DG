"""Read-only Contract Schema and data audit used before Alembic stamping."""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterable
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError

from app.settings import DATABASE_URL


BASELINE_REVISION = "0001_contract_review_baseline"
HEAD_REVISION = "0002_contract_schema_alignment"
REQUIRED_COLUMNS: dict[str, set[str]] = {
    "contract_customers": {"id", "user_id", "name", "email", "created_at", "updated_at"},
    "contracts": {"id", "user_id", "customer_id", "title", "created_at", "updated_at"},
    "contract_versions": {
        "id", "contract_id", "number", "source_key", "filename", "status", "created_at"
    },
    "contract_version_contents": {
        "version_id", "document_text", "content_hash", "parser_name", "parser_version",
        "page_count", "character_count", "created_at", "updated_at",
    },
    "contract_analysis_runs": {
        "id", "version_id", "status", "document_text", "result", "error", "workflow_name",
        "current_step", "attempt", "model_name", "prompt_version", "created_at", "started_at",
        "finished_at",
    },
    "contract_clauses": {
        "id", "version_id", "run_id", "sequence", "clause_type", "title", "original_text",
        "summary", "locator", "created_at",
    },
    "contract_risks": {
        "id", "version_id", "run_id", "clause_id", "title", "risk_level", "evidence_text",
        "reason", "suggestion", "review_status", "reviewer_note", "created_at", "updated_at",
    },
    "contract_review_selections": {"version_id", "run_id", "selected_at"},
}
REQUIRED_FOREIGN_KEYS = {
    ("contract_customers", ("user_id",), "users", ("user_id",)),
    ("contracts", ("user_id",), "users", ("user_id",)),
    ("contracts", ("customer_id",), "contract_customers", ("id",)),
    ("contract_versions", ("contract_id",), "contracts", ("id",)),
    ("contract_version_contents", ("version_id",), "contract_versions", ("id",)),
    ("contract_analysis_runs", ("version_id",), "contract_versions", ("id",)),
    ("contract_clauses", ("version_id",), "contract_versions", ("id",)),
    ("contract_clauses", ("run_id",), "contract_analysis_runs", ("id",)),
    ("contract_risks", ("version_id",), "contract_versions", ("id",)),
    ("contract_risks", ("run_id",), "contract_analysis_runs", ("id",)),
    ("contract_risks", ("clause_id",), "contract_clauses", ("id",)),
    ("contract_review_selections", ("version_id",), "contract_versions", ("id",)),
    ("contract_review_selections", ("run_id",), "contract_analysis_runs", ("id",)),
}
REQUIRED_INDEXES = {
    "uq_contract_active_analysis",
    "ix_contract_versions_contract_id",
    "ix_contract_analysis_runs_version_id",
}


def _sync_url(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)


def _column_tuple(columns: Iterable[str]) -> tuple[str, ...]:
    return tuple(columns)


def _unique_column_sets(insp, table: str) -> set[tuple[str, ...]]:
    values = {
        _column_tuple(item.get("column_names") or ())
        for item in insp.get_unique_constraints(table)
    }
    values.update(
        _column_tuple(item.get("column_names") or ())
        for item in insp.get_indexes(table)
        if item.get("unique")
    )
    return values


def _scalar_rows(conn: Connection, sql: str) -> list[dict[str, object]]:
    return [dict(row._mapping) for row in conn.execute(text(sql)).fetchall()]


def audit(conn: Connection, *, target: str = "head") -> dict[str, object]:
    if target not in {"baseline", "head"}:
        raise ValueError(f"unknown audit target: {target}")
    expected_revision = BASELINE_REVISION if target == "baseline" else HEAD_REVISION
    insp = inspect(conn)
    table_names = set(insp.get_table_names())
    issues: list[str] = []
    warnings: list[str] = []

    for table, required in REQUIRED_COLUMNS.items():
        if table not in table_names:
            issues.append(f"missing table: {table}")
            continue
        actual = {column["name"] for column in insp.get_columns(table)}
        for column in sorted(required - actual):
            issues.append(f"missing column: {table}.{column}")

    actual_fks: set[tuple[str, tuple[str, ...], str, tuple[str, ...]]] = set()
    for table in REQUIRED_COLUMNS.keys() & table_names:
        for fk in insp.get_foreign_keys(table):
            referred_table = fk.get("referred_table")
            if referred_table:
                actual_fks.add(
                    (
                        table,
                        _column_tuple(fk.get("constrained_columns") or ()),
                        referred_table,
                        _column_tuple(fk.get("referred_columns") or ()),
                    )
                )
    for fk in sorted(REQUIRED_FOREIGN_KEYS - actual_fks):
        issues.append(f"missing foreign key: {fk[0]}{fk[1]} -> {fk[2]}{fk[3]}")

    indexes_by_name = {
        index["name"]: index
        for table in REQUIRED_COLUMNS.keys() & table_names
        for index in insp.get_indexes(table)
    }
    all_indexes = set(indexes_by_name)
    for index_name in sorted(REQUIRED_INDEXES - all_indexes):
        issues.append(f"missing index: {index_name}")
    if target == "head" and "ix_contract_versions_status" not in all_indexes:
        issues.append("missing index: ix_contract_versions_status")
    active_index = indexes_by_name.get("uq_contract_active_analysis")
    if active_index is not None:
        if not active_index.get("unique"):
            issues.append("index uq_contract_active_analysis is not unique")
        if tuple(active_index.get("column_names") or ()) != ("version_id",):
            issues.append("index uq_contract_active_analysis has unexpected columns")
        predicate = str(
            (active_index.get("dialect_options") or {}).get("postgresql_where") or ""
        ).lower()
        if predicate and not all(status in predicate for status in ("pending", "parsing", "analyzing")):
            issues.append("index uq_contract_active_analysis has unexpected predicate")

    if "contract_versions" in table_names:
        version_uniques = {
            item.get("name"): _column_tuple(item.get("column_names") or ())
            for item in insp.get_unique_constraints("contract_versions")
        }
        expected_constraint = (
            "uq_contract_versions_contract_number"
            if target == "baseline"
            else "uq_contract_version_number"
        )
        if version_uniques.get(expected_constraint) != ("contract_id", "number"):
            issues.append(f"missing unique constraint: {expected_constraint}")
        if target == "baseline":
            legacy_index = indexes_by_name.get("uq_contract_version_number")
            if (
                legacy_index is None
                or not legacy_index.get("unique")
                or _column_tuple(legacy_index.get("column_names") or ())
                != ("contract_id", "number")
            ):
                issues.append("missing legacy unique index: uq_contract_version_number")
        elif "uq_contract_versions_contract_number" in version_uniques:
            issues.append("legacy unique constraint still present: uq_contract_versions_contract_number")
        if ("contract_id", "number") not in _unique_column_sets(insp, "contract_versions"):
            issues.append("missing unique constraint: contract_versions(contract_id, number)")
        duplicate_versions = _scalar_rows(
            conn,
            """
            SELECT contract_id, number, COUNT(*) AS row_count
            FROM contract_versions
            GROUP BY contract_id, number
            HAVING COUNT(*) > 1
            ORDER BY row_count DESC
            LIMIT 20
            """,
        )
        if duplicate_versions:
            issues.append(f"duplicate version numbers: {len(duplicate_versions)} group(s)")
    else:
        duplicate_versions = []

    if "contract_analysis_runs" in table_names:
        duplicate_active_runs = _scalar_rows(
            conn,
            """
            SELECT version_id, COUNT(*) AS row_count
            FROM contract_analysis_runs
            WHERE status IN ('pending', 'parsing', 'analyzing')
            GROUP BY version_id
            HAVING COUNT(*) > 1
            ORDER BY row_count DESC
            LIMIT 20
            """,
        )
        if duplicate_active_runs:
            issues.append(f"multiple active runs: {len(duplicate_active_runs)} version(s)")
    else:
        duplicate_active_runs = []

    if "contract_clauses" in table_names:
        if ("run_id", "sequence") not in _unique_column_sets(insp, "contract_clauses"):
            issues.append("missing unique constraint: contract_clauses(run_id, sequence)")

    if "contract_review_selections" in table_names:
        if ("run_id",) not in _unique_column_sets(insp, "contract_review_selections"):
            issues.append("missing unique constraint: contract_review_selections(run_id)")

    stamped_revision: str | None = None
    if "alembic_version" in table_names:
        stamped_revision = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
        if stamped_revision != expected_revision:
            warnings.append(
                f"database revision is {stamped_revision!r}, expected {expected_revision!r}"
            )
    else:
        warnings.append("alembic_version is absent; audit before stamping is expected to show this")

    return {
        "ok": not issues,
        "baseline_revision": BASELINE_REVISION,
        "head_revision": HEAD_REVISION,
        "audit_target": target,
        "expected_revision": expected_revision,
        "stamped_revision": stamped_revision,
        "issues": issues,
        "warnings": warnings,
        "data_checks": {
            "duplicate_version_numbers": duplicate_versions,
            "multiple_active_runs": duplicate_active_runs,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default=os.environ.get("CONTRACT_SCHEMA_DATABASE_URL") or DATABASE_URL,
        help="Database URL; defaults to application settings (never printed).",
    )
    parser.add_argument(
        "--target",
        choices=("baseline", "head"),
        default="head",
        help="Audit legacy baseline before stamp, or the current Alembic head.",
    )
    args = parser.parse_args()
    url = _sync_url(args.url)
    connect_args = {"connect_timeout": 5} if url.startswith("postgresql") else {}
    engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
    try:
        with engine.connect() as conn:
            report = audit(conn, target=args.target)
    except SQLAlchemyError as exc:
        print(json.dumps({"ok": False, "connection_error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    finally:
        engine.dispose()
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
