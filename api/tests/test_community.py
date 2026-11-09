"""Communities (working plan step 2): a public invitation, joining by your own choice,
several affiliations, and editing only by the organizer. Real Elasticsearch, except the
first test, which fakes the store."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, get_ident

from fastapi.testclient import TestClient

from hallway import es
from hallway.auth import current_attendee, optional_attendee
from hallway.main import app
from hallway.routes import communities

LUMA = "https://luma.com/event"
# Everything the public page may contain. No member names or ids, and no owner_id.
PUBLIC_KEYS = {
    "id", "name", "description", "luma_url", "member_count", "is_member", "is_organizer",
}  # fmt: skip


def _create(owner: TestClient, name: str = "Community") -> dict:
    body = {"name": name, "description": "Meet together", "luma_url": LUMA}
    created = owner.post("/api/communities", json=body)
    assert created.status_code == 201, created.text
    return created.json()


def test_community_invitation_requires_a_session_and_hides_the_owner(monkeypatch):
    documents = {}

    class Store:
        def index(self, *, index, id, document, refresh):
            documents[id] = document

        def get(self, *, index, id):
            return {"_source": documents[id], "_seq_no": 0, "_primary_term": 1}

    monkeypatch.setattr(es, "get_client", lambda: Store())
    client = TestClient(app)
    data = {
        "name": "Community", "description": "Meet together", "luma_url": "https://luma.com/event"
    }
    assert client.post("/api/communities", json=data).status_code == 401
    app.dependency_overrides[current_attendee] = lambda: {"id": "private-owner"}
    try:
        created = client.post("/api/communities", json=data)
        assert created.status_code == 201
        app.dependency_overrides.clear()
        invitation = client.get(f"/api/communities/{created.json()['id']}")
        assert invitation.status_code == 200
        assert invitation.json() == {
            "id": created.json()["id"], **data,
            "member_count": 0, "is_member": False, "is_organizer": False,
        }  # fmt: skip
    finally:
        app.dependency_overrides.clear()


def test_join_then_leave_and_both_can_be_repeated(person):
    organizer, _ = person("Olu Organizer")
    member, _ = person("Mia Member")
    community = _create(organizer)
    members = f"/api/communities/{community['id']}/members"
    page = f"/api/communities/{community['id']}"

    # Creating a community does not make the organizer a member of it.
    assert community["member_count"] == 0 and community["is_member"] is False

    for _ in range(2):
        joined = member.post(members)
        assert joined.status_code == 200
        assert joined.json()["is_member"] is True
        assert joined.json()["member_count"] == 1
    assert member.get(page).json()["is_member"] is True

    for _ in range(2):
        left = member.delete(members)
        assert left.status_code == 200
        assert left.json()["is_member"] is False
        assert left.json()["member_count"] == 0
    assert member.get(page).json()["is_member"] is False


def test_joining_needs_a_session_and_a_real_community(person):
    organizer, _ = person("Olu Organizer")
    community = _create(organizer)
    anonymous = TestClient(app)
    members = f"/api/communities/{community['id']}/members"
    assert anonymous.post(members).status_code == 401
    assert anonymous.delete(members).status_code == 401
    assert organizer.post("/api/communities/missing/members").status_code == 404
    assert organizer.delete("/api/communities/missing/members").status_code == 404
    # The body is ignored: the member is whoever holds the cookie, never an id sent in.
    _, other = person("Not Asked")
    organizer.post(members, json={"attendee_id": other["id"]})
    stored = es.get_client().get(index=es.COMMUNITIES, id=community["id"])["_source"]
    assert other["id"] not in stored["members"]


def test_two_people_joining_at_the_same_moment_are_both_members(person, monkeypatch):
    organizer, _ = person("Olu Organizer")
    community = _create(organizer)
    joiners = [person("Ana Atonce"), person("Ben Atonce")]
    client = es.get_client()
    barrier = Barrier(2)
    waited = set()
    original_index = client.index

    def synchronized_index(*args, **kwargs):
        """Hold each person's first write until both have read the same version, so
        one of the two is certain to meet a conflict and has to retry."""
        if kwargs.get("index") == es.COMMUNITIES and get_ident() not in waited:
            waited.add(get_ident())
            barrier.wait(timeout=5)
        return original_index(*args, **kwargs)

    monkeypatch.setattr(client, "index", synchronized_index)
    path = f"/api/communities/{community['id']}/members"
    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(lambda joiner: joiner[0].post(path).status_code, joiners))

    assert codes == [200, 200]
    stored = client.get(index=es.COMMUNITIES, id=community["id"])["_source"]
    assert sorted(stored["members"]) == sorted(me["id"] for _, me in joiners)


def test_public_page_shows_a_count_and_nothing_about_who(person):
    organizer, organizer_me = person("Olu Organizer")
    member, member_me = person("Mia Member")
    community = _create(organizer)
    path = f"/api/communities/{community['id']}"
    assert member.post(f"{path}/members").status_code == 200

    anonymous = TestClient(app)
    public = anonymous.get(path)
    assert public.status_code == 200
    assert set(public.json()) == PUBLIC_KEYS
    assert public.json()["member_count"] == 1
    assert public.json()["is_member"] is False
    assert public.json()["is_organizer"] is False
    for private in (member_me["id"], member_me["name"], organizer_me["id"]):
        assert private not in public.text

    # Signed in, the same keys; the two flags are only ever about the caller.
    assert set(member.get(path).json()) == PUBLIC_KEYS
    assert member.get(path).json()["is_member"] is True
    assert member.get(path).json()["is_organizer"] is False
    assert organizer.get(path).json()["is_organizer"] is True
    assert organizer.get(path).json()["is_member"] is False
    assert organizer_me["id"] not in organizer.get(path).text

    # A cookie that is not a real session is treated as a visitor, not an error.
    anonymous.cookies.set("hallway_session", f"{member_me['id']}.guessed-secret")
    assert anonymous.get(path).json()["is_member"] is False


def test_a_person_can_be_in_several_communities(person):
    organizer, _ = person("Olu Organizer")
    member, _ = person("Mia Member")
    first, second, third = (_create(organizer, name) for name in ("Beta", "alpha", "Gamma"))
    for community in (first, second):
        assert member.post(f"/api/communities/{community['id']}/members").status_code == 200
    own = _create(member, "Delta")

    assert TestClient(app).get("/api/me/communities").status_code == 401
    mine = member.get("/api/me/communities")
    assert mine.status_code == 200
    assert [c["name"] for c in mine.json()] == ["alpha", "Beta", "Delta"]
    assert all(set(c) == PUBLIC_KEYS for c in mine.json())
    by_id = {c["id"]: c for c in mine.json()}
    assert third["id"] not in by_id
    assert by_id[first["id"]]["is_member"] and not by_id[first["id"]]["is_organizer"]
    # The one I created is listed and marked, although I did not join it.
    assert by_id[own["id"]]["is_organizer"] and not by_id[own["id"]]["is_member"]

    assert member.delete(f"/api/communities/{first['id']}/members").status_code == 200
    assert [c["name"] for c in member.get("/api/me/communities").json()] == ["alpha", "Delta"]


def test_one_person_cannot_join_more_than_the_limit(person, monkeypatch):
    monkeypatch.setattr(communities, "MAX_JOINED", 2)
    organizer, _ = person("Olu Organizer")
    member, _ = person("Mia Member")
    ids = [_create(organizer, f"Community {n}")["id"] for n in range(3)]
    assert member.post(f"/api/communities/{ids[0]}/members").status_code == 200
    assert member.post(f"/api/communities/{ids[1]}/members").status_code == 200

    refused = member.post(f"/api/communities/{ids[2]}/members")
    assert refused.status_code == 409
    assert "Leave one to join another" in refused.json()["detail"]
    assert member.get(f"/api/communities/{ids[2]}").json()["member_count"] == 0
    # At the limit, joining one I am already in is still fine, and leaving frees a place.
    assert member.post(f"/api/communities/{ids[1]}/members").status_code == 200
    assert member.delete(f"/api/communities/{ids[0]}/members").status_code == 200
    assert member.post(f"/api/communities/{ids[2]}/members").status_code == 200


def test_only_the_organizer_can_edit_the_invitation(person):
    organizer, _ = person("Olu Organizer")
    member, member_me = person("Mia Member")
    community = _create(organizer)
    path = f"/api/communities/{community['id']}"
    assert member.post(f"{path}/members").status_code == 200
    change = {"name": "New name", "luma_url": "https://lu.ma/other"}

    assert TestClient(app).patch(path, json=change).status_code == 401
    assert member.patch(path, json=change).status_code == 403  # a member is not an organizer
    assert organizer.patch("/api/communities/missing", json=change).status_code == 404
    for bad in (
        {"luma_url": "https://luma.com.example.com/event"},
        {"luma_url": "http://luma.com/event"},
        {"name": "   "},
        {"description": "x" * 501},
    ):
        assert organizer.patch(path, json=bad).status_code == 422
    assert TestClient(app).get(path).json()["name"] == "Community"

    edited = organizer.patch(path, json=change)
    assert edited.status_code == 200
    assert set(edited.json()) == PUBLIC_KEYS
    public = TestClient(app).get(path).json()
    assert public["name"] == "New name" and public["luma_url"] == "https://lu.ma/other"
    assert public["description"] == "Meet together"  # left out, so kept
    # Editing keeps the members, and the organizer still owns it.
    stored = es.get_client().get(index=es.COMMUNITIES, id=community["id"])["_source"]
    assert stored["members"] == [member_me["id"]]
    assert organizer.get(path).json()["is_organizer"] is True


def test_a_person_in_no_community_can_still_get_matches(person):
    solo, _ = person("Sol Unaffiliated", asks="quorblix", working_on="quorblix")
    _, helper = person("Hel Helper", offers="quorblix", working_on="quorblix")
    assert solo.get("/api/me/communities").json() == []
    matches = solo.get("/api/matches")
    assert matches.status_code == 200
    assert helper["id"] in [m["attendee"]["id"] for m in matches.json()]


def test_joining_does_not_change_the_groups_on_a_profile(person):
    organizer, _ = person("Olu Organizer")
    member, member_me = person("Mia Member", groups=["Typed Myself"])
    community = _create(organizer, "Typed Myself")
    members = f"/api/communities/{community['id']}/members"
    assert member.post(members).status_code == 200
    assert member.get("/api/me").json()["groups"] == ["Typed Myself"]
    assert member.delete(members).status_code == 200
    assert member.get("/api/me").json()["groups"] == ["Typed Myself"]


def test_an_existing_index_gains_the_members_field_without_losing_data(indices, monkeypatch):
    """A deployment that already has a communities index must pick up `members` on
    startup without the index being deleted."""
    client = es.get_client()
    old = f"{es.COMMUNITIES}-before-members"
    monkeypatch.setattr(es, "COMMUNITIES", old)
    old_mapping = {"properties": {"id": {"type": "keyword"}, "owner_id": {"type": "keyword"}}}
    client.indices.create(index=old, mappings=old_mapping)
    try:
        doc = {"id": "kept", "name": "Kept", "description": "", "luma_url": LUMA, "owner_id": "o"}
        client.index(index=old, id="kept", document=doc, refresh=True)

        es.ensure_indices(client)

        properties = client.indices.get_mapping(index=old)[old]["mappings"]["properties"]
        assert properties["members"] == {"type": "keyword"}
        assert client.get(index=old, id="kept")["_source"] == doc
        # A community stored before members existed reads as having none.
        page = TestClient(app).get("/api/communities/kept")
        assert page.status_code == 200 and page.json()["member_count"] == 0
    finally:
        client.indices.delete(index=old, ignore_unavailable=True)


def test_community_rejects_misleading_luma_links():
    import pytest
    from pydantic import ValidationError

    from hallway.models import CommunityIn

    for url in (
        "javascript:alert(1)", "https://luma.com.example.com/event",
        "http://luma.com/event", "https://luma.com/",
        # user:pass credentials in the URL
        "https://user:pass@luma.com/event",
        # whitespace and control characters
        "https://luma.com/e\nX", "https://luma.com/ e", "https://luma.com/e\t1",
        # invalid or non-443 ports
        "https://luma.com:8443/event", "https://luma.com:abc/event",
    ):
        with pytest.raises(ValidationError):
            CommunityIn(name="Community", luma_url=url)


def test_community_accepts_valid_luma_links():
    from hallway.models import CommunityIn

    # Standard luma.com
    c = CommunityIn(name="Community", luma_url="https://luma.com/event")
    assert c.luma_url == "https://luma.com/event"

    # www.luma.com should also be allowed
    c = CommunityIn(name="Community", luma_url="https://www.luma.com/event")
    assert c.luma_url == "https://www.luma.com/event"

    # lu.ma
    c = CommunityIn(name="Community", luma_url="https://lu.ma/event")
    assert c.luma_url == "https://lu.ma/event"

    # Explicit port 443 is fine
    c = CommunityIn(name="Community", luma_url="https://luma.com:443/event")
    assert c.luma_url == "https://luma.com:443/event"

# ---- Community discovery: GET /api/communities (list / search) -----------------
# These tests fake the store (same pattern as the first test in this file), so
# they run without Elasticsearch. The integration test below runs against real
# Elasticsearch in CI / live ES.


class _ListStore:
    """In-memory communities index: index / get / search / count, ES-shaped."""

    def __init__(self, docs: list[dict] | None = None):
        self.documents = {d["id"]: dict(d) for d in (docs or [])}

    def index(self, *, index, id, document, refresh, **kwargs):
        self.documents[id] = dict(document)

    def get(self, *, index, id):
        return {"_source": self.documents[id], "_seq_no": 0, "_primary_term": 1}

    def count(self, *, index, query):
        wanted = query.get("term", {}).get("members")
        return {"count": sum(wanted in d.get("members", []) for d in self.documents.values())}

    def search(self, *, index, query, size, sort=None):
        docs = sorted(
            self.documents.values(), key=lambda d: d["created_at"], reverse=True
        )
        if "multi_match" in query:
            term = query["multi_match"]["query"].strip().lower()
            fields = query["multi_match"]["fields"]
            docs = [
                d for d in docs
                if term and any(term in str(d.get(f, "")).lower() for f in fields)
            ]
        return {"hits": {"hits": [{"_source": d} for d in docs[:size]]}}


def _community_doc(
    name, *, id, owner_id="owner-1", members=None, created_at="2026-11-09T10:00:00+00:00"
):
    return {
        "id": id, "name": name, "description": "Meet together",
        "luma_url": LUMA, "owner_id": owner_id, "members": members or [],
        "created_at": created_at,
    }


def test_list_communities_is_empty_when_none_exist(monkeypatch):
    monkeypatch.setattr(es, "get_client", lambda: _ListStore())
    assert TestClient(app).get("/api/communities").json() == []


def test_list_communities_shows_created_communities_with_counts_only(monkeypatch):
    store = _ListStore()
    monkeypatch.setattr(es, "get_client", lambda: store)
    app.dependency_overrides[current_attendee] = lambda: {"id": "owner-1"}
    try:
        _create(TestClient(app), "Beta")
        _create(TestClient(app), "alpha")
    finally:
        app.dependency_overrides.clear()
    listed = TestClient(app).get("/api/communities")
    assert listed.status_code == 200
    assert {c["name"] for c in listed.json()} == {"Beta", "alpha"}
    assert all(set(c) == PUBLIC_KEYS for c in listed.json())
    assert all(c["member_count"] == 0 for c in listed.json())
    assert all(c["is_member"] is False for c in listed.json())


def test_list_communities_search_filters_by_name_and_description(monkeypatch):
    store = _ListStore([
        _community_doc("Girls Who Code", id="gwc", created_at="2026-11-09T10:00:00+00:00"),
        _community_doc("Platform Engineering", id="pe", created_at="2026-11-09T11:00:00+00:00"),
    ])
    monkeypatch.setattr(es, "get_client", lambda: store)
    client = TestClient(app)
    assert [c["id"] for c in client.get("/api/communities?q=girls").json()] == ["gwc"]
    assert [c["id"] for c in client.get("/api/communities?q=PLATFORM").json()] == ["pe"]
    assert client.get("/api/communities?q=zzz-no-such").json() == []
    assert len(client.get("/api/communities").json()) == 2


def test_list_communities_marks_membership_for_the_caller(monkeypatch):
    store = _ListStore([
        _community_doc("Students", id="stu", owner_id="owner-1", members=["member-1"]),
    ])
    monkeypatch.setattr(es, "get_client", lambda: store)
    app.dependency_overrides[optional_attendee] = lambda: {"id": "member-1"}
    try:
        mine = TestClient(app).get("/api/communities").json()
    finally:
        app.dependency_overrides.clear()
    assert mine[0]["is_member"] is True and mine[0]["is_organizer"] is False
    visitor = TestClient(app).get("/api/communities").json()
    assert visitor[0]["is_member"] is False and visitor[0]["is_organizer"] is False


def test_list_communities_limit_is_bounded(monkeypatch):
    store = _ListStore([
        _community_doc("One", id="one"), _community_doc("Two", id="two"),
    ])
    monkeypatch.setattr(es, "get_client", lambda: store)
    client = TestClient(app)
    assert client.get("/api/communities?limit=0").status_code == 422
    assert client.get("/api/communities?limit=51").status_code == 422
    assert client.get("/api/communities?limit=abc").status_code == 422
    assert len(client.get("/api/communities?limit=1").json()) == 1


def test_list_communities_shows_duplicate_names_as_separate_communities(monkeypatch):
    # Documented behaviour, not fixed here: names are not unique, so two
    # communities called "Students" are two entries with distinct ids.
    store = _ListStore([
        _community_doc("Students", id="stu-1"),
        _community_doc("Students", id="stu-2", owner_id="owner-2"),
    ])
    monkeypatch.setattr(es, "get_client", lambda: store)
    listed = TestClient(app).get("/api/communities").json()
    assert [c["name"] for c in listed] == ["Students", "Students"]
    assert {c["id"] for c in listed} == {"stu-1", "stu-2"}


def test_list_communities_against_real_elasticsearch(person):
    """Integration: the same browse behaviour on real ES (skipped without it)."""
    organizer, _ = person("Olu Organizer")
    first = _create(organizer, "Beta")
    second = _create(organizer, "alpha")
    listed = TestClient(app).get("/api/communities")
    assert listed.status_code == 200
    assert {c["id"] for c in listed.json()} == {first["id"], second["id"]}
    assert [c["id"] for c in TestClient(app).get("/api/communities?q=beta").json()] == [
        first["id"]
    ]
