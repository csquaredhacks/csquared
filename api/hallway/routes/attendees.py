import secrets

from elasticsearch import NotFoundError
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response

from .. import es, matcher
from ..auth import current_attendee, set_session
from ..config import settings
from ..models import Attendee, AttendeeIn, Config, Me, MeUpdate, RecoverIn, Rum
from ..telemetry import tag_attendee

router = APIRouter()

# No 0/O or 1/I/L: the code gets read off one phone and typed into another.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


@router.get("/api/config")
def config() -> Config:
    rum = None
    if settings.rum_url and settings.rum_token:
        rum = Rum(url=settings.rum_url, token=settings.rum_token)
    return Config(rooms=settings.rooms, chaos_enabled=settings.chaos_enabled, rum=rum)


@router.post("/api/attendees", status_code=201)
def register(body: AttendeeIn, response: Response, background: BackgroundTasks) -> Me:
    client = es.get_client()
    doc = body.model_dump() | {
        "id": secrets.token_hex(6),
        "secret": secrets.token_urlsafe(24),
        "recovery_code": "".join(secrets.choice(CODE_ALPHABET) for _ in range(6)),
        "created_at": es.now(),
    }
    # refresh=True: the new person is searchable immediately, so they can be matched
    # and recovered right away. Fine at conference write volumes.
    client.index(index=es.ATTENDEES, id=doc["id"], document=doc, refresh=True)
    tag_attendee(doc["id"])
    set_session(response, doc)
    # The matchmaking agent draws this person's suggested edges on the graph right away.
    background.add_task(matcher.suggest_for, client, doc)
    return Me(**doc)


@router.get("/api/me")
def me(doc: dict = Depends(current_attendee)) -> Me:
    return Me(**doc)


@router.patch("/api/me")
def update_me(body: MeUpdate, doc: dict = Depends(current_attendee)) -> Me:
    """Change what I show publicly. Turning a choice off removes that information from
    the public graph on its very next load."""
    changes = body.model_dump(exclude_none=True)
    if changes:
        es.get_client().update(index=es.ATTENDEES, id=doc["id"], doc=changes, refresh=True)
    return Me(**(doc | changes))


@router.post("/api/recover")
def recover(body: RecoverIn, response: Response) -> Me:
    query = {"term": {"recovery_code": body.code.upper()}}
    hits = es.get_client().search(index=es.ATTENDEES, query=query, size=1)["hits"]["hits"]
    if not hits:
        raise HTTPException(404, "No attendee has that recovery code")
    doc = hits[0]["_source"]
    set_session(response, doc)
    return Me(**doc)


@router.get("/api/attendees/{attendee_id}")
def get_attendee(attendee_id: str) -> Attendee:
    try:
        doc = es.get_client().get(index=es.ATTENDEES, id=attendee_id)["_source"]
    except NotFoundError:
        raise HTTPException(404, "No such attendee") from None
    return Attendee(**doc)
