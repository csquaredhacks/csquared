"""The graph: who is connected to whom, and how.

Four kinds of relationship are kept apart on purpose:
  suggested  the matcher thinks two people should meet. Nobody agreed to anything.
  invited    one person asked to meet another. Only those two people can see it.
  planned    the invitation was accepted. Both agreed to meet.
  connected  one scanned the other's QR. They met.

The public graph (GET /api/graph) shows only people who opted in, and never an invitation.
My own view (GET /api/graph/me) adds my private invitations and who could introduce me.
"""

from collections import deque

from elasticsearch import NotFoundError
from fastapi import APIRouter, Depends, HTTPException, Response

from .. import edges, es
from ..auth import current_attendee
from ..matcher import MAX_ATTENDEES
from ..matching import SOURCE_FIELDS, explain_why, find_matches
from ..models import (
    Attendee,
    EdgeIn,
    Graph,
    GraphLink,
    GraphNode,
    InvitationResult,
    MyGraph,
    Path,
    PathStep,
    Relationship,
)
from ..telemetry import tracer

router = APIRouter()

PUBLIC_KINDS = {"connected", "planned", "suggested"}
MAX_PENDING = 20  # invitations one person can have waiting for an answer
MAX_INTRODUCERS = 2  # a chain longer than me -> A -> B -> them is not a real introduction
# Order of the list in "my graph": what needs my attention first.
ORDER = ["invited_you", "planned", "you_invited", "suggested", "met"]


def load_graph() -> Graph:
    """Everyone who opted in, and every public edge between two of them."""
    client = es.get_client()
    hits = client.search(
        index=es.ATTENDEES,
        query={"term": {"on_graph": True}},
        size=MAX_ATTENDEES,
        source=["id", "name", "groups", "tags", "show_groups"],
    )["hits"]["hits"]
    people = {h["_source"]["id"]: h["_source"] for h in hits}

    links = []
    for e in edges.all_edges(client):
        if e["kind"] not in PUBLIC_KINDS:
            continue  # a pending invitation is private to the two people involved
        if e["source"] not in people or e["target"] not in people:
            continue  # one side did not opt in to the graph
        links.append(GraphLink(**e))
    nodes = [
        GraphNode(
            id=p["id"],
            name=p["name"],
            tags=p["tags"],
            # Communities are a separate choice from being on the graph at all.
            groups=p["groups"] if p.get("show_groups") else [],
        )
        for p in people.values()
    ]
    return Graph(nodes=nodes, links=links)


def met_neighbours(links: list[GraphLink]) -> dict[str, list[str]]:
    """For each person, the people they have actually met ("connected" links only)."""
    neighbours: dict[str, list[str]] = {}
    for link in links:
        if link.kind == "connected":
            neighbours.setdefault(link.source, []).append(link.target)
            neighbours.setdefault(link.target, []).append(link.source)
    return neighbours


def shortest_path(links: list[GraphLink], start: str, goal: str) -> list[str]:
    """Breadth-first search over "connected" links only. Returns ids from start to goal,
    or [] if no chain of real connections exists. This is the "who can introduce me" path."""
    neighbours = met_neighbours(links)
    came_from: dict[str, str | None] = {start: None}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        if current == goal:
            path = []
            while current is not None:
                path.append(current)
                current = came_from[current]
            return path[::-1]
        for nxt in neighbours.get(current, []):
            if nxt not in came_from:
                came_from[nxt] = current
                queue.append(nxt)
    return []


@router.get("/api/graph")
def graph() -> Graph:
    return load_graph()


@router.get("/api/graph/path")
def path(to: str, me: dict = Depends(current_attendee)) -> Path:
    data = load_graph()
    names = {n.id: n.name for n in data.nodes}
    with tracer.start_as_current_span("graph.bfs") as span:
        ids = shortest_path(data.links, me["id"], to)
        span.set_attribute("graph.path_length", len(ids))
    return Path(path=[PathStep(id=i, name=names.get(i, "?")) for i in ids])


@router.get("/api/graph/me")
def my_graph(me: dict = Depends(current_attendee)) -> MyGraph:
    """My relationships, each with a reason and, where one exists, an introducer."""
    client = es.get_client()
    with tracer.start_as_current_span("graph.me") as span:
        # 1. What each person is to me. If more than one edge exists for a person,
        #    the strongest relationship wins: met, then planned, invited, suggested.
        strength = ["met", "planned", "invited_you", "you_invited", "suggested"]
        kinds: dict[str, str] = {}
        for e in edges.edges_of(client, me["id"]):
            mine = e["source"] == me["id"]
            other = e["target"] if mine else e["source"]
            kind = {"connected": "met", "planned": "planned", "suggested": "suggested"}.get(
                e["kind"], "you_invited" if mine else "invited_you"
            )
            if other not in kinds or strength.index(kind) < strength.index(kinds[other]):
                kinds[other] = kind

        # 2. Reasons, always from my point of view, from the same query as "my five".
        found = find_matches(client, me, size=10)
        people = {other["id"]: other for other, _score, _reason in found}
        reasons = {other["id"]: reason for other, _score, reason in found}

        #    People outside my top ten (someone who invited me, say) get their real
        #    reason too, by running the same query over just those people.
        unexplained = sorted(o for o, kind in kinds.items() if kind != "met" and o not in reasons)
        if unexplained:
            extra = find_matches(client, me, size=len(unexplained), only_ids=unexplained)
            people |= {other["id"]: other for other, _score, _reason in extra}
            reasons |= {other["id"]: reason for other, _score, reason in extra}

        # 3. Introductions: people my connections have met, searched with my asks and
        #    offers. Only connections between people on the public graph are used.
        data = load_graph()
        neighbours = met_neighbours(data.links)
        met = {other for other, kind in kinds.items() if kind == "met"}
        friends_of_friends = {n for m in met for n in neighbours.get(m, [])} - met - {me["id"]}
        if friends_of_friends:
            nearby = find_matches(client, me, size=5, only_ids=sorted(friends_of_friends))
            for other, _score, reason in nearby:
                kinds.setdefault(other["id"], "suggested")
                people[other["id"]] = other
                reasons[other["id"]] = reason

        # 4. Load anyone we do not have a profile for yet (never the private fields).
        missing = [other for other in kinds if other not in people]
        if missing:
            docs = client.mget(index=es.ATTENDEES, ids=missing, source=SOURCE_FIELDS)["docs"]
            people |= {d["_id"]: d["_source"] for d in docs if d.get("found")}

        names = {n.id: n.name for n in data.nodes}
        relationships = []
        for other, kind in kinds.items():
            if other not in people:
                continue  # the profile no longer exists
            via: list[PathStep] = []
            if kind != "met":
                chain = shortest_path(data.links, me["id"], other)[1:-1]
                if 0 < len(chain) <= MAX_INTRODUCERS:
                    via = [PathStep(id=i, name=names.get(i, "?")) for i in chain]
            relationships.append(
                Relationship(
                    attendee=Attendee(**people[other]),
                    kind=kind,
                    reason=reasons.get(other) or explain_why(me, people[other], set()),
                    via=via,
                )
            )
        relationships.sort(key=lambda r: (ORDER.index(r.kind), r.attendee.name))
        span.set_attribute("graph.relationships", len(relationships))
        span.set_attribute("graph.introductions", sum(1 for r in relationships if r.via))
    return MyGraph(relationships=relationships)


# ---- Invitations: "I would like to meet you". Private until the other person accepts. ----


def _other_person(other_id: str, me: dict) -> dict:
    if other_id == me["id"]:
        raise HTTPException(400, "You cannot invite yourself")
    try:
        return es.get_client().get(index=es.ATTENDEES, id=other_id, source=SOURCE_FIELDS)["_source"]
    except NotFoundError:
        raise HTTPException(404, "No such attendee") from None


def _plan(me: dict, other: dict) -> InvitationResult:
    """Both people have now said yes: replace the invitation with an accepted plan."""
    client = es.get_client()
    edges.delete_between(client, me["id"], other["id"], ["suggested", "invited"])
    edges.upsert_edge(client, other["id"], me["id"], "planned", "You both chose to meet")
    return InvitationResult(kind="planned", other=Attendee(**other))


@router.post("/api/invitations")
def invite(body: EdgeIn, me: dict = Depends(current_attendee)) -> InvitationResult:
    """Ask to meet someone. They can accept, decline or ignore it. Nobody else sees it."""
    other = _other_person(body.to_id, me)
    client = es.get_client()
    if client.exists(index=es.EDGES, id=edges.edge_id(me["id"], other["id"], "connected")):
        raise HTTPException(400, "You have already met")
    if client.exists(index=es.EDGES, id=edges.edge_id(me["id"], other["id"], "planned")):
        return InvitationResult(kind="planned", other=Attendee(**other))
    if client.exists(index=es.EDGES, id=edges.invitation_id(other["id"], me["id"])):
        return _plan(me, other)  # they had already asked me: that makes it mutual

    waiting = {"bool": {"filter": [{"term": {"kind": "invited"}}, {"term": {"source": me["id"]}}]}}
    if client.count(index=es.EDGES, query=waiting)["count"] >= MAX_PENDING:
        raise HTTPException(429, f"You have {MAX_PENDING} invitations waiting for an answer")
    edges.upsert_edge(
        client,
        me["id"],
        other["id"],
        "invited",
        reason="",
        doc_id=edges.invitation_id(me["id"], other["id"]),
    )
    return InvitationResult(kind="you_invited", other=Attendee(**other))


@router.post("/api/invitations/{other_id}/accept")
def accept(other_id: str, me: dict = Depends(current_attendee)) -> InvitationResult:
    other = _other_person(other_id, me)
    invitation = edges.invitation_id(other["id"], me["id"])
    if not es.get_client().exists(index=es.EDGES, id=invitation):
        raise HTTPException(404, "That person has not invited you")
    return _plan(me, other)


@router.delete("/api/invitations/{other_id}", status_code=204)
def withdraw(other_id: str, me: dict = Depends(current_attendee)) -> Response:
    """Decline their invitation, take back mine, or cancel our plan. The other person is
    not told who did it or why: the invitation or plan is simply no longer there."""
    other = _other_person(other_id, me)
    edges.delete_between(es.get_client(), me["id"], other["id"], ["invited", "planned"])
    return Response(status_code=204)
