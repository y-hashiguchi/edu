"""scheduled_broadcasts

Revision ID: b2c3d4e5f6a7
Revises: 53858e23cd1b
Create Date: 2026-06-11 18:00:00.000000

Sprint 11: admin-scheduled course broadcast notifications.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "53858e23cd1b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scheduled_broadcasts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sender_user_id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("link", sa.String(length=500), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_count", sa.Integer(), nullable=True),
        sa.Column("skipped_inbox_full", sa.Integer(), nullable=True),
        sa.Column("skipped_admin", sa.Integer(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["course_id"], ["courses.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["sender_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_scheduled_broadcasts_course_id"),
        "scheduled_broadcasts",
        ["course_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scheduled_broadcasts_sender_user_id"),
        "scheduled_broadcasts",
        ["sender_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_scheduled_broadcasts_pending_due",
        "scheduled_broadcasts",
        ["scheduled_at"],
        unique=False,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_scheduled_broadcasts_pending_due",
        table_name="scheduled_broadcasts",
    )
    op.drop_index(
        op.f("ix_scheduled_broadcasts_sender_user_id"),
        table_name="scheduled_broadcasts",
    )
    op.drop_index(
        op.f("ix_scheduled_broadcasts_course_id"),
        table_name="scheduled_broadcasts",
    )
    op.drop_table("scheduled_broadcasts")
