"""The four kinds of relationship stay distinct, and private things stay private."""

from hallway.matching import build_match_query


def links_between(graph: dict, a: dict, b: dict) -> list[str]:
    pair = {a["id"], b["id"]}
    return [link["kind"] for link in graph["links"] if {link["source"], link["target"]} == pair]


def my_view(client, other: dict) -> dict | None:
    relationships = client.get("/api/graph/me").json()["relationships"]
    return next((r for r in relationships if r["attendee"]["id"] == other["id"]), None)


def test_only_ids_narrows_the_match_query():
    a = {"id": "me", "asks": "help with tracing"}
    rrf = build_match_query(a, ["me"], only_ids=["x", "y"], semantic=False)["retriever"]["rrf"]
    assert rrf["filter"]["bool"]["filter"] == [{"ids": {"values": ["x", "y"]}}]
    assert rrf["filter"]["bool"]["must_not"] == [{"ids": {"values": ["me"]}}]
    plain = build_match_query(a, ["me"], semantic=False)["retriever"]["rrf"]
    assert "filter" not in plain["filter"]["bool"]


def test_an_invitation_is_private_until_it_is_accepted(person):
    a_client, a = person("Invite A", working_on="alpha invitations")
    b_client, b = person("Invite B", working_on="beta invitations")
    c_client, _c = person("Invite C", working_on="gamma invitations")

    sent = a_client.post("/api/invitations", json={"to_id": b["id"]})
    assert sent.status_code == 200 and sent.json()["kind"] == "you_invited"

    # Nobody else can see it: not on the public graph, not in a third person's view.
    assert "invited" not in str(c_client.get("/api/graph").json())
    assert all(k == "suggested" for k in links_between(c_client.get("/api/graph").json(), a, b))
    assert my_view(c_client, a) is None or my_view(c_client, a)["kind"] == "suggested"
    # The two people involved each see their own side of it.
    assert my_view(a_client, b)["kind"] == "you_invited"
    assert my_view(b_client, a)["kind"] == "invited_you"
    # The reason is real matching evidence, written from the reader's point of view.
    assert "alpha invitations" in my_view(b_client, a)["reason"]

    accepted = b_client.post(f"/api/invitations/{a['id']}/accept")
    assert accepted.status_code == 200 and accepted.json()["kind"] == "planned"
    assert links_between(a_client.get("/api/graph").json(), a, b) == ["planned"]
    assert my_view(a_client, b)["kind"] == "planned"


def test_two_invitations_make_a_plan_and_declining_removes_it(person):
    a_client, a = person("Mutual A")
    b_client, b = person("Mutual B")
    a_client.post("/api/invitations", json={"to_id": b["id"]})
    assert b_client.post("/api/invitations", json={"to_id": a["id"]}).json()["kind"] == "planned"

    # Either person can cancel. Nothing about the plan is left anywhere.
    assert b_client.delete(f"/api/invitations/{a['id']}").status_code == 204
    assert "planned" not in links_between(a_client.get("/api/graph").json(), a, b)
    assert my_view(a_client, b) is None or my_view(a_client, b)["kind"] == "suggested"

    # Declining an invitation works the same way.
    a_client.post("/api/invitations", json={"to_id": b["id"]})
    b_client.delete(f"/api/invitations/{a['id']}")
    assert b_client.post(f"/api/invitations/{a['id']}/accept").status_code == 404


def test_meeting_replaces_the_plan_and_remembers_it(person):
    a_client, a = person("Plan A")
    b_client, b = person("Plan B")
    c_client, c = person("Plan C")
    a_client.post("/api/invitations", json={"to_id": b["id"]})
    b_client.post(f"/api/invitations/{a['id']}/accept")

    planned = a_client.post("/api/edges", json={"to_id": b["id"]}).json()["edge"]
    chance = a_client.post("/api/edges", json={"to_id": c["id"]}).json()["edge"]
    assert planned["planned"] is True and chance["planned"] is False
    assert links_between(a_client.get("/api/graph").json(), a, b) == ["connected"]
    assert my_view(a_client, b)["kind"] == "met"
    # Once two people have met there is nothing left to invite.
    assert b_client.post("/api/invitations", json={"to_id": a["id"]}).status_code == 400


def test_invitation_rules(person):
    a_client, a = person("Rules A")
    assert a_client.post("/api/invitations", json={"to_id": a["id"]}).status_code == 400
    assert a_client.post("/api/invitations", json={"to_id": "nobody"}).status_code == 404
    assert a_client.post("/api/invitations/nobody/accept").status_code == 404


def test_someone_i_met_can_introduce_me(person):
    me_client, me = person("Intro Me", asks="help with zebra telemetry pipelines")
    friend_client, friend = person("Intro Friend", working_on="unrelated gardening")
    _, expert = person("Intro Expert", offers="zebra telemetry pipelines advice")
    me_client.post("/api/edges", json={"to_id": friend["id"]})
    friend_client.post("/api/edges", json={"to_id": expert["id"]})

    view = my_view(me_client, expert)
    assert view["kind"] == "suggested"
    assert [step["name"] for step in view["via"]] == ["Intro Friend"]
    assert "zebra telemetry" in view["reason"]  # the reason is the real matching evidence
    assert my_view(me_client, friend)["via"] == []  # no introducer needed for someone I met


def test_people_off_the_graph_are_never_used_as_introducers(person):
    me_client, me = person("Quiet Me", asks="help with walrus databases")
    hidden_client, hidden = person("Quiet Friend", on_graph=False)
    _, expert = person("Quiet Expert", offers="walrus databases advice")
    me_client.post("/api/edges", json={"to_id": hidden["id"]})
    hidden_client.post("/api/edges", json={"to_id": expert["id"]})

    view = my_view(me_client, expert)
    assert view is None or view["via"] == []  # their meeting is not ours to reveal


def test_graph_visibility_is_two_separate_choices_and_can_be_withdrawn(person):
    client, me = person("Choice Me", groups=["Walrus Club"], on_graph=True, show_groups=False)

    def node():
        nodes = client.get("/api/graph").json()["nodes"]
        return next((n for n in nodes if n["id"] == me["id"]), None)

    assert node()["groups"] == []  # on the graph, communities hidden
    assert client.patch("/api/me", json={"show_groups": True}).json()["show_groups"] is True
    assert node()["groups"] == ["Walrus Club"]
    assert client.patch("/api/me", json={"on_graph": False}).json()["on_graph"] is False
    assert node() is None  # withdrawing removes the public information

    # Both choices are off unless someone turns them on.
    fresh = client.post("/api/attendees", json={"name": "Default", "working_on": "x"}).json()
    assert fresh["on_graph"] is False and fresh["show_groups"] is False
