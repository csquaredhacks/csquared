from fastapi import APIRouter, Depends

from .. import chaos, edges, es
from ..auth import current_attendee
from ..matching import default_icebreaker, find_matches_detailed, is_reciprocal
from ..models import Attendee, Match
from ..telemetry import tracer

router = APIRouter()


@router.get("/api/matches")
def matches(me: dict = Depends(current_attendee)) -> list[Match]:
    """Your Five: the people you should meet, why, and how to start talking."""
    client = es.get_client()
    with tracer.start_as_current_span("match.query") as span:
        chaos.apply()
        found = find_matches_detailed(client, me)
        span.set_attribute("match.count", len(found))
    if not found:
        return []

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
