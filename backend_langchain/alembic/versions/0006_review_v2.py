"""Add Review V2 alongside immutable legacy Review rows."""
from alembic import op
import sqlalchemy as sa

revision = '0006_review_v2'
down_revision = '0005_document_facts'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('contract_analysis_runs', sa.Column('review_version', sa.String(16), nullable=False, server_default='v1'))
    op.add_column('contract_analysis_runs', sa.Column('our_party', sa.String(255), nullable=False, server_default=''))
    op.add_column('contract_document_blocks', sa.Column('join_previous', sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table('contract_risks') as batch:
        batch.add_column(sa.Column('canonical_clause_id', sa.Uuid(), nullable=True))
        batch.add_column(sa.Column('risk_type', sa.String(64), nullable=True))
        batch.add_column(sa.Column('related_clause_ids', sa.JSON(), nullable=False, server_default='[]'))
        batch.create_foreign_key('fk_contract_risk_canonical_clause', 'contract_document_clauses',
            ['canonical_clause_id'], ['id'], ondelete='CASCADE')
        batch.create_index('ix_contract_risks_canonical_clause_id', ['canonical_clause_id'])
        batch.create_check_constraint('ck_contract_risk_single_clause_source',
            'NOT (clause_id IS NOT NULL AND canonical_clause_id IS NOT NULL)')


def downgrade():
    # V2 findings cannot be represented in V1. Refuse to silently erase or detach them.
    conn = op.get_bind()
    if conn.scalar(sa.text("SELECT COUNT(*) FROM contract_analysis_runs WHERE review_version = 'v2'")):
        raise RuntimeError('Review V2 数据存在，不能降级并丢失审查协议/立场；请先备份并制定显式迁移')
    with op.batch_alter_table('contract_risks') as batch:
        batch.drop_constraint('ck_contract_risk_single_clause_source', type_='check')
        batch.drop_index('ix_contract_risks_canonical_clause_id')
        batch.drop_constraint('fk_contract_risk_canonical_clause', type_='foreignkey')
        batch.drop_column('related_clause_ids')
        batch.drop_column('risk_type')
        batch.drop_column('canonical_clause_id')
    op.drop_column('contract_document_blocks', 'join_previous')
    op.drop_column('contract_analysis_runs', 'our_party')
    op.drop_column('contract_analysis_runs', 'review_version')
