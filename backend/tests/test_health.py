def test_healthz_returns_ok(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version_returns_unknown_without_render_env(client):
    # Locally / in CI the Render-injected vars are absent, so the endpoint must
    # degrade gracefully rather than 500.
    response = client.get("/version")
    assert response.status_code == 200
    body = response.json()
    assert body["commit"] == "unknown"
    assert body["branch"] == "unknown"


def test_version_reports_render_commit(client, monkeypatch):
    # Render injects RENDER_GIT_COMMIT / RENDER_GIT_BRANCH per deploy; /version
    # surfaces them so the live revision is verifiable from outside.
    #
    # Patch the settings object the route actually holds. Other tests reload
    # app.config (importlib.reload in the file-storage suites), which rebinds
    # app.config.settings to a fresh object while the already-imported route
    # keeps its original reference. Patching app.api.health.settings targets
    # the exact object the endpoint reads, independent of test ordering.
    from app.api import health

    monkeypatch.setattr(health.settings, "render_git_commit", "a13c8cb")
    monkeypatch.setattr(health.settings, "render_git_branch", "main")

    response = client.get("/version")
    assert response.status_code == 200
    assert response.json() == {"commit": "a13c8cb", "branch": "main"}
