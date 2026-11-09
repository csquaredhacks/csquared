"""PATCH /api/me: a person edits their own profile, and only their own."""

from fastapi.testclient import TestClient

from hallway import es
from hallway.main import app


def match_with(client, other: dict) -> dict | None:
    matches = client.get("/api/matches").json()
    return next((m for m in matches if m["attendee"]["id"] == other["id"]), None)


def test_editing_needs_a_session(person):
    _, someone = person("Edit Target", offers="original offer")
    anonymous = TestClient(app)
    assert anonymous.patch("/api/me", json={"offers": "hijacked"}).status_code == 401
    assert anonymous.get(f"/api/attendees/{someone['id']}").json()["offers"] == "original offer"


def test_unknown_and_invalid_fields_are_refused(person):
    client, me = person("Edit Strict", asks="original ask")
    # Only the listed profile fields can be changed. Identity and secrets never can.
    for field in ("id", "name", "secret", "recovery_code", "created_at", "nickname"):
        assert client.patch("/api/me", json={field: "x"}).status_code == 422, field
    # One bad field refuses the whole request, even next to a good one.
    assert client.patch("/api/me", json={"asks": "new ask", "id": "x"}).status_code == 422
    # The same limits as registration.
    assert client.patch("/api/me", json={"asks": "x" * 501}).status_code == 422
    assert client.patch("/api/me", json={"fun_fact": "x" * 301}).status_code == 422
    assert client.patch("/api/me", json={"working_on": "   "}).status_code == 422
    assert client.patch("/api/me", json={"tags": [f"t{i}" for i in range(11)]}).status_code == 422
    assert client.patch("/api/me", json={"groups": list("abcdef")}).status_code == 422
    assert client.patch("/api/me", json={"comfort": "crowds"}).status_code == 422
    assert client.get("/api/me").json() == me  # nothing was changed by any of them


def test_an_edit_is_cleaned_like_registration_and_leaves_the_rest_alone(person):
    client, me = person(
        "Edit Partial", asks="original ask", offers="original offer", fun_fact="juggles",
        tags=["go"], groups=["Walrus Club"], comfort="small_groups",
    )  # fmt: skip
    changed = client.patch("/api/me", json={"offers": "  rust reviews  ", "tags": [" K8s ", "k8s"]})
    assert changed.status_code == 200
    expected = me | {"offers": "rust reviews", "tags": ["k8s"]}
    assert changed.json() == expected
    assert client.get("/api/me").json() == expected  # stored, not only echoed back
    assert client.get(f"/api/attendees/{me['id']}").json()["offers"] == "rust reviews"

    # An empty body and a null both mean "keep it as it is".
    assert client.patch("/api/me", json={}).json() == expected
    assert client.patch("/api/me", json={"asks": None}).json() == expected
    # An optional field can be emptied. The session still works: the secret was not touched.
    assert client.patch("/api/me", json={"asks": "", "tags": []}).status_code == 200
    assert client.get("/api/me").json() == expected | {"asks": "", "tags": []}
    stored = es.get_client().get(index=es.ATTENDEES, id=me["id"])["_source"]
    assert stored["secret"] and stored["created_at"] and stored["name"] == "Edit Partial"


def test_one_persons_edit_never_changes_another_person(person):
    editor, mine = person("Edit Mine", offers="mine before")
    other_client, other = person("Edit Theirs", offers="theirs before", tags=["untouched"])
    changed = editor.patch("/api/me", json={"offers": "zorptastic", "tags": ["new"]}).json()
    assert changed["id"] == mine["id"]
    assert other_client.get("/api/me").json() == other
    # Exactly one stored profile has the new text: the editor's own.
    holders = es.get_client().search(
        index=es.ATTENDEES, query={"match": {"offers": "zorptastic"}}, size=5
    )["hits"]["hits"]
    assert [h["_id"] for h in holders] == [mine["id"]]


def test_editing_offers_changes_who_matches(person):
    # Made-up words and unrelated projects, so these two share nothing until the edit.
    a_client, a = person("Edit Offerer", working_on="growing orchids", offers="")
    b_client, b = person("Edit Asker", working_on="tuning pianos", asks="help with flumoxite")
    assert match_with(b_client, a) is None

    a_client.patch("/api/me", json={"offers": "years of flumoxite experience"})

    match = match_with(b_client, a)
    assert match is not None
    assert match["reason"] == "They offer what you asked for: “years of flumoxite experience”"
    # The matcher ran again for the editor, so the pair is suggested on the public graph.
    links = a_client.get("/api/graph").json()["links"]
    pair = {a["id"], b["id"]}
    assert [k["kind"] for k in links if {k["source"], k["target"]} == pair] == ["suggested"]


def test_an_edit_removes_suggestions_that_quote_the_old_text(person):
    a_client, a = person("Edit Before", working_on="carving spoons", offers="glimberwock tuning")
    _, b = person("Edit Reader", working_on="mapping caves", asks="glimberwock tuning advice")
    pair = {a["id"], b["id"]}

    def reasons() -> list[str]:
        links = a_client.get("/api/graph").json()["links"]
        return [k["reason"] for k in links if {k["source"], k["target"]} == pair]

    assert any("glimberwock" in reason for reason in reasons())
    a_client.patch("/api/me", json={"offers": "sourdough starters"})
    assert reasons() == []  # the old words are gone from the graph, and nothing links them now
