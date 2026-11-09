"""Arrival groups. See hallway/crews.py for the rules."""

from fastapi import APIRouter, Depends, HTTPException

from .. import crews, es
from ..auth import current_attendee
from ..models import AcceptIn, Attendee, Crew, CrewOut, Meeting, MeetingIn

router = APIRouter()


def _out(me: dict, crew: dict | None) -> CrewOut:
    if crew is None:
        return CrewOut(status="none", crew=None)
    client = es.get_client()
    members = crews.load_people(client, crew["members"])
    status = "member" if me["id"] in crew["members"] else "suggested"
    # Limit as it would be for me: a suggestion shows the size I would actually join.
    limit = crews.crew_limit(members if status == "member" else [*members, me])
    return CrewOut(
        status=status,
        crew=Crew(
            id=crew["id"],
            members=[Attendee(**m) for m in members],
            seats_taken=crews.seats_taken(crew),
            limit=limit,
            why=crews.why(members if status == "member" else [*members, me]),
            meeting=Meeting(**crew["meeting"]) if crew.get("meeting") else None,
        ),
        bringing_companion=me["id"] in crew.get("companions", []),
    )


def _run(action):
    try:
        return action()
    except crews.CrewError as error:
        raise HTTPException(error.status, error.message) from None


@router.get("/api/crew")
def get_crew(me: dict = Depends(current_attendee)) -> CrewOut:
    """My crew if I accepted one, else my pending suggestion, else none."""
    client = es.get_client()
    return _out(me, crews.crew_of(client, me["id"]) or crews.pending_for(client, me["id"]))


@router.post("/api/crew/suggest")
def suggest_crew(me: dict = Depends(current_attendee)) -> CrewOut:
    """Ask for a suggestion. Changes nothing if I already have a crew or a suggestion."""
    return _out(me, _run(lambda: crews.suggest(es.get_client(), me)))


@router.post("/api/crew/accept")
def accept_crew(body: AcceptIn, me: dict = Depends(current_attendee)) -> CrewOut:
    return _out(me, _run(lambda: crews.accept(es.get_client(), me, body.companion)))


@router.post("/api/crew/decline")
def decline_crew(me: dict = Depends(current_attendee)) -> CrewOut:
    _run(lambda: crews.decline(es.get_client(), me))
    return CrewOut(status="none", crew=None)


@router.delete("/api/crew")
def leave_crew(me: dict = Depends(current_attendee)) -> CrewOut:
    """Leave (or decline). You are not reassigned; ask for a new suggestion when ready."""
    _run(lambda: crews.leave(es.get_client(), me))
    return CrewOut(status="none", crew=None)


@router.put("/api/crew/meeting")
def set_meeting(body: MeetingIn, me: dict = Depends(current_attendee)) -> CrewOut:
    starts_at = body.starts_at.isoformat(timespec="minutes")
    return _out(
        me,
        _run(lambda: crews.set_meeting(es.get_client(), me, body.place, starts_at, body.timezone)),
    )
