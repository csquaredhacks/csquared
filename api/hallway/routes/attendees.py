import secrets
from collections import deque
from math import ceil
from threading import Lock
from time import monotonic

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
# The profile fields the match query reads. An edit to any of them changes the matches.
MATCHING_FIELDS = ["working_on", "asks", "offers", "tags", "groups"]

# One shared budget for the single-process, single-replica Helm deployment. The
# Cloudflare tunnel is a separate proxy; do not key on untrusted forwarding headers.
# Exhausting this budget temporarily blocks everyone's recovery, including valid codes.
# State resets on restart and is independent per worker/replica. Scaling requires a
# shared limiter (and explicitly trusted proxy configuration for per-client limits).
RECOVERY_FAILURE_LIMIT = 10
RECOVERY_WINDOW_SECONDS = 60
_recovery_failures: deque[float] = deque(maxlen=RECOVERY_FAILURE_LIMIT)
_recovery_lock = Lock()


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
    # Serialize the check, lookup and failure accounting so concurrent guesses cannot
    # all pass the budget check before any failures have been recorded.
    with _recovery_lock:
        now = monotonic()
        while _recovery_failures and _recovery_failures[0] <= now - RECOVERY_WINDOW_SECONDS:
            _recovery_failures.popleft()
        if len(_recovery_failures) >= RECOVERY_FAILURE_LIMIT:
            retry_after = ceil(_recovery_failures[0] + RECOVERY_WINDOW_SECONDS - now)
            raise HTTPException(
                429,
                "Too many failed recovery attempts. Try again shortly.",
                headers={"Retry-After": str(retry_after)},
            )
        query = {"term": {"recovery_code": body.code.upper()}}
        hits = es.get_client().search(index=es.ATTENDEES, query=query, size=1)["hits"]["hits"]
        if not hits:
            _recovery_failures.append(monotonic())
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
