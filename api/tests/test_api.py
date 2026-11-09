"""End-to-end through the real API and a real Elasticsearch."""

from fastapi.testclient import TestClient

from hallway.auth import COOKIE
from hallway.main import app


def test_community_invitation_is_public_but_creation_requires_session(person):
    anonymous = TestClient(app)
    data = {
        "name": "Community", "description": "Meet together", "luma_url": "https://luma.com/event"
    }
    assert anonymous.post("/api/communities", json=data).status_code == 401
    client, _ = person("Organizer")
    created = client.post("/api/communities", json=data)
    assert created.status_code == 201
    invitation = anonymous.get(f"/api/communities/{created.json()['id']}")
    assert invitation.status_code == 200
    assert invitation.json() == {
        "id": created.json()["id"], **data,
        "member_count": 0, "is_member": False, "is_organizer": False,
    }  # fmt: skip
    assert anonymous.get("/api/communities/missing").status_code == 404
    for url in ("javascript:alert(1)", "https://luma.com.example.com/event", "http://luma.com/event"):
        assert client.post("/api/communities", json=data | {"luma_url": url}).status_code == 422


def test_register_then_me_and_secrets_stay_private(person):
    client, me = person("Ada Example", tags=[" Go ", "go", "K8s"])
    assert me["tags"] == ["go", "k8s"]
    assert len(me["recovery_code"]) == 6
    assert "secret" not in me
    assert client.get("/api/me").json()["id"] == me["id"]
    public = client.get(f"/api/attendees/{me['id']}").json()
    assert "recovery_code" not in public and "secret" not in public


def test_knowing_a_public_id_is_not_enough_to_be_that_person(person):
    _, victim = person("Vic Tim")
    attacker = TestClient(app)
    assert attacker.get("/api/me").status_code == 401
    attacker.cookies.set(COOKIE, f"{victim['id']}.guessed-secret")
    assert attacker.get("/api/me").status_code == 401


def test_recovery_code_restores_the_session(person):
    _, me = person("Lost Phone")
    fresh = TestClient(app)
    assert fresh.post("/api/recover", json={"code": "ZZZZZZ"}).status_code == 404
    assert fresh.post("/api/recover", json={"code": me["recovery_code"].lower()}).status_code == 200
    assert fresh.get("/api/me").json()["id"] == me["id"]


def test_asks_are_matched_against_other_peoples_offers(person):
    asker, _ = person("Needs Help", asks="postgres replication lag debugging", working_on="billing")
    _, helper = person("Can Help", offers="debugging postgres replication", working_on="databases")
    person("Unrelated", offers="watercolor painting tips", working_on="illustration")
    matches = asker.get("/api/matches").json()
    assert 1 <= len(matches) <= 5
    assert matches[0]["attendee"]["id"] == helper["id"]
    assert matches[0]["reason"].startswith("They offer what you asked for")
    assert matches[0]["icebreaker"]


def test_matches_never_include_me_or_people_i_already_met(person):
    me_client, me = person("Solo", asks="rust async", working_on="rust services")
    other_client, other = person("Rusty", offers="rust async", working_on="rust services")
    ids = [m["attendee"]["id"] for m in me_client.get("/api/matches").json()]
    assert me["id"] not in ids and other["id"] in ids
    me_client.post("/api/edges", json={"to_id": other["id"]})
    ids = [m["attendee"]["id"] for m in me_client.get("/api/matches").json()]
    assert other["id"] not in ids


def test_connecting_rules(person):
    a_client, a = person("Scanner")
    b_client, b = person("Scanned")
    assert a_client.post("/api/edges", json={"to_id": a["id"]}).status_code == 400
    assert a_client.post("/api/edges", json={"to_id": "nobody"}).status_code == 404
    assert TestClient(app).post("/api/edges", json={"to_id": b["id"]}).status_code == 401
    first = a_client.post("/api/edges", json={"to_id": b["id"]}).json()
    assert first["created"] is True and first["other"]["name"] == "Scanned"
    # Review focus 2: the same pair again, from either side, is not a second edge.
    assert b_client.post("/api/edges", json={"to_id": a["id"]}).json()["created"] is False


def test_graph_path_and_recap(person):
    a_client, a = person("Path A", groups=["Students"])
    b_client, b = person("Path B", groups=["SRE"])
    c_client, c = person("Path C", groups=["Security"])
    hidden_client, hidden = person("Off Graph", on_graph=False)
    a_client.post("/api/edges", json={"to_id": b["id"]})
    b_client.post("/api/edges", json={"to_id": c["id"]})
    hidden_client.post("/api/edges", json={"to_id": a["id"]})

    graph = a_client.get("/api/graph").json()
    node_ids = {n["id"] for n in graph["nodes"]}
    assert {a["id"], b["id"], c["id"]} <= node_ids and hidden["id"] not in node_ids
    assert all(
        link["source"] != hidden["id"] and link["target"] != hidden["id"] for link in graph["links"]
    )
    assert "degree" not in graph["nodes"][0]  # no public popularity score

    path = a_client.get(f"/api/graph/path?to={c['id']}").json()["path"]
    assert [step["name"] for step in path] == ["Path A", "Path B", "Path C"]

    recap = b_client.get("/api/recap").json()
    assert {p["name"] for p in recap["connections"]} == {"Path A", "Path C"}
    assert recap["groups_bridged"] == 2 and len(recap["nudges"]) == 2


def test_rooms_and_checkins(person):
    client, me = person("Roomie")
    # Review focus 4: unknown rooms are rejected.
    assert client.post("/api/checkins", json={"room": "Narnia"}).status_code == 400
    before = {r["room"]: r["count"] for r in client.get("/api/rooms").json()}
    assert "Coffee Bar" in before
    assert (
        client.post("/api/checkins", json={"room": "Coffee Bar"}).json()["count"]
        == before["Coffee Bar"] + 1
    )
    client.post("/api/checkins", json={"room": "Quiet Room"})  # moving, not cloning
    after = {r["room"]: r["count"] for r in client.get("/api/rooms").json()}
    assert after["Coffee Bar"] == before["Coffee Bar"]
    assert after["Quiet Room"] == before["Quiet Room"] + 1


def test_registering_draws_suggested_edges_and_connecting_replaces_them(person):
    a_client, a = person("Agent A", asks="grafana dashboards", working_on="observability")
    b_client, b = person("Agent B", offers="grafana dashboards", working_on="observability")
    # B registered second, so the background matcher ran for B and suggested A.
    links = [
        link
        for link in a_client.get("/api/graph").json()["links"]
        if {link["source"], link["target"]} == {a["id"], b["id"]}
    ]
    assert [link["kind"] for link in links] == ["suggested"]
    a_client.post("/api/edges", json={"to_id": b["id"]})
    links = [
        link
        for link in a_client.get("/api/graph").json()["links"]
        if {link["source"], link["target"]} == {a["id"], b["id"]}
    ]
    assert [link["kind"] for link in links] == ["connected"]


def test_chaos_needs_the_admin_token(person):
    client, _ = person("Chaos Monkey", asks="anything")
    assert client.post("/api/chaos", json={"mode": "error"}).status_code == 403
    headers = {"X-Admin-Token": "test-admin"}
    assert client.post("/api/chaos", json={"mode": "error"}, headers=headers).json() == {
        "mode": "error"
    }
    assert client.get("/api/matches").status_code == 503
    client.post("/api/chaos", json={"mode": "off"}, headers=headers)
    assert client.get("/api/matches").status_code == 200


def test_validation(person):
    assert (
        TestClient(app).post("/api/attendees", json={"name": "", "working_on": "x"}).status_code
        == 422
    )
