"""The matchmaking agent. It runs the match query for people and writes the results
into the graph as "suggested" edges, so the big screen shows who SHOULD meet.

Runs in two places:
- right after someone registers (suggest_for, as a background task)
- every two minutes for everyone, as a Kubernetes CronJob:  python -m hallway.matcher
"""

import logging

from elasticsearch import Elasticsearch

from . import edges, es, llm
from .matching import find_matches
from .telemetry import matcher_pairs, tracer

log = logging.getLogger("hallway.matcher")

MAX_ATTENDEES = 2000


def suggest_for(client: Elasticsearch, a: dict, use_llm: bool = True) -> int:
    """Write a suggested edge to each of this attendee's top matches. Returns how many were new."""
    new = 0
    for other, _score, reason in find_matches(client, a):
        doc_id = edges.edge_id(a["id"], other["id"], "suggested")
        if client.exists(index=es.EDGES, id=doc_id):
            continue
        icebreaker = llm.icebreaker(a, other, reason) if use_llm else ""
        _edge, created = edges.upsert_edge(
            client, a["id"], other["id"], "suggested", reason, icebreaker
        )
        new += created
    if new:
        matcher_pairs.add(new)
    return new


def run_once(client: Elasticsearch, llm_budget: int = 30) -> int:
    """One pass over every attendee. `llm_budget` caps LLM calls per run so a big
    first run (60 seeded people) finishes in seconds, not minutes."""
    with tracer.start_as_current_span("matcher.run") as span:
        hits = client.search(index=es.ATTENDEES, query={"match_all": {}}, size=MAX_ATTENDEES)
        attendees = [h["_source"] for h in hits["hits"]["hits"]]
        total = 0
        for a in attendees:
            new = suggest_for(client, a, use_llm=llm_budget > 0)
            llm_budget -= new
            total += new
        span.set_attribute("matcher.attendees", len(attendees))
        span.set_attribute("matcher.new_pairs", total)
        log.info("matcher: %d attendees, %d new suggested pairs", len(attendees), total)
        return total


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    es_client = es.get_client()
    es.ensure_indices_with_retry(es_client)
    run_once(es_client)
