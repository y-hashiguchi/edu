def test_list_phases_requires_auth(client, db_session):
    response = client.get("/api/curriculum/phases")
    assert response.status_code == 401


def test_list_phases_returns_four_with_locked_flags(auth_client):
    response = auth_client.get("/api/curriculum/phases")
    assert response.status_code == 200

    data = response.json()
    assert [item["phase"] for item in data] == [1, 2, 3, 4]
    assert [item["locked"] for item in data] == [False, True, True, True]
    assert data[0]["status"] == "in_progress"
    assert data[1]["status"] == "locked"


def test_list_phases_returns_titles_and_tasks(auth_client):
    data = auth_client.get("/api/curriculum/phases").json()
    phase1 = data[0]
    assert phase1["title"] == "開発環境の近代化"
    assert len(phase1["tasks"]) >= 3
    assert "Git" in " ".join(phase1["skills"])


def test_list_phases_reflects_completion(auth_client):
    auth_client.post("/api/progress/1/complete")

    response = auth_client.get("/api/curriculum/phases")
    data = response.json()
    assert data[0]["status"] == "completed"
    assert data[0]["locked"] is False
    assert data[1]["status"] == "in_progress"
    assert data[1]["locked"] is False
