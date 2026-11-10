"""Group messages (working plan: group chat before/after the event).

Members of a community can read and send its messages; a non-member gets 403
and never sees a message, and the author's id is never returned. The first
test fakes the store so it runs without Elasticsearch; the rest are
integration tests against real Elasticsearch (skipped when it is unreachable).
"""

from elasticsearch import NotFoundError
from fastapi.testclient import TestClient

from hallway import es
from hallway.auth import current_attendee
from hallway.main import app

LUMA = "https://luma.com/event"
PATH = "/api/communities/{id}/messages"


class Store:
    """Minimal fake Elasticsearch: one community, plus the messages index."""

    def __init__(self) -> None:
        self.community = {
            "id": "community-1",
            "name": "Founders",
            "description": "Meet together",
            "luma_url": LUMA,
            "owner_id": "owner-1",
            "members": ["member-1"],
            "created_at": "2026-11-09T00:00:00+00:00",
        }
        self.messages: dict[str, dict] = {}

    def get(self, *, index, id):
        if index == es.COMMUNITIES and id == self.community["id"]:
            return {"_source": self.community, "_seq_no": 0, "_primary_term": 1}
        raise NotFoundError(404, "not found", {})

    def index(self, *, index, id, document, refresh):
        self.messages[id] = document

    def search(self, *, index, query, size, sort):
        community_id = query["term"]["community_id"]
        found = [m for m in self.messages.values() if m["community_id"] == community_id]
        found.sort(
            key=lambda m: (m["created_at"], m["id"]),
            reverse=sort[0]["created_at"] == "desc",
        )
        return {"hits": {"hits": [{"_source": m} for m in found[:size]]}}


def test_members_only_and_author_id_never_returned(monkeypatch):
    store = Store()
    monkeypatch.setattr(es, "get_client", lambda: store)
    client = TestClient(app)
    path = PATH.format(id="community-1")
    member = {"id": "member-1", "name": "Mia Member"}
    outsider = {"id": "outsider-1", "name": "Ollie Outsider"}

    # No session at all: 401, from the auth dependency.
    assert client.get(path).status_code == 401

    app.dependency_overrides[current_attendee] = lambda: outsider
    try:
        assert client.get(path).status_code == 403
        assert client.post(path, json={"text": "hello"}).status_code == 403
    finally:
        app.dependency_overrides.clear()

    app.dependency_overrides[current_attendee] = lambda: member
    try:
        assert client.get("/api/communities/nope/messages").status_code == 404
        assert client.post(path, json={"text": "   "}).status_code == 422
        assert client.post(path, json={"text": "x" * 1001}).status_code == 422
        sent = client.post(path, json={"text": "See you at the keynote"})
        assert sent.status_code == 201, sent.text
        timestamp = sent.json()["created_at"]
        assert len(timestamp.split(".")[1].split("+")[0]) == 3
        assert sent.json() == {
            "id": sent.json()["id"],
            "author_name": "Mia Member",
            "text": "See you at the keynote",
            "created_at": sent.json()["created_at"],
        }
        listed = client.get(path)
        assert listed.status_code == 200
        assert listed.json() == [sent.json()]
    finally:
        app.dependency_overrides.clear()


def test_limit_returns_latest_messages_oldest_first(monkeypatch):
    store = Store()
    store.messages = {
        str(number): {
            "id": str(number),
            "community_id": "community-1",
            "author_name": "Mia Member",
            "text": f"Message {number}",
            "created_at": f"2026-11-09T00:00:0{number}.000+00:00",
        }
        for number in range(1, 5)
    }
    monkeypatch.setattr(es, "get_client", lambda: store)
    app.dependency_overrides[current_attendee] = lambda: {
        "id": "member-1",
        "name": "Mia Member",
    }
    try:
        path = PATH.format(id="community-1")
        listed = TestClient(app).get(f"{path}?limit=2")
        assert listed.status_code == 200, listed.text
        assert [message["text"] for message in listed.json()] == [
            "Message 3",
            "Message 4",
        ]
    finally:
        app.dependency_overrides.clear()


def _create_and_join(organizer, member, name: str = "Founders") -> str:
    body = {"name": name, "description": "Meet together", "luma_url": LUMA}
    created = organizer.post("/api/communities", json=body)
    assert created.status_code == 201, created.text
    community_id = created.json()["id"]
    joined = member.post(f"/api/communities/{community_id}/members")
    assert joined.status_code == 200, joined.text
    return community_id


def test_member_posts_and_reads_back_in_order(person):
    organizer, _ = person("Olu Organizer")
    member, _ = person("Mia Member")
    community_id = _create_and_join(organizer, member)
    path = PATH.format(id=community_id)

    first = member.post(path, json={"text": "First, coffee?"})
    assert first.status_code == 201, first.text
    assert first.json()["author_name"] == "Mia Member"
    assert "author_id" not in first.json()

    second = organizer.post(path, json={"text": "Coffee, yes"})
    # The organizer created the community but is not a member until they join.
    assert second.status_code == 403
    joined = organizer.post(f"/api/communities/{community_id}/members")
    assert joined.status_code == 200
    second = organizer.post(path, json={"text": "Coffee, yes"})
    assert second.status_code == 201, second.text

    listed = member.get(path)
    assert listed.status_code == 200
    assert [m["text"] for m in listed.json()] == ["First, coffee?", "Coffee, yes"]
    assert [m["author_name"] for m in listed.json()] == ["Mia Member", "Olu Organizer"]


def test_non_member_cannot_read_or_send(person):
    organizer, _ = person("Olu Organizer")
    member, _ = person("Mia Member")
    outsider, _ = person("Ollie Outsider")
    community_id = _create_and_join(organizer, member)
    path = PATH.format(id=community_id)

    assert outsider.get(path).status_code == 403
    assert outsider.post(path, json={"text": "hello"}).status_code == 403
    assert member.get("/api/communities/nope/messages").status_code == 404
