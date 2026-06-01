def test_list_phases_returns_four_phases(client):
    response = client.get("/api/curriculum/phases")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 4
    phase_numbers = [item["phase"] for item in data]
    assert phase_numbers == [1, 2, 3, 4]


def test_list_phases_includes_titles_and_tasks(client):
    response = client.get("/api/curriculum/phases")
    phase1 = response.json()[0]

    assert phase1["title"] == "開発環境の近代化"
    assert len(phase1["tasks"]) >= 3
    assert "Git" in " ".join(phase1["skills"])
