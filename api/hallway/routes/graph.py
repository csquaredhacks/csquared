from collections import deque

from fastapi import APIRouter, Depends

from .. import edges, es
from ..auth import current_attendee
from ..matcher import MAX_ATTENDEES
from ..models import Graph, GraphLink, GraphNode, Path, PathStep
from ..telemetry import tracer

router = APIRouter()


def load_graph() -> Graph:
    """Everyone who opted in, and every edge between two of them."""
    client = es.get_client()
    hits = client.search(
        index=es.ATTENDEES,
        query={"term": {"on_graph": True}},
        size=MAX_ATTENDEES,
        source=["id", "name", "groups", "tags"],
    )["hits"]["hits"]
    people = {h["_source"]["id"]: h["_source"] for h in hits}

    links, degree = [], dict.fromkeys(people, 0)
    for e in edges.all_edges(client):
        if e["source"] not in people or e["target"] not in people:
            continue  # one side opted out of the graph
        links.append(GraphLink(**e))
        if e["kind"] == "connected":
            degree[e["source"]] += 1
            degree[e["target"]] += 1
    nodes = [GraphNode(**p, degree=degree[p["id"]]) for p in people.values()]
    return Graph(nodes=nodes, links=links)


def shortest_path(links: list[GraphLink], start: str, goal: str) -> list[str]:
    """Breadth-first search over "connected" links only. Returns ids from start to goal,
    or [] if no chain of real connections exists. This is the "who can introduce me" path."""
    neighbours: dict[str, list[str]] = {}
    for link in links:
        if link.kind == "connected":
            neighbours.setdefault(link.source, []).append(link.target)
            neighbours.setdefault(link.target, []).append(link.source)

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
