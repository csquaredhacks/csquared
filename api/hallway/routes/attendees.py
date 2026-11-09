import secrets

from elasticsearch import NotFoundError
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response

from .. import es, matcher, signin
from ..auth import current_attendee, set_session
from ..config import settings
from ..models import Attendee, AttendeeIn, Config, Me, MeUpdate, RecoverIn, Rum
from ..telemetry import tag_attendee

router = APIRouter()

# No 0/O or 1/I/L: the code gets read off one phone and typed into another.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
# The profile fields the match query reads. An edit to any of them changes the matches.
MATCHING_FIELDS = ["working_on", "asks", "offers", "tags", "groups"]


@router.get("/api/config")
def config() -> Config:
    rum = None
    if settings.rum_url and settings.rum_token:
        rum = Rum(url=settings.rum_url, token=settings.rum_token)
    return Config(
        rooms=settings.rooms,
        chaos_enabled=settings.chaos_enabled,
        rum=rum,
        signin=signin.configured(),
    )


@router.post("/api/attendees", status_code=201)
def register(
    body: AttendeeIn, request: Request, response: Response, background: BackgroundTasks
) -> Me:
    client = es.get_client()
    doc = body.model_dump() | {
        "id": secrets.token_hex(6),
        "secret": secrets.token_urlsafe(24),
        "recovery_code": "".join(secrets.choice(CODE_ALPHABET) for _ in range(6)),
        "created_at": es.now(),
    }
    # Did this browser just sign in with Google or LinkedIn? Then the new profile belongs
    # to that account, and the next sign in with it opens this profile.
    identity = signin.pending(request)
    if identity:
        if signin.find_attendee(client, identity["provider"], identity["sub"]):
            raise HTTPException(409, "That account already has a profile. Sign in again to open it")
        doc |= {"signin_provider": identity["provider"], "signin_sub": identity["sub"]}
        response.delete_cookie(signin.PENDING_COOKIE)  # used once
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
def update_me(
    body: MeUpdate, background: BackgroundTasks, doc: dict = Depends(current_attendee)
) -> Me:
    """Change my own profile: what I need and offer, and what I show publicly. Turning a
    public choice off removes that information from the public graph on its next load."""
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if not changes:
        return Me(**doc)
    client = es.get_client()
    # A partial update through the Update API re-indexes the whole merged document, so the
    # semantic copies of working_on, asks and offers (copy_to in the mapping) are rebuilt
    # exactly as they are at registration. refresh=True: matching sees the edit at once.
    client.update(index=es.ATTENDEES, id=doc["id"], doc=changes, refresh=True)
    updated = doc | changes
    if any(updated.get(field) != doc.get(field) for field in MATCHING_FIELDS):
        # Who this person should meet has changed, so the matcher looks again.
        background.add_task(matcher.resuggest_for, client, updated)
    return Me(**updated)


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
