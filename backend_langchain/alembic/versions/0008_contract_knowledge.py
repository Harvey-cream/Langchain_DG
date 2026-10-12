"""Private reference documents, transactional pgvector and lexical indexes."""

import json
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "0008_contract_knowledge"
down_revision = "0007_contract_policy"
branch_labels = None
depends_on = None


def upgrade():
    postgres = op.get_bind().dialect.name == "postgresql"
    if postgres:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "contract_knowledge_documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=False
        ),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("source_key", sa.String(1024), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("document_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("category", sa.String(64), nullable=False, server_default="other"),
        sa.Column("status", sa.String(32), nullable=False, server_default="uploaded"),
        sa.Column("generation", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("byte_count", sa.Integer(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("embedding_model", sa.String(128), nullable=False, server_default=""),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
    )
    for column in ("user_id", "status"):
        op.create_index(
            f"ix_contract_knowledge_documents_{column}",
            "contract_knowledge_documents",
            [column],
        )
    op.create_index(
        "uq_contract_knowledge_owned_hash",
        "contract_knowledge_documents",
        ["user_id", "content_hash"],
        unique=True,
        postgresql_where=sa.text("status != 'deleted'"),
        sqlite_where=sa.text("status != 'deleted'"),
    )
    op.create_table(
        "contract_knowledge_chunks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("contract_knowledge_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=False
        ),
        sa.Column("document_version", sa.Integer(), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("locator", sa.JSON(), nullable=False),
        sa.Column("token_index", sa.JSON(), nullable=False),
        sa.Column("embedding", Vector(1024) if postgres else sa.JSON(), nullable=False),
        sa.Column("embedding_model", sa.String(128), nullable=False),
        sa.UniqueConstraint(
            "document_id",
            "generation",
            "sequence",
            name="uq_contract_knowledge_chunk_sequence",
        ),
    )
    for column in ("document_id", "user_id"):
        op.create_index(
            f"ix_contract_knowledge_chunks_{column}",
            "contract_knowledge_chunks",
            [column],
        )
    if postgres:
        op.create_index(
            "ix_contract_knowledge_embedding",
            "contract_knowledge_chunks",
            ["embedding"],
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        )
    op.add_column(
        "contract_risks",
        sa.Column(
            "reference_citations", sa.JSON(), nullable=False, server_default="[]"
        ),
    )


def downgrade():
    conn = op.get_bind()
    if conn.scalar(sa.text("SELECT COUNT(*) FROM contract_knowledge_documents")):
        raise RuntimeError("知识库文档存在，不能静默降级丢失原件索引")
    snapshots = conn.execute(
        sa.text("SELECT context_snapshot FROM contract_analysis_runs")
    ).scalars()
    if any(
        (json.loads(v) if isinstance(v, str) else v).get("references")
        for v in snapshots
    ):
        raise RuntimeError("历史审查含知识库引用，不能静默降级")
    op.drop_column("contract_risks", "reference_citations")
    op.drop_table("contract_knowledge_chunks")
    op.drop_table("contract_knowledge_documents")
    # The shared vector extension belongs to other products too; never drop it here.
