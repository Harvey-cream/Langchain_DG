"""Align legacy Contract version constraints with current ORM metadata.

Revision ID: 0002_contract_schema_alignment
Revises: 0001_contract_review_baseline
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "0002_contract_schema_alignment"
down_revision: str | None = "0001_contract_review_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The legacy schema has both objects on the same columns. Keep the constraint
    # in place while removing the redundant index, then rename it transactionally.
    op.drop_index("uq_contract_version_number", table_name="contract_versions")
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE contract_versions "
            "RENAME CONSTRAINT uq_contract_versions_contract_number "
            "TO uq_contract_version_number"
        )
    else:
        with op.batch_alter_table("contract_versions") as batch_op:
            batch_op.drop_constraint(
                "uq_contract_versions_contract_number", type_="unique"
            )
            batch_op.create_unique_constraint(
                "uq_contract_version_number", ["contract_id", "number"]
            )
    op.create_index(
        "ix_contract_versions_status", "contract_versions", ["status"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_contract_versions_status", table_name="contract_versions")
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE contract_versions "
            "RENAME CONSTRAINT uq_contract_version_number "
            "TO uq_contract_versions_contract_number"
        )
    else:
        with op.batch_alter_table("contract_versions") as batch_op:
            batch_op.drop_constraint("uq_contract_version_number", type_="unique")
            batch_op.create_unique_constraint(
                "uq_contract_versions_contract_number", ["contract_id", "number"]
            )
    op.create_index(
        "uq_contract_version_number",
        "contract_versions",
        ["contract_id", "number"],
        unique=True,
    )
