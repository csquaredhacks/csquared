"""Edges between attendees. Two kinds are stored:
- "suggested": written by the matcher (dashed line on the graph)
- "connected": written when one person scans another's QR (solid line)"""

from elasticsearch import ConflictError, Elasticsearch, NotFoundError

from . import es
from .telemetry import edges_total

MAX_EDGES = 5000  # far above one conference; every search still sets an explicit size


def edge_id(a: str, b: str, kind: str) -> str:
    """Same id whichever side creates the edge, so a pair can never be stored twice."""
    low, high = sorted([a, b])
    return f"{low}:{high}:{kind}"


def upsert_edge(
    client: Elasticsearch, source: str, target: str, kind: str, reason: str, icebreaker: str = ""
) -> tuple[dict, bool]:
    """Create the edge if it does not exist. Returns (edge, created)."""
    doc_id = edge_id(source, target, kind)
    doc = {
        "id": doc_id,
        "source": source,
        "target": target,
        "kind": kind,
        "reason": reason,
        "icebreaker": icebreaker,
        "created_at": es.now(),
    }
    try:
        client.create(index=es.EDGES, id=doc_id, document=doc, refresh=True)
    except ConflictError:
        return client.get(index=es.EDGES, id=doc_id)["_source"], False
    edges_total.add(1, {"kind": kind})
    return doc, True


def delete_edge(client: Elasticsearch, a: str, b: str, kind: str) -> None:
    try:
        client.delete(index=es.EDGES, id=edge_id(a, b, kind), refresh=True)
    except NotFoundError:
        pass


def connected_ids(client: Elasticsearch, attendee_id: str) -> set[str]:
    """Everyone this attendee has a "connected" edge with."""
    query = {
        "bool": {
            "filter": [{"term": {"kind": "connected"}}],
            "should": [{"term": {"source": attendee_id}}, {"term": {"target": attendee_id}}],
            "minimum_should_match": 1,
        }
    }
    hits = client.search(index=es.EDGES, query=query, size=MAX_EDGES)["hits"]["hits"]
    ids = {h["_source"]["source"] for h in hits} | {h["_source"]["target"] for h in hits}
    ids.discard(attendee_id)
    return ids


def all_edges(client: Elasticsearch) -> list[dict]:
    hits = client.search(index=es.EDGES, query={"match_all": {}}, size=MAX_EDGES)["hits"]["hits"]
    return [h["_source"] for h in hits]
