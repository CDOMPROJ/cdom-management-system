"""merge heads

Revision ID: 20260406_0004
Revises: 20260406_0001, f1f548b6a1bd
Create Date: 2026-04-06 00:04:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260406_0004'
down_revision = ('20260406_0001', 'f1f548b6a1bd')
branch_labels = None
depends_on = None

def upgrade():
    pass   # Merge migration - no schema changes needed

def downgrade():
    pass   # Merge migration - no schema changes needed