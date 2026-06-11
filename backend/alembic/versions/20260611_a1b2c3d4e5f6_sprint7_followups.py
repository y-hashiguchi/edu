"""sprint7_followups

Revision ID: a1b2c3d4e5f6
Revises: 75b4bc4af35b
Create Date: 2026-06-11 16:30:00.000000

LOW-3: prefix ai-driven-dev embedding source_ref with course slug.
LOW-4: optional course_id on notifications for broadcast audit trail.
LOW-1: backfill ai-era-se progress rows for phases 2-4 (locked).
"""

import uuid

import sqlalchemy as sa
from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "75b4bc4af35b"
branch_labels = None
depends_on = None

AI_DRIVEN_DEV_UUID = "00000000-0000-4000-8000-000000000001"
AI_ERA_SE_UUID = "00000000-0000-4000-8000-000000000002"


def upgrade() -> None:
    # LOW-3: course:ai-driven-dev:phase:N:task:N (and :skill:N)
    op.execute(
        sa.text(
            """
            UPDATE embeddings
            SET source_ref = 'course:ai-driven-dev:' || source_ref
            WHERE course_id = :course_id
              AND source_ref LIKE 'phase:%'
              AND source_ref NOT LIKE 'course:%'
            """
        ).bindparams(course_id=uuid.UUID(AI_DRIVEN_DEV_UUID))
    )

    # LOW-4: broadcast notifications carry the target course for auditing.
    op.add_column(
        "notifications",
        sa.Column("course_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_notifications_course_id",
        "notifications",
        "courses",
        ["course_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_notifications_course_id", "notifications", ["course_id"]
    )

    # LOW-1: learners already on ai-era-se only had Phase 1 progress rows.
    for phase_no in (2, 3, 4):
        op.execute(
            sa.text(
                """
                INSERT INTO progress (id, user_id, course_id, phase, status)
                SELECT gen_random_uuid(), e.user_id, e.course_id, :phase, 'locked'
                FROM enrollments e
                WHERE e.course_id = :course_id
                  AND e.status = 'active'
                  AND NOT EXISTS (
                    SELECT 1 FROM progress p
                    WHERE p.user_id = e.user_id
                      AND p.course_id = e.course_id
                      AND p.phase = :phase
                  )
                """
            ).bindparams(
                course_id=uuid.UUID(AI_ERA_SE_UUID),
                phase=phase_no,
            )
        )


def downgrade() -> None:
    op.drop_index("ix_notifications_course_id", table_name="notifications")
    op.drop_constraint("fk_notifications_course_id", "notifications", type_="foreignkey")
    op.drop_column("notifications", "course_id")

    op.execute(
        sa.text(
            """
            UPDATE embeddings
            SET source_ref = substring(source_ref from 22)
            WHERE course_id = :course_id
              AND source_ref LIKE 'course:ai-driven-dev:phase:%'
            """
        ).bindparams(course_id=uuid.UUID(AI_DRIVEN_DEV_UUID))
    )

    op.execute(
        sa.text(
            """
            DELETE FROM progress
            WHERE course_id = :course_id AND phase IN (2, 3, 4)
            """
        ).bindparams(course_id=uuid.UUID(AI_ERA_SE_UUID))
    )
