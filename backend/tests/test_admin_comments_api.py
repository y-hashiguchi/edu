"""Sprint 4 instructor comments API tests.

Covers the admin-write path, the learner-read path on their own
submissions, and the BOLA boundaries between them. The single-source-of-
truth fact under test: a comment row is admin-authored and learner-read,
never the other way around.
"""

from datetime import UTC, datetime

import pytest

from app.core.security import create_access_token, hash_password


def _auth(client, user_id) -> None:
    client.headers.update(
        {"Authorization": f"Bearer {create_access_token(subject=str(user_id))}"}
    )


async def _seed_learner_with_sub(db_session, *, email="learner@e.com"):
    from app.models.submission import Submission
    from app.models.user import User
    from app.services.progress import initialize_progress

    learner = User(email=email, name="L", password_hash=hash_password("p"))
    db_session.add(learner)
    await db_session.flush()
    await initialize_progress(db_session, learner.id)

    sub = Submission(
        user_id=learner.id, phase=1, task_no=1,
        content="essay", submitted_at=datetime.now(UTC),
    )
    db_session.add(sub)
    await db_session.commit()
    await db_session.refresh(sub)
    return learner, sub


@pytest.mark.asyncio
async def test_admin_posts_comment_and_learner_reads(
    client, db_session, admin_user,
):
    learner, sub = await _seed_learner_with_sub(db_session)

    _auth(client, admin_user.id)
    r = client.post(
        f"/api/admin/submissions/{sub.id}/comments",
        json={"body": "phase 2 をもう少し具体的に書くと良いです。"},
    )
    assert r.status_code == 201, r.text
    posted = r.json()
    assert posted["body"].startswith("phase 2")
    assert posted["author_name"] == "講師"
    assert posted["submission_id"] == str(sub.id)

    # Admin sees their own comment via the same endpoint.
    r = client.get(f"/api/admin/submissions/{sub.id}/comments")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["author_name"] == "講師"

    # Learner sees their comment via /api/me/...; no instructor PII besides name.
    _auth(client, learner.id)
    r = client.get(f"/api/me/submissions/{sub.id}/comments")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["author_name"] == "講師"
    # The learner-facing DTO must not leak the author's user_id.
    assert "author_user_id" not in items[0]


@pytest.mark.asyncio
async def test_admin_comment_requires_admin(client, db_session, admin_user):
    """Logged-in learners cannot post comments on anything — not their
    own submissions, not someone else's. Only admins author comments."""
    learner, sub = await _seed_learner_with_sub(db_session)

    _auth(client, learner.id)
    r = client.post(
        f"/api/admin/submissions/{sub.id}/comments",
        json={"body": "self comment"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_comment_404_for_unknown_submission(
    client, db_session, admin_user,
):
    import uuid as uuid_mod

    _auth(client, admin_user.id)
    r = client.post(
        f"/api/admin/submissions/{uuid_mod.uuid4()}/comments",
        json={"body": "x"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_admin_list_comments_404_for_unknown_submission(
    client, db_session, admin_user,
):
    """MED-3 (sprint-4 security follow-up): GET admin comments must
    return 404 for an unknown UUID — the same shape as the POST path
    and as `/api/admin/submissions/{id}` detail. Returning `[]` here
    is technically harmless (admins see everything) but creates a
    response-status inconsistency that bites refactors and confuses
    front-end error handling."""
    import uuid as uuid_mod

    _auth(client, admin_user.id)
    r = client.get(f"/api/admin/submissions/{uuid_mod.uuid4()}/comments")
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_admin_comment_rejects_empty_or_oversized_body(
    client, db_session, admin_user,
):
    """Body must be 1..2000 chars: empty string is meaningless feedback,
    huge bodies are a UI/storage abuse path."""
    learner, sub = await _seed_learner_with_sub(db_session)

    _auth(client, admin_user.id)
    assert client.post(
        f"/api/admin/submissions/{sub.id}/comments",
        json={"body": ""},
    ).status_code == 422
    assert client.post(
        f"/api/admin/submissions/{sub.id}/comments",
        json={"body": "x" * 2001},
    ).status_code == 422


@pytest.mark.asyncio
async def test_intruder_cannot_read_others_comments(
    client, db_session, admin_user,
):
    """BOLA boundary: a different learner with a valid token cannot pull
    someone else's comment thread by guessing the submission UUID."""
    from app.models.user import User
    from app.services.progress import initialize_progress

    owner, sub = await _seed_learner_with_sub(db_session, email="own@e.com")
    intruder = User(email="int@e.com", name="i", password_hash=hash_password("p"))
    db_session.add(intruder)
    await db_session.flush()
    await initialize_progress(db_session, intruder.id)
    await db_session.commit()

    # Admin authors a comment so there's something to attempt to steal.
    _auth(client, admin_user.id)
    client.post(
        f"/api/admin/submissions/{sub.id}/comments",
        json={"body": "private feedback"},
    )

    _auth(client, intruder.id)
    r = client.get(f"/api/me/submissions/{sub.id}/comments")
    # Always 404 (not 403) — never confirm the submission exists to a
    # non-owner.
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_learner_read_returns_empty_when_no_comments(
    client, db_session,
):
    learner, sub = await _seed_learner_with_sub(db_session)
    _auth(client, learner.id)
    r = client.get(f"/api/me/submissions/{sub.id}/comments")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_admin_comment_rate_limited_at_high_rate(
    client, db_session, admin_user, monkeypatch,
):
    """Burst posts past admin_write_rate_limit return 429.

    Cap dropped to 5/minute here so 7 rapid POSTs guarantee we cross the
    threshold regardless of what the production default ends up being —
    coupling the test to "60/minute" would force tests to make 61
    requests, which the in-process MemoryStorage can still buffer but
    would slow the suite for no signal."""
    from app.config import settings
    from app.core.limiter import limiter

    _learner, sub = await _seed_learner_with_sub(db_session)
    monkeypatch.setattr(settings, "admin_write_rate_limit", "5/minute")
    monkeypatch.setattr(limiter, "enabled", True)
    try:
        limiter._storage.reset()
    except Exception:  # pragma: no cover - non-memory storage backend
        pass

    _auth(client, admin_user.id)
    statuses = [
        client.post(
            f"/api/admin/submissions/{sub.id}/comments",
            json={"body": f"burst {i}"},
        ).status_code
        for i in range(7)
    ]
    assert 429 in statuses, statuses


@pytest.mark.asyncio
async def test_unauthenticated_request_returns_401(client, db_session):
    """No token on either side returns 401 from the auth layer, never 403
    or 404 — fixed reading on logs and proxies."""
    _, sub = await _seed_learner_with_sub(db_session)
    r1 = client.get(f"/api/admin/submissions/{sub.id}/comments")
    r2 = client.get(f"/api/me/submissions/{sub.id}/comments")
    assert r1.status_code == 401
    assert r2.status_code == 401


@pytest.mark.asyncio
async def test_admin_can_post_reply_to_existing_trunk(client, db_session, admin_user):
    """Admin が trunk または既存 reply に対して返信できる。parent_id を渡せる (Sprint 6)."""
    learner, sub = await _seed_learner_with_sub(db_session)

    _auth(client, admin_user.id)
    r1 = client.post(
        f"/api/admin/submissions/{sub.id}/comments",
        json={"body": "trunk"},
    )
    assert r1.status_code == 201, r1.text
    trunk_id = r1.json()["id"]
    assert r1.json()["parent_id"] is None

    r2 = client.post(
        f"/api/admin/submissions/{sub.id}/comments",
        json={"body": "follow-up", "parent_id": trunk_id},
    )
    assert r2.status_code == 201, r2.text
    assert r2.json()["parent_id"] == trunk_id


@pytest.mark.asyncio
async def test_admin_comment_list_returns_parent_id_field(
    client, db_session, admin_user,
):
    learner, sub = await _seed_learner_with_sub(db_session)

    _auth(client, admin_user.id)
    client.post(
        f"/api/admin/submissions/{sub.id}/comments",
        json={"body": "trunk"},
    )
    r = client.get(f"/api/admin/submissions/{sub.id}/comments")
    assert r.status_code == 200
    items = r.json()
    assert len(items) >= 1
    assert "parent_id" in items[0]
    assert items[0]["parent_id"] is None
