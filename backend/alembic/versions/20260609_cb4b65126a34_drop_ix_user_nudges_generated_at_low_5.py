"""drop_ix_user_nudges_generated_at_low_5

Revision ID: cb4b65126a34
Revises: dc3aae18994c
Create Date: 2026-06-09 13:34:22.365199

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cb4b65126a34'
down_revision: Union[str, None] = 'dc3aae18994c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # LOW-5 (sprint-5 follow-up): the index was declared in the initial
    # user_nudges migration but never read by any query — cache lookups
    # go by PK user_id and freshness reads the row's own column.
    op.drop_index("ix_user_nudges_generated_at", table_name="user_nudges")


def downgrade() -> None:
    op.create_index(
        "ix_user_nudges_generated_at",
        "user_nudges",
        ["generated_at"],
        unique=False,
    )
