"""add office enum with 8 values (spaced strings)

Revision ID: 239c5a02cc35
Revises: 0afa1e4cb891
Create Date: 2026-04-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '239c5a02cc35'
down_revision: Union[str, None] = '0afa1e4cb891'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. NORMALIZE EXISTING DATA to exact spaced strings you want
    op.execute("""
        UPDATE users SET office = CASE
            WHEN office ILIKE '%Parish Priest%' THEN 'Parish Priest'
            WHEN office ILIKE '%Assistant Priest%' THEN 'Assistant Priest'
            WHEN office ILIKE '%Deanery Youth Chaplain%' THEN 'Deanery Youth Chaplain'
            WHEN office ILIKE '%Parish Youth Chaplain%' THEN 'Parish Youth Chaplain'
            WHEN office ILIKE '%Dean%' THEN 'Dean'
            WHEN office ILIKE '%Bishop%' THEN 'Bishop'
            WHEN office ILIKE '%Sys Admin%' OR office ILIKE '%Diocesan ICT%' THEN 'Sys Admin'
            WHEN office ILIKE '%Parish Secretary%' THEN 'Parish Secretary'
            ELSE office
        END
        WHERE office IS NOT NULL;
    """)

    op.execute("""
        UPDATE user_invitations SET office = CASE
            WHEN office ILIKE '%Parish Priest%' THEN 'Parish Priest'
            WHEN office ILIKE '%Assistant Priest%' THEN 'Assistant Priest'
            WHEN office ILIKE '%Deanery Youth Chaplain%' THEN 'Deanery Youth Chaplain'
            WHEN office ILIKE '%Parish Youth Chaplain%' THEN 'Parish Youth Chaplain'
            WHEN office ILIKE '%Dean%' THEN 'Dean'
            WHEN office ILIKE '%Bishop%' THEN 'Bishop'
            WHEN office ILIKE '%Sys Admin%' OR office ILIKE '%Diocesan ICT%' THEN 'Sys Admin'
            WHEN office ILIKE '%Parish Secretary%' THEN 'Parish Secretary'
            ELSE office
        END
        WHERE office IS NOT NULL;
    """)

    # 2. Create the PostgreSQL ENUM with exact spaced strings
    op.execute("""
        CREATE TYPE office AS ENUM (
            'Bishop',
            'Sys Admin',
            'Dean',
            'Deanery Youth Chaplain',
            'Parish Priest',
            'Assistant Priest',
            'Parish Youth Chaplain',
            'Parish Secretary'
        )
    """)

    # 3. Convert columns to the Enum
    op.alter_column('users', 'office',
                    existing_type=sa.VARCHAR(),
                    type_=sa.Enum('Bishop', 'Sys Admin', 'Dean', 'Deanery Youth Chaplain',
                                  'Parish Priest', 'Assistant Priest', 'Parish Youth Chaplain',
                                  'Parish Secretary', name='office'),
                    existing_nullable=False,
                    postgresql_using="office::office")

    op.alter_column('user_invitations', 'office',
                    existing_type=sa.VARCHAR(),
                    type_=sa.Enum('Bishop', 'Sys Admin', 'Dean', 'Deanery Youth Chaplain',
                                  'Parish Priest', 'Assistant Priest', 'Parish Youth Chaplain',
                                  'Parish Secretary', name='office'),
                    existing_nullable=False,
                    postgresql_using="office::office")


def downgrade() -> None:
    op.alter_column('users', 'office',
                    existing_type=sa.Enum('Bishop', 'Sys Admin', 'Dean', 'Deanery Youth Chaplain',
                                          'Parish Priest', 'Assistant Priest', 'Parish Youth Chaplain',
                                          'Parish Secretary', name='office'),
                    type_=sa.VARCHAR(),
                    existing_nullable=False)

    op.alter_column('user_invitations', 'office',
                    existing_type=sa.Enum('Bishop', 'Sys Admin', 'Dean', 'Deanery Youth Chaplain',
                                          'Parish Priest', 'Assistant Priest', 'Parish Youth Chaplain',
                                          'Parish Secretary', name='office'),
                    type_=sa.VARCHAR(),
                    existing_nullable=False)

    op.execute("DROP TYPE office")