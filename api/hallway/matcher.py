"""The matchmaking agent. It runs the match query for people and writes the results
into the graph as "suggested" edges, so the big screen shows who SHOULD meet.

Runs in three places:
- right after someone registers (suggest_for, as a background task)
- right after someone edits what they need or offer (resuggest_for, as a background task)
- every two minutes for everyone, as a Kubernetes CronJob:  python -m hallway.matcher
"""

import logging

from elasticsearch import Elasticsearch

from . import edges, es, llm
from .matching import find_matches
from .telemetry import matcher_pairs, tracer

log = logging.getLogger("hallway.matcher")

MAX_ATTENDEES = 2000


def suggest_for(
    client: Elasticsearch, a: dict, use_llm: bool = True, semantic: bool | None = None
) -> int:
    """Write a suggested edge to each of this attendee's top matches. Returns how many were new."""
    new = 0
    for other, _score, reason in find_matches(client, a, semantic=semantic):
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


def resuggest_for(client: Elasticsearch, a: dict) -> int:
    """After a profile edit: drop this person's old suggestions, then suggest again.
    A suggested edge stores its reason as text that quotes asks and offers, so an old one
    would keep showing words the person has since changed or removed. Suggestions other
    people had for this person come back on the next scheduled run."""
    touches_me = [{"term": {"source": a["id"]}}, {"term": {"target": a["id"]}}]
    client.delete_by_query(
        index=es.EDGES,
        query={
            "bool": {
                "filter": [{"term": {"kind": "suggested"}}],
                "should": touches_me,
                "minimum_should_match": 1,
            }
        },
        refresh=True,
        conflicts="proceed",
    )
    return suggest_for(client, a)


def run_once(client: Elasticsearch, llm_budget: int = 30) -> int:
    """One pass over every attendee. `llm_budget` caps LLM calls per run so a big
    first run (60 seeded people) finishes in seconds, not minutes."""
    with tracer.start_as_current_span("matcher.run") as span:
        hits = client.search(index=es.ATTENDEES, query={"match_all": {}}, size=MAX_ATTENDEES)
        attendees = [h["_source"] for h in hits["hits"]["hits"]]
        total = 0
        failed = 0
        for a in attendees:
            try:
                # Keywords only. This pass asks about everyone every two minutes; with the
                # semantic half on, it used up the ELSER trial quota that a person's own
                # "Your five" needs. People still get hybrid matching when they register,
                # edit their profile, and open their five.
                new = suggest_for(client, a, use_llm=llm_budget > 0, semantic=False)
            except Exception as error:  # noqa: BLE001 - one person must not stop the pass
                failed += 1
                log.warning("matcher: skipped one attendee: %s", error)
                continue
            llm_budget -= new
            total += new
        span.set_attribute("matcher.failed", failed)
        span.set_attribute("matcher.attendees", len(attendees))
        span.set_attribute("matcher.new_pairs", total)
        log.info("matcher: %d attendees, %d new suggested pairs", len(attendees), total)
        return total


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    es_client = es.get_client()
    es.ensure_indices_with_retry(es_client)
    run_once(es_client)
