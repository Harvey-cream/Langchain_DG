"""Add canonical version clauses alongside untouched legacy run clauses."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004_canonical_document_clauses"
down_revision = "0003_document_blocks"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "contract_document_clauses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("version_id", sa.Uuid(), sa.ForeignKey("contract_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("clause_type", sa.String(64), nullable=False),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("source_block_ids", sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False),
        sa.Column("pages", sa.JSON(), nullable=False),
        sa.Column("intelligence_version", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("version_id", "sequence", name="uq_contract_document_clause_sequence"),
    )
    op.create_index("ix_contract_document_clauses_version_id", "contract_document_clauses", ["version_id"])


def downgrade():
    op.drop_table("contract_document_clauses")
