"""Version facts publication marker, shadow metadata and quality diagnostics."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005_document_facts"
down_revision = "0004_canonical_document_clauses"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "contract_document_facts",
        sa.Column("version_id", sa.Uuid(), sa.ForeignKey("contract_versions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("parser_version", sa.String(32), nullable=False),
        sa.Column("intelligence_version", sa.String(32), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("extracted_metadata", sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False),
        sa.Column("covered_blocks", sa.Integer(), nullable=False),
        sa.Column("total_blocks", sa.Integer(), nullable=False),
        sa.Column("coverage_ratio", sa.Float(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table("contract_document_facts")
