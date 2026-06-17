"""Sprint 12 — CSV export for admin cohort summary."""

from __future__ import annotations

import csv
import io

from app.services.cohort_summary import CohortSummary


def render_cohort_csv(summary: CohortSummary) -> str:
    """Render cohort summary as a multi-section CSV string."""
    buf = io.StringIO()
    writer = csv.writer(buf)

    writer.writerow(
        [
            "course_slug",
            "course_title",
            "cohort_label",
            "enrolled_count",
            "average_score",
            "completion_rate",
        ]
    )
    writer.writerow(
        [
            summary.course_slug,
            summary.course_title,
            summary.cohort_label or "",
            summary.enrolled_count,
            summary.average_score if summary.average_score is not None else "",
            summary.completion_rate,
        ]
    )
    writer.writerow([])

    writer.writerow(
        [
            "user_id",
            "display_name",
            "email_masked",
            "last_activity_at",
            "current_phase",
            "submission_count",
            "reason",
        ]
    )
    for learner in summary.stuck_learners:
        writer.writerow(
            [
                str(learner.user_id),
                learner.display_name,
                learner.email_masked,
                learner.last_activity_at.isoformat() if learner.last_activity_at else "",
                learner.current_phase,
                learner.submission_count,
                learner.reason,
            ]
        )
    writer.writerow([])

    writer.writerow(["tag", "average_score", "submission_count"])
    for entry in summary.tag_heatmap:
        writer.writerow([entry.tag, entry.average_score, entry.submission_count])

    return buf.getvalue()
