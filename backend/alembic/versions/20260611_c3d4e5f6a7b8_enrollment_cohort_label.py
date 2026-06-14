"""enrollment cohort_label

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-11 20:00:00.000000

Sprint 13: optional enrollment batch label for cohort filtering.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "enrollments",
        sa.Column("cohort_label", sa.String(length=80), nullable=True),
    )
    op.create_index(
        "ix_enrollments_course_cohort_label",
        "enrollments",
        ["course_id", "cohort_label"],
    )


def downgrade() -> None:
    op.drop_index("ix_enrollments_course_cohort_label", table_name="enrollments")
    op.drop_column("enrollments", "cohort_label")
