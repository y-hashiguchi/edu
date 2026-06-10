"""sprint7_multi_course

Revision ID: 75b4bc4af35b
Revises: 57242832bf0f
Create Date: 2026-06-11 00:47:24.671192

Sprint 7: introduce courses + enrollments, propagate course_id to
5 dependent tables, auto-enroll all existing users into ai-driven-dev,
and rebuild affected UNIQUE constraints. Down deletes ai-era-se rows
before restoring the single-course schema."""

import uuid

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '75b4bc4af35b'
down_revision = '57242832bf0f'
branch_labels = None
depends_on = None


AI_DRIVEN_DEV_UUID = uuid.UUID("00000000-0000-4000-8000-000000000001")
AI_ERA_SE_UUID = uuid.UUID("00000000-0000-4000-8000-000000000002")


def upgrade() -> None:
    # 1. courses table
    op.create_table(
        "courses",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # 2. seed two courses with fixed UUIDs
    op.execute(
        sa.text(
            "INSERT INTO courses (id, slug, title, description, sort_order) "
            "VALUES (:id1, 'ai-driven-dev', "
            "'AI駆動型開発 補足カリキュラム', "
            "'既存 Java/Python 経験者向けの AI 駆動型開発習得カリキュラム', 0), "
            "(:id2, 'ai-era-se', "
            "'AI時代SE育成カリキュラム', "
            "'12 ヶ月のSE育成カリキュラム。Phase 1 をパイロット投入。', 1)"
        ).bindparams(id1=AI_DRIVEN_DEV_UUID, id2=AI_ERA_SE_UUID)
    )

    # 3. enrollments table
    op.create_table(
        "enrollments",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "course_id",
            sa.UUID(),
            sa.ForeignKey("courses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column(
            "enrolled_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "user_id", "course_id", name="uq_enrollments_user_course"
        ),
    )
    op.create_index("ix_enrollments_user_id", "enrollments", ["user_id"])
    op.create_index("ix_enrollments_course_id", "enrollments", ["course_id"])

    # 4. add course_id to 5 tables as NULLABLE first
    for table in ("progress", "submissions", "chat_history", "embeddings", "user_nudges"):
        op.add_column(
            table,
            sa.Column(
                "course_id",
                sa.UUID(),
                sa.ForeignKey("courses.id", ondelete="RESTRICT"),
                nullable=True,
            ),
        )

    # 5. backfill existing rows to ai-driven-dev
    for table in ("progress", "submissions", "chat_history", "embeddings", "user_nudges"):
        op.execute(
            sa.text(f"UPDATE {table} SET course_id = :cid WHERE course_id IS NULL")
            .bindparams(cid=AI_DRIVEN_DEV_UUID)
        )

    # 6. auto-enroll all existing users into ai-driven-dev
    op.execute(
        sa.text(
            "INSERT INTO enrollments (id, user_id, course_id, status) "
            "SELECT gen_random_uuid(), id, :cid, 'active' FROM users "
            "ON CONFLICT (user_id, course_id) DO NOTHING"
        ).bindparams(cid=AI_DRIVEN_DEV_UUID)
    )

    # 7. NOT NULL + indexes
    for table in ("progress", "submissions", "chat_history", "embeddings", "user_nudges"):
        op.alter_column(table, "course_id", nullable=False)
        op.create_index(f"ix_{table}_course_id", table, ["course_id"])

    # 8. submissions: drop task_no CHECK, rebuild UNIQUE
    op.drop_constraint("ck_submissions_task_no", "submissions", type_="check")
    op.drop_constraint(
        "uq_submissions_user_phase_task", "submissions", type_="unique"
    )
    op.create_unique_constraint(
        "uq_submissions_user_course_phase_task",
        "submissions",
        ["user_id", "course_id", "phase", "task_no"],
    )

    # 9. progress UNIQUE rebuild
    op.drop_constraint("uq_progress_user_phase", "progress", type_="unique")
    op.create_unique_constraint(
        "uq_progress_user_course_phase",
        "progress",
        ["user_id", "course_id", "phase"],
    )

    # 10. user_nudges PK rebuild (single -> composite)
    op.execute("ALTER TABLE user_nudges DROP CONSTRAINT user_nudges_pkey")
    op.create_primary_key(
        "user_nudges_pkey", "user_nudges", ["user_id", "course_id"]
    )

    # 11. chat_history index rebuild
    op.drop_index("ix_chat_history_user_phase_created", table_name="chat_history")
    op.create_index(
        "ix_chat_history_user_course_phase_created",
        "chat_history",
        ["user_id", "course_id", "phase", "created_at"],
    )

    # 12. embeddings index rebuild (HNSW stays as-is)
    op.drop_index("ix_embeddings_user_phase", table_name="embeddings")
    op.create_index(
        "ix_embeddings_course_user_phase",
        "embeddings",
        ["course_id", "user_id", "phase"],
    )


def downgrade() -> None:
    # Drop ai-era-se rows so the single-course CHECK restoration succeeds.
    # ai-era-se has up to 8 tasks; restoring task_no <= 5 would fail
    # on any task_no > 5 row.
    for table in ("progress", "submissions", "chat_history", "embeddings", "user_nudges"):
        op.execute(
            sa.text(f"DELETE FROM {table} WHERE course_id = :cid")
            .bindparams(cid=AI_ERA_SE_UUID)
        )

    op.drop_index("ix_embeddings_course_user_phase", table_name="embeddings")
    op.create_index("ix_embeddings_user_phase", "embeddings", ["user_id", "phase"])

    op.drop_index("ix_chat_history_user_course_phase_created", table_name="chat_history")
    op.create_index(
        "ix_chat_history_user_phase_created",
        "chat_history",
        ["user_id", "phase", "created_at"],
    )

    op.execute("ALTER TABLE user_nudges DROP CONSTRAINT user_nudges_pkey")
    op.create_primary_key("user_nudges_pkey", "user_nudges", ["user_id"])

    op.drop_constraint("uq_progress_user_course_phase", "progress", type_="unique")
    op.create_unique_constraint(
        "uq_progress_user_phase", "progress", ["user_id", "phase"]
    )

    op.drop_constraint(
        "uq_submissions_user_course_phase_task", "submissions", type_="unique"
    )
    op.create_unique_constraint(
        "uq_submissions_user_phase_task",
        "submissions",
        ["user_id", "phase", "task_no"],
    )
    op.create_check_constraint(
        "ck_submissions_task_no", "submissions", "task_no BETWEEN 1 AND 5"
    )

    for table in ("user_nudges", "embeddings", "chat_history", "submissions", "progress"):
        op.drop_index(f"ix_{table}_course_id", table_name=table)
        op.drop_column(table, "course_id")

    op.drop_index("ix_enrollments_course_id", table_name="enrollments")
    op.drop_index("ix_enrollments_user_id", table_name="enrollments")
    op.drop_table("enrollments")

    op.drop_table("courses")
