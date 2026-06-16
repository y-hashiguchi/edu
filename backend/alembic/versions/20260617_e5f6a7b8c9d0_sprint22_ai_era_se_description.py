"""Sprint 22 — sync ai-era-se course catalog description with full syllabus."""

from alembic import op

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None

_NEW_DESCRIPTION = (
    "12 ヶ月のSE育成カリキュラム（4 フェーズ・31 課題）。"
    "MFRS / Nichinichi Anshin / IES を題材にする。"
)
_OLD_DESCRIPTION = "12 ヶ月のSE育成カリキュラム。Phase 1 をパイロット投入。"


def upgrade() -> None:
    op.execute(
        f"UPDATE courses SET description = '{_NEW_DESCRIPTION}' "
        "WHERE slug = 'ai-era-se'"
    )


def downgrade() -> None:
    op.execute(
        f"UPDATE courses SET description = '{_OLD_DESCRIPTION}' "
        "WHERE slug = 'ai-era-se'"
    )
