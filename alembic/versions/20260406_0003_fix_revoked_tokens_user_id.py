"""fix revoked_tokens user_id to UUID to match users.id

Revision ID: 20260406_0003
Revises: 20260406_0001
Create Date: 2026-04-06 00:03:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

# revision identifiers, used by Alembic.
revision = '20260406_0003'
down_revision = '20260406_0001'
branch_labels = None
depends_on = None

def upgrade():
    # Drop the incorrectly created table
    op.drop_table('revoked_tokens')

    # Recreate with correct UUID types
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
    # Revert to previous (incorrect) Integer version
    op.drop_table('revoked_tokens')
    op.create_table(
        'revoked_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('jti', sa.String(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('reason', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('jti')
    )
    op.create_index('ix_revoked_tokens_jti', 'revoked_tokens', ['jti'])
    op.create_index('ix_revoked_tokens_expires_at', 'revoked_tokens', ['expires_at'])
    op.create_foreign_key('fk_revoked_tokens_user_id', 'revoked_tokens', 'users', ['user_id'], ['id'])