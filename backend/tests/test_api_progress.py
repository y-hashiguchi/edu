def test_list_returns_four_phases(auth_client):
    response = auth_client.get("/api/progress")
    assert response.status_code == 200

    data = response.json()
    assert [item["phase"] for item in data] == [1, 2, 3, 4]
    assert [item["status"] for item in data] == [
        "in_progress",
        "locked",
        "locked",
        "locked",
    ]


def test_list_requires_auth(client, db_session):
    response = client.get("/api/progress")
    assert response.status_code == 401


def test_complete_phase_unlocks_next(auth_client):
    response = auth_client.post("/api/progress/1/complete")
    assert response.status_code == 200

    body = response.json()
    assert body["phase"] == 1
    assert body["status"] == "completed"
    assert body["next_unlocked"] is not None
    assert body["next_unlocked"]["phase"] == 2
    assert body["next_unlocked"]["status"] == "in_progress"


def test_complete_last_phase_no_next_unlocked(auth_client):
    auth_client.post("/api/progress/1/complete")
    auth_client.post("/api/progress/2/complete")
    auth_client.post("/api/progress/3/complete")

    response = auth_client.post("/api/progress/4/complete")
    assert response.status_code == 200
    assert response.json()["next_unlocked"] is None


def test_complete_locked_phase_returns_403(auth_client):
    response = auth_client.post("/api/progress/2/complete")
    assert response.status_code == 403
    assert response.json()["detail"] == "phase 2 is locked"


def test_complete_phase_out_of_range_returns_422(auth_client):
    response = auth_client.post("/api/progress/99/complete")
    assert response.status_code == 422


def test_complete_requires_auth(client, db_session):
    response = client.post("/api/progress/1/complete")
    assert response.status_code == 401


def test_complete_is_idempotent(auth_client):
    auth_client.post("/api/progress/1/complete")
    response = auth_client.post("/api/progress/1/complete")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["next_unlocked"] is None
