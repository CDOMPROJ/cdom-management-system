"""empty message

Revision ID: 2215cbdb4c33
Revises: 20260406_0003
Create Date: 2026-04-06 03:01:45.123456

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2215cbdb4c33'
down_revision: Union[str, None] = '20260406_0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass   # This is an empty merge migration - no schema changes


def downgrade() -> None:
    pass   # This is an empty merge migration - no schema changes