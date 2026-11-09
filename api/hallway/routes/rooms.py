from fastapi import APIRouter, Depends, HTTPException

from .. import es
from ..auth import current_attendee
from ..config import settings
from ..matcher import MAX_ATTENDEES
from ..models import CheckinIn, PathStep, Room
from ..telemetry import set_room_occupancy

router = APIRouter()

RECENT = "now-3h"  # a check-in older than this no longer counts as "in the room"


def current_occupancy() -> list[Room]:
    """One check-in document per attendee (their latest room), grouped by room."""
    hits = es.get_client().search(
        index=es.CHECKINS, query={"range": {"at": {"gte": RECENT}}}, size=MAX_ATTENDEES
    )["hits"]["hits"]
    people: dict[str, list[PathStep]] = {room: [] for room in settings.rooms}
    for h in hits:
        checkin = h["_source"]
        if checkin["room"] in people:
            people[checkin["room"]].append(
                PathStep(id=checkin["attendee_id"], name=checkin["name"])
            )
    # Feeds the hallway.room.occupancy gauge, so the same numbers appear in Dash0.
    set_room_occupancy({room: len(who) for room, who in people.items()})
    return [Room(room=room, count=len(who), people=who[:8]) for room, who in people.items()]


@router.get("/api/rooms")
def rooms() -> list[Room]:
    return current_occupancy()


@router.post("/api/checkins")
def checkin(body: CheckinIn, me: dict = Depends(current_attendee)) -> Room:
    # Only configured rooms: keeps the metric's "room" label to a small fixed set.
    if body.room not in settings.rooms:
        raise HTTPException(400, f"Unknown room. Choose one of: {', '.join(settings.rooms)}")
    doc = {"attendee_id": me["id"], "name": me["name"], "room": body.room, "at": es.now()}
    # Document id = attendee id, so checking in somewhere new moves you instead of cloning you.
    es.get_client().index(index=es.CHECKINS, id=me["id"], document=doc, refresh=True)
    return next(r for r in current_occupancy() if r.room == body.room)
