"""Sprint 12 — cohort CSV export unit tests."""

from datetime import UTC, datetime
from uuid import UUID

from app.services.cohort_csv import render_cohort_csv
from app.services.cohort_summary import CohortSummary, StuckLearner, TagHeatmapEntry


def test_render_cohort_csv_includes_all_sections():
    uid = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    summary = CohortSummary(
        course_slug="ai-driven-dev",
        course_title="AI Driven Dev",
        enrolled_count=3,
        average_score=72.5,
        completion_rate=0.4,
        stuck_learners=[
            StuckLearner(
                user_id=uid,
                display_name="Learner One",
                email_masked="l***@example.com",
                last_activity_at=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
                current_phase=2,
                submission_count=1,
                reason="inactive_7d",
            )
        ],
        tag_heatmap=[
            TagHeatmapEntry(
                tag="python",
                average_score=80.0,
                submission_count=5,
            )
        ],
    )

    csv_text = render_cohort_csv(summary)

    assert "ai-driven-dev,AI Driven Dev,,3,72.5,0.4" in csv_text
    assert "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" in csv_text
    assert "Learner One,l***@example.com" in csv_text
    assert "python,80.0,5" in csv_text
