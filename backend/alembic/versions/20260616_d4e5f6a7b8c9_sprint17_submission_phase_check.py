"""Sprint 17 — relax submissions.phase CHECK (allow >4 phases).

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-16
"""

from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_submissions_phase", "submissions", type_="check")
    op.create_check_constraint(
        "ck_submissions_phase",
        "submissions",
        "phase >= 1",
    )


def downgrade() -> None:
    op.drop_constraint("ck_submissions_phase", "submissions", type_="check")
    op.create_check_constraint(
        "ck_submissions_phase",
        "submissions",
        "phase BETWEEN 1 AND 4",
    )
