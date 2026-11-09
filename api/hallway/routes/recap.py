from fastapi import APIRouter, Depends

from .. import edges, es
from ..auth import current_attendee
from ..models import Attendee, Recap

router = APIRouter()


@router.get("/api/recap")
def recap(me: dict = Depends(current_attendee)) -> Recap:
    """End of conference: who you met, how many groups you reached, what to do next."""
    client = es.get_client()
    ids = sorted(edges.connected_ids(client, me["id"]))
    if not ids:
        return Recap(connections=[], groups_bridged=0, nudges=[])
    docs = client.mget(index=es.ATTENDEES, ids=ids)["docs"]
    people = [d["_source"] for d in docs if d.get("found")]

    # Bridge score: distinct groups you connected into that you are not a member of.
    reached = {g for p in people for g in p["groups"]} - set(me["groups"])

    nudges = []
    for p in people[:5]:
        first_name = p["name"].split()[0]
        if me["asks"] and p["offers"]:
            nudges.append(f"Take {first_name} up on their offer: {p['offers']}")
        elif p["asks"] and me["offers"]:
            nudges.append(f"Follow through for {first_name}, who needs: {p['asks']}")
        else:
            nudges.append(f"Send {first_name} a note about {p['working_on']}")
    return Recap(
        connections=[Attendee(**p) for p in people], groups_bridged=len(reached), nudges=nudges
    )
