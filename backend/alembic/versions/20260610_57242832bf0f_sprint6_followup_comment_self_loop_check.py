"""sprint6_followup_comment_self_loop_check

Revision ID: 57242832bf0f
Revises: 25fabf9abf19
Create Date: 2026-06-10 09:19:41.937375

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '57242832bf0f'
down_revision: Union[str, None] = '25fabf9abf19'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # MED-1 (sprint-6 follow-up): direct self-loops are a sufficient
    # condition for the recursive CTE in services/comment.py to require
    # the depth cap. Belt-and-suspenders — the depth cap is the live
    # defense, this constraint catches the simplest invalid state at
    # write time and surfaces it as IntegrityError rather than a silent
    # query truncation.
    op.create_check_constraint(
        "ck_instructor_comments_no_self_parent",
        "instructor_comments",
        "parent_id IS NULL OR parent_id != id",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_instructor_comments_no_self_parent",
        "instructor_comments",
        type_="check",
    )
