from elasticsearch import NotFoundError
from fastapi import APIRouter, Depends, HTTPException

from .. import edges, es
from ..auth import current_attendee
from ..models import Attendee, ConnectResult, Edge, EdgeIn

router = APIRouter()


@router.post("/api/edges")
def connect(body: EdgeIn, me: dict = Depends(current_attendee)) -> ConnectResult:
    """Called when I scan someone's QR. Scanning twice is harmless (created=false)."""
    if body.to_id == me["id"]:
        raise HTTPException(400, "You cannot connect with yourself")
    client = es.get_client()
    try:
        other = client.get(index=es.ATTENDEES, id=body.to_id)["_source"]
    except NotFoundError:
        raise HTTPException(404, "No such attendee") from None

    # Remember whether the two had agreed to meet beforehand: the recap and the
    # dashboard can then tell planned meetings that happened from chance ones.
    had_plan = bool(
        client.exists(index=es.EDGES, id=edges.edge_id(me["id"], other["id"], "planned"))
    )
    edge, created = edges.upsert_edge(
        client, me["id"], other["id"], "connected", "Met at the conference", planned=had_plan
    )
    # The suggestion, invitation or plan has done its job: only "met" remains.
    edges.delete_between(client, me["id"], other["id"], ["suggested", "invited", "planned"])
    return ConnectResult(edge=Edge(**edge), created=created, other=Attendee(**other))
