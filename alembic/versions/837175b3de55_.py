"""empty message

Revision ID: 837175b3de55
Revises: 2215cbdb4c33
Create Date: 2026-04-06 03:02:02.664632

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '837175b3de55'
down_revision: Union[str, None] = '2215cbdb4c33'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass   # This is an empty merge migration - no schema changes


def downgrade() -> None:
    pass   # This is an empty merge migration - no schema changes