"""sprint6_comment_parent_id

Revision ID: 25fabf9abf19
Revises: cb4b65126a34
Create Date: 2026-06-09 15:33:14.566234

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '25fabf9abf19'
down_revision: Union[str, None] = 'cb4b65126a34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "instructor_comments",
        sa.Column(
            "parent_id",
            sa.UUID(),
            sa.ForeignKey("instructor_comments.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_instructor_comments_parent_id",
        "instructor_comments",
        ["parent_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_instructor_comments_parent_id", table_name="instructor_comments"
    )
    op.drop_column("instructor_comments", "parent_id")
