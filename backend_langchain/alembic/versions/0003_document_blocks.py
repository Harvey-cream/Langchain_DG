"""Add version-owned source blocks; never migrate legacy Review clauses."""
from alembic import op
import sqlalchemy as sa

revision = "0003_document_blocks"
down_revision = "0002_contract_schema_alignment"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "contract_document_blocks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("version_id", sa.Uuid(), sa.ForeignKey("contract_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("version_id", "sequence", name="uq_contract_block_version_sequence"),
    )
    op.create_index("ix_contract_document_blocks_version_id", "contract_document_blocks", ["version_id"])


def downgrade():
    op.drop_table("contract_document_blocks")
