"""User-owned policies and immutable per-review policy snapshots."""

from alembic import op
import sqlalchemy as sa

revision = "0007_contract_policy"
down_revision = "0006_review_v2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "contract_policies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=False
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("category", sa.String(64), nullable=False, server_default="other"),
        sa.Column(
            "applicable_contract_types", sa.JSON(), nullable=False, server_default="[]"
        ),
        sa.Column(
            "applicable_party_role", sa.String(64), nullable=False, server_default=""
        ),
        sa.Column("requirement", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_contract_policies_user_id", "contract_policies", ["user_id"])
    for field in ("party_role", "contract_type"):
        op.add_column(
            "contract_analysis_runs",
            sa.Column(field, sa.String(64), nullable=False, server_default=""),
        )
    op.add_column(
        "contract_analysis_runs",
        sa.Column("context_snapshot", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "contract_risks",
        sa.Column("policy_ids", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade():
    conn = op.get_bind()
    if conn.scalar(sa.text("SELECT COUNT(*) FROM contract_policies")):
        raise RuntimeError("企业规则存在，请先备份并制定显式降级方案")
    snapshots = conn.execute(
        sa.text("SELECT context_snapshot FROM contract_analysis_runs")
    ).scalars()
    import json

    if any(
        (json.loads(value) if isinstance(value, str) else value).get("policies")
        for value in snapshots
    ):
        raise RuntimeError("历史审查含企业规则快照，不能静默降级")
    op.drop_column("contract_risks", "policy_ids")
    for field in ("context_snapshot", "contract_type", "party_role"):
        op.drop_column("contract_analysis_runs", field)
    op.drop_table("contract_policies")
