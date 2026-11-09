"""The goal board is private and only its owner marks progress."""

from fastapi.testclient import TestClient

from hallway.main import app


def test_goals_need_a_session():
    anonymous = TestClient(app)
    assert anonymous.get("/api/goals").status_code == 401
    assert anonymous.put("/api/goals", json={"goals": []}).status_code == 401


def test_i_set_tick_and_remove_my_own_goals(person):
    ana, _ = person("Ana goalkeeper")
    assert ana.get("/api/goals").json() == {"goals": []}

    wanted = {"goals": [{"text": "  Find a collaborator  "}, {"text": "Learn about eBPF"}]}
    saved = ana.put("/api/goals", json=wanted).json()
    assert saved == {
        "goals": [
            {"text": "Find a collaborator", "done": False},
            {"text": "Learn about eBPF", "done": False},
        ]
    }

    saved["goals"][1]["done"] = True
    ana.put("/api/goals", json=saved)
    assert ana.get("/api/goals").json()["goals"][1] == {"text": "Learn about eBPF", "done": True}

    ana.put("/api/goals", json={"goals": []})
    assert ana.get("/api/goals").json() == {"goals": []}


def test_goals_are_limited_and_validated(person):
    ana, _ = person("Ana toomany")
    six = {"goals": [{"text": f"goal {n}"} for n in range(6)]}
    assert ana.put("/api/goals", json=six).status_code == 422
    assert ana.put("/api/goals", json={"goals": [{"text": "   "}]}).status_code == 422
    assert ana.put("/api/goals", json={"goals": [{"text": "x" * 121}]}).status_code == 422


def test_nobody_else_sees_my_goals_and_meeting_someone_does_not_tick_one(person):
    ana, ana_me = person("Ana private", on_graph=True)
    ben, ben_me = person("Ben curious")
    ana.put("/api/goals", json={"goals": [{"text": "zyxgoalsecret meet a maintainer"}]})

    assert ben.get("/api/goals").json() == {"goals": []}
    for response in (
        ben.get(f"/api/attendees/{ana_me['id']}"),
        ben.get("/api/graph"),
        ben.get("/api/matches"),
        ana.get("/api/me"),
    ):
        assert "zyxgoalsecret" not in response.text

    ben.post("/api/edges", json={"to_id": ana_me["id"]})  # they meet
    assert ana.get("/api/goals").json()["goals"][0]["done"] is False
