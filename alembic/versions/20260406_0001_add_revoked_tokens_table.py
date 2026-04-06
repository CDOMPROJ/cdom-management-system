"""add revoked_tokens table with UUID to match users.id

Revision ID: 20260406_0001
Revises: f1f548b6a1bd
Create Date: 2026-04-06 00:01:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

# revision identifiers, used by Alembic.
revision = '20260406_0001'
down_revision = 'f1f548b6a1bd'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'revoked_tokens',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('jti', sa.String(), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('reason', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('jti')
    )
    op.create_index('ix_revoked_tokens_jti', 'revoked_tokens', ['jti'])
    op.create_index('ix_revoked_tokens_expires_at', 'revoked_tokens', ['expires_at'])
    op.create_foreign_key('fk_revoked_tokens_user_id', 'revoked_tokens', 'users', ['user_id'], ['id'])

def downgrade():
    op.drop_index('ix_revoked_tokens_expires_at', table_name='revoked_tokens')
    op.drop_index('ix_revoked_tokens_jti', table_name='revoked_tokens')
    op.drop_constraint('fk_revoked_tokens_user_id', 'revoked_tokens', type_='foreignkey')
    op.drop_table('revoked_tokens')