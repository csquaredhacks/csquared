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

    edge, created = edges.upsert_edge(
        client, me["id"], other["id"], "connected", reason="Met at the conference"
    )
    # The dashed "you should meet" line has done its job: replace it with the solid one.
    edges.delete_edge(client, me["id"], other["id"], "suggested")
    return ConnectResult(edge=Edge(**edge), created=created, other=Attendee(**other))
