"""merge securitypatch heads before office enum

Revision ID: 0afa1e4cb891
Revises: 20260406_0005, 837175b3de55
Create Date: 2026-04-06 16:54:01.901546

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0afa1e4cb891'
down_revision: Union[str, None] = ('20260406_0005', '837175b3de55')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
