"""The organizer board returns counts only. Other tests share the indices, so these
tests compare before and after instead of expecting absolute numbers."""

from hallway import crowd, es

KEYS = {
    "registered", "in_groups", "groups", "groups_with_meeting", "invitations",
    "plans", "meetings", "checked_in", "topics", "comfort",
}


def test_board_is_public_and_holds_only_counts(person):
    from fastapi.testclient import TestClient

    from hallway.main import app

    ana, ana_me = person("Ana Crowdsecret", asks="glimmerwort", tags=["glimmerwort"])
    anonymous = TestClient(app)
    response = anonymous.get("/api/crowd")
    assert response.status_code == 200
    board = response.json()
    assert set(board) == KEYS
    assert all(set(t) == {"topic", "asking", "offering"} for t in board["topics"])
    assert all(set(c) == {"key", "count"} for c in board["comfort"])
    # No person can be found in it: not a name, not an id.
    assert "Crowdsecret" not in response.text
    assert ana_me["id"] not in response.text


def test_counts_follow_what_people_do(person):
    client = es.get_client()
    before = crowd.board(client)

    ana, ana_me = person("Ana tallybright", asks="tallybright", working_on="tallybright")
    ben, ben_me = person("Ben tallybright", offers="tallybright", working_on="tallybright")
    ana.post("/api/crew/suggest")
    ana.post("/api/crew/accept", json={})
    ana.put(
        "/api/crew/meeting",
        json={
            "place": "Front desk",
            "starts_at": "2026-11-10T08:30:00-07:00",
            "timezone": "America/Denver",
        },
    )
    ana.post("/api/invitations", json={"to_id": ben_me["id"]})
    ben.post(f"/api/invitations/{ana_me['id']}/accept")
    ben.post("/api/checkins", json={"room": "Main Stage"})

    after = crowd.board(client)
    assert after["registered"] == before["registered"] + 2
    assert after["in_groups"] == before["in_groups"] + 1
    assert after["groups"] == before["groups"] + 1
    assert after["groups_with_meeting"] == before["groups_with_meeting"] + 1
    assert after["plans"] == before["plans"] + 1
    assert after["checked_in"] == before["checked_in"] + 1

    ana.post("/api/edges", json={"to_id": ben_me["id"]})  # they meet
    met = crowd.board(client)
    assert met["meetings"] == before["meetings"] + 1


def test_topics_count_asks_against_offers_widest_gap_first(person):
    for number in range(4):
        person(f"Asker {number}", asks="help with quorblesnatch please", tags=["quorblesnatch"])
    person("Offerer", offers="I know quorblesnatch", tags=["quorblesnatch"])
    for number in range(3):
        person(f"Giver {number}", offers="deep vintrellic knowledge", tags=["vintrellic"])

    topics = crowd._topics(es.get_client(), ["vintrellic", "quorblesnatch"])
    assert topics == [
        {"topic": "quorblesnatch", "asking": 4, "offering": 1},  # four want it, one has it
        {"topic": "vintrellic", "asking": 0, "offering": 3},
    ]


def test_a_topic_about_fewer_than_three_people_is_left_out(person):
    person("Only one", asks="wimblethorn", tags=["wimblethorn"])
    person("Only two", offers="wimblethorn", tags=["wimblethorn"])
    assert crowd._topics(es.get_client(), ["wimblethorn"]) == []
