"""Contract Review schema baseline.

Revision ID: 0001_contract_review_baseline
Revises: None
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0001_contract_review_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contract_customers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_contract_customers_user_id", "contract_customers", ["user_id"], unique=False
    )

    op.create_table(
        "contracts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["contract_customers.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contracts_customer_id", "contracts", ["customer_id"], unique=False)
    op.create_index("ix_contracts_user_id", "contracts", ["user_id"], unique=False)

    op.create_table(
        "contract_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contract_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("source_key", sa.String(length=1024), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "contract_id", "number", name="uq_contract_versions_contract_number"
        ),
    )
    op.create_index(
        "ix_contract_versions_contract_id", "contract_versions", ["contract_id"], unique=False
    )
    op.create_index(
        "uq_contract_version_number",
        "contract_versions",
        ["contract_id", "number"],
        unique=True,
    )

    op.create_table(
        "contract_analysis_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("document_text", sa.Text(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("workflow_name", sa.String(length=64), nullable=False),
        sa.Column("current_step", sa.String(length=64), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("prompt_version", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["version_id"], ["contract_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_contract_analysis_runs_version_id",
        "contract_analysis_runs",
        ["version_id"],
        unique=False,
    )
    active_run = sa.text("status IN ('pending', 'parsing', 'analyzing')")
    op.create_index(
        "uq_contract_active_analysis",
        "contract_analysis_runs",
        ["version_id"],
        unique=True,
        postgresql_where=active_run,
        sqlite_where=active_run,
    )

    op.create_table(
        "contract_version_contents",
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("document_text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("parser_name", sa.String(length=64), nullable=False),
        sa.Column("parser_version", sa.String(length=32), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.ForeignKeyConstraint(["version_id"], ["contract_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("version_id"),
    )
    op.create_index(
        "ix_contract_version_contents_content_hash",
        "contract_version_contents",
        ["content_hash"],
        unique=False,
    )

    op.create_table(
        "contract_clauses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("clause_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("locator", sa.JSON(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["contract_analysis_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["version_id"], ["contract_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "sequence", name="uq_contract_clause_run_sequence"),
    )
    op.create_index("ix_contract_clauses_clause_type", "contract_clauses", ["clause_type"])
    op.create_index("ix_contract_clauses_run_id", "contract_clauses", ["run_id"])
    op.create_index("ix_contract_clauses_version_id", "contract_clauses", ["version_id"])

    op.create_table(
        "contract_risks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("clause_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("risk_level", sa.String(length=16), nullable=False),
        sa.Column("evidence_text", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("suggestion", sa.Text(), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("reviewer_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.ForeignKeyConstraint(["clause_id"], ["contract_clauses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["run_id"], ["contract_analysis_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["version_id"], ["contract_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contract_risks_clause_id", "contract_risks", ["clause_id"])
    op.create_index("ix_contract_risks_review_status", "contract_risks", ["review_status"])
    op.create_index("ix_contract_risks_risk_level", "contract_risks", ["risk_level"])
    op.create_index("ix_contract_risks_run_id", "contract_risks", ["run_id"])
    op.create_index("ix_contract_risks_version_id", "contract_risks", ["version_id"])

    op.create_table(
        "contract_review_selections",
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column(
            "selected_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["contract_analysis_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["version_id"], ["contract_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("version_id"),
    )
    op.create_index(
        "ix_contract_review_selections_run_id",
        "contract_review_selections",
        ["run_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_contract_review_selections_run_id", table_name="contract_review_selections")
    op.drop_table("contract_review_selections")

    op.drop_index("ix_contract_risks_version_id", table_name="contract_risks")
    op.drop_index("ix_contract_risks_run_id", table_name="contract_risks")
    op.drop_index("ix_contract_risks_risk_level", table_name="contract_risks")
    op.drop_index("ix_contract_risks_review_status", table_name="contract_risks")
    op.drop_index("ix_contract_risks_clause_id", table_name="contract_risks")
    op.drop_table("contract_risks")

    op.drop_index("ix_contract_clauses_version_id", table_name="contract_clauses")
    op.drop_index("ix_contract_clauses_run_id", table_name="contract_clauses")
    op.drop_index("ix_contract_clauses_clause_type", table_name="contract_clauses")
    op.drop_table("contract_clauses")

    op.drop_index(
        "ix_contract_version_contents_content_hash", table_name="contract_version_contents"
    )
    op.drop_table("contract_version_contents")

    op.drop_index("uq_contract_active_analysis", table_name="contract_analysis_runs")
    op.drop_index("ix_contract_analysis_runs_version_id", table_name="contract_analysis_runs")
    op.drop_table("contract_analysis_runs")

    op.drop_index("uq_contract_version_number", table_name="contract_versions")
    op.drop_index("ix_contract_versions_contract_id", table_name="contract_versions")
    op.drop_table("contract_versions")

    op.drop_index("ix_contracts_user_id", table_name="contracts")
    op.drop_index("ix_contracts_customer_id", table_name="contracts")
    op.drop_table("contracts")

    op.drop_index("ix_contract_customers_user_id", table_name="contract_customers")
    op.drop_table("contract_customers")
