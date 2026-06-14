"""Sprint 10 — admin cohort summary HTTP API tests."""

import pytest


@pytest.mark.asyncio
async def test_cohort_summary_requires_admin(
    client, auth_user, auth_token, seed_curriculum,
):
    client.headers.update({"Authorization": f"Bearer {auth_token}"})
    res = client.get("/api/admin/courses/ai-driven-dev/cohort-summary")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_cohort_summary_returns_metrics(
    client, admin_user, admin_token, auth_user, seed_curriculum,
):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    res = client.get("/api/admin/courses/ai-driven-dev/cohort-summary")
    assert res.status_code == 200
    body = res.json()
    assert body["course_slug"] == "ai-driven-dev"
    assert body["enrolled_count"] >= 1
    assert "completion_rate" in body
    assert isinstance(body["stuck_learners"], list)
    assert isinstance(body["tag_heatmap"], list)


@pytest.mark.asyncio
async def test_cohort_summary_unknown_slug_404(
    client, admin_user, admin_token, seed_curriculum,
):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    res = client.get("/api/admin/courses/no-such-course/cohort-summary")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_cohort_summary_invalid_slug_pattern_422(
    client, admin_user, admin_token, seed_curriculum,
):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    res = client.get("/api/admin/courses/BAD%20SLUG/cohort-summary")
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_cohort_summary_includes_enrolled_auth_user(
    client, admin_user, admin_token, auth_user, seed_curriculum,
):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    res = client.get("/api/admin/courses/ai-driven-dev/cohort-summary")
    assert res.status_code == 200
    assert res.json()["enrolled_count"] >= 2


@pytest.mark.asyncio
async def test_cohort_export_requires_admin(
    client, auth_user, auth_token, seed_curriculum,
):
    client.headers.update({"Authorization": f"Bearer {auth_token}"})
    res = client.get("/api/admin/courses/ai-driven-dev/cohort-summary/export")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_cohort_export_returns_csv(
    client, admin_user, admin_token, auth_user, seed_curriculum,
):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    res = client.get("/api/admin/courses/ai-driven-dev/cohort-summary/export")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    assert 'attachment; filename="cohort-ai-driven-dev.csv"' in res.headers[
        "content-disposition"
    ]
    body = res.text
    assert "course_slug,course_title,enrolled_count" in body
    assert "ai-driven-dev" in body
    assert "user_id,display_name,email_masked" in body
    assert "tag,average_score,submission_count" in body


@pytest.mark.asyncio
async def test_cohort_export_unknown_slug_404(
    client, admin_user, admin_token, seed_curriculum,
):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    res = client.get("/api/admin/courses/no-such-course/cohort-summary/export")
    assert res.status_code == 404
