"""The matchmaking query: one Elasticsearch request that cross-matches people.

My ASKS are searched against other people's OFFERS, my OFFERS against their ASKS,
my project against their projects, plus shared tags and groups. Each of those is its
own retriever; Reciprocal Rank Fusion (RRF) merges the ranked lists into one top five.
With ELSER configured, every text retriever runs twice: BM25 (exact words) and
semantic (meaning), so "pods keep getting evicted" finds "happy to explain QoS classes".

Every query is named, and Elasticsearch reports which names matched each hit
(`matched_queries`). That is how the app can honestly say WHY two people were matched.
"""

from elasticsearch import Elasticsearch

from . import edges, es
from .config import settings

SOURCE_FIELDS = [
    "id", "name", "working_on", "asks", "offers", "fun_fact", "tags", "groups", "comfort",
]  # fmt: skip


def _lexical(field: str, text: str, name: str) -> dict:
    return {"standard": {"query": {"match": {field: {"query": text, "_name": name}}}}}


def _semantic(field: str, text: str, name: str) -> dict:
    return {"standard": {"query": {"semantic": {"field": field, "query": text, "_name": name}}}}


def build_match_query(
    a: dict, exclude_ids: list[str], size: int = 5, semantic: bool | None = None
) -> dict:
    """Search body for "who should attendee `a` meet". Pure function, easy to test.
    Empty fields are left out: Elasticsearch rejects an empty semantic query."""
    if semantic is None:
        semantic = bool(settings.elser_id)

    retrievers = []
    pairs = [  # (my text, their lexical field, their semantic field, query name)
        (a.get("asks"), "offers", "offers_semantic", "asks_to_offers"),
        (a.get("offers"), "asks", "asks_semantic", "offers_to_asks"),
        (a.get("working_on"), "working_on", "profile_semantic", "similar_work"),
    ]
    for text, lexical_field, semantic_field, name in pairs:
        if not text:
            continue
        retrievers.append(_lexical(lexical_field, text, name))
        if semantic:
            retrievers.append(_semantic(semantic_field, text, name))
    if a.get("tags"):
        retrievers.append(
            {"standard": {"query": {"terms": {"tags": a["tags"], "_name": "shared_tags"}}}}
        )
    if a.get("groups"):
        retrievers.append(
            {"standard": {"query": {"terms": {"groups": a["groups"], "_name": "shared_groups"}}}}
        )

    return {
        "retriever": {
            "rrf": {
                "retrievers": retrievers,
                "rank_window_size": 50,
                "rank_constant": 20,
                # Never suggest yourself or someone you are already connected to.
                "filter": {"bool": {"must_not": [{"ids": {"values": exclude_ids}}]}},
            }
        },
        "size": size,
        "_source": SOURCE_FIELDS,
    }


def _short(text: str, limit: int = 90) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def explain_why(a: dict, b: dict, matched: set[str]) -> str:
    """One sentence built from which named queries matched. No LLM, so it is always true."""
    if "asks_to_offers" in matched and b.get("offers"):
        return f"They offer what you asked for: “{_short(b['offers'])}”"
    if "offers_to_asks" in matched and b.get("asks"):
        return f"You can help them: they need “{_short(b['asks'])}”"
    shared_tags = sorted(set(a.get("tags", [])) & set(b.get("tags", [])))
    if shared_tags:
        return "You both care about " + ", ".join(shared_tags[:3])
    if "similar_work" in matched:
        return f"You are working on similar things: “{_short(b['working_on'])}”"
    shared_groups = sorted(set(a.get("groups", [])) & set(b.get("groups", [])))
    if shared_groups:
        return f"You are both in {shared_groups[0]}"
    return "Your profiles overlap"


def default_icebreaker(b: dict) -> str:
    """Used when no LLM-written icebreaker exists for the pair."""
    first_name = b["name"].split()[0]
    if b.get("fun_fact"):
        return f"Ask {first_name} about this: {_short(b['fun_fact'])}"
    return f"Ask {first_name} what the hardest part of “{_short(b['working_on'], 60)}” has been."


def find_matches(client: Elasticsearch, a: dict, size: int = 5) -> list[tuple[dict, float, str]]:
    """Run the query for attendee `a`. Returns (other attendee, score, reason) tuples."""
    exclude = [a["id"], *edges.connected_ids(client, a["id"])]
    body = build_match_query(a, exclude, size)
    hits = client.search(index=es.ATTENDEES, body=body)["hits"]["hits"]
    return [
        (
            h["_source"],
            h["_score"] or 0.0,
            explain_why(a, h["_source"], set(h.get("matched_queries", []))),
        )
        for h in hits
    ]
