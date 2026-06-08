"""sprint5_user_nudges

Revision ID: dc3aae18994c
Revises: af4220e315e6
Create Date: 2026-06-09 00:17:08.795206

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dc3aae18994c'
down_revision: Union[str, None] = 'af4220e315e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_nudges",
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("body", sa.String(length=500), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("input_signature", sa.String(length=16), nullable=False),
    )
    op.create_index(
        "ix_user_nudges_generated_at",
        "user_nudges",
        ["generated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_user_nudges_generated_at", table_name="user_nudges")
    op.drop_table("user_nudges")
