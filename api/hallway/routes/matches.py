from fastapi import APIRouter, Depends

from .. import chaos, edges, es
from ..auth import current_attendee
from ..matching import default_icebreaker, find_matches_detailed, is_reciprocal
from ..models import Attendee, Match
from ..telemetry import tracer

router = APIRouter()

SHOWN = 5  # people on the page
CANDIDATES = 15  # how many Elasticsearch is asked for, so the sort below has something to sort


@router.get("/api/matches")
def matches(me: dict = Depends(current_attendee)) -> list[Match]:
    """Your Five: the people you should meet, why, and how to start talking."""
    client = es.get_client()
    with tracer.start_as_current_span("match.query") as span:
        chaos.apply()
        found = find_matches_detailed(client, me, size=CANDIDATES)
        span.set_attribute("match.count", len(found))
    if not found:
        return []

    # Matches that work both ways first. sorted() is stable, so inside each group the people
    # stay in Elasticsearch's own order; the cap comes after the sort, so a two-way match is
    # never pushed off the page by one-way matches that happened to score higher.
    found = sorted(found, key=lambda hit: not is_reciprocal(hit[3]))[:SHOWN]

    # The matcher may already have stored an LLM-written icebreaker for a pair.
    ids = [edges.edge_id(me["id"], other["id"], "suggested") for other, _, _, _ in found]
    stored = client.mget(index=es.EDGES, ids=ids)["docs"]
    icebreakers = [d["_source"]["icebreaker"] if d.get("found") else "" for d in stored]

    return [
        Match(
            attendee=Attendee(**other),
            score=score,
            reason=reason,
            icebreaker=icebreaker or default_icebreaker(other),
            is_reciprocal=is_reciprocal(matched),
        )
        for (other, score, reason, matched), icebreaker in zip(found, icebreakers, strict=True)
    ]
