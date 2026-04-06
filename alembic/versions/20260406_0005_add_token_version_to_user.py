"""add token_version to users for logout-from-all-devices

Revision ID: 20260406_0005
Revises: 20260406_0004
Create Date: 2026-04-06 00:05:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260406_0005'
down_revision = '20260406_0004'
branch_labels = None
depends_on = None

def upgrade():
    # ==========================================
    # Add token_version column
    # ==========================================
    op.add_column('users', sa.Column('token_version', sa.Integer(), nullable=False, server_default='0'))

def downgrade():
    # ==========================================
    # Remove token_version column
    # ==========================================
    op.drop_column('users', 'token_version')