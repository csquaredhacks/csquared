"""Identity without accounts. Registering sets one cookie: "<attendee id>.<secret>".
The id is public (it is inside your QR code); the secret never leaves the cookie,
so knowing someone's id is not enough to act as them."""

import hmac

from elasticsearch import NotFoundError
from fastapi import HTTPException, Request, Response

from . import es
from .config import settings
from .telemetry import tag_attendee

COOKIE = "hallway_session"
WEEK = 7 * 24 * 3600


def set_session(response: Response, doc: dict) -> None:
    response.set_cookie(
        COOKIE,
        f"{doc['id']}.{doc['secret']}",
        max_age=WEEK,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
    )


def current_attendee(request: Request) -> dict:
    """FastAPI dependency: the stored attendee document for the session cookie, or 401."""
    attendee_id, _, secret = request.cookies.get(COOKIE, "").partition(".")
    if not attendee_id or not secret:
        raise HTTPException(401, "Not registered yet")
    try:
        # A GET by id is real-time, so this works the instant after registering.
        doc = es.get_client().get(index=es.ATTENDEES, id=attendee_id)["_source"]
    except NotFoundError:
        raise HTTPException(401, "Not registered yet") from None
    if not hmac.compare_digest(doc["secret"], secret):
        raise HTTPException(401, "Not registered yet")
    tag_attendee(attendee_id)
    return doc


def optional_attendee(request: Request) -> dict | None:
    """For public pages that show a little more to a signed-in person: their attendee
    document, or None for a visitor. A missing or stale cookie is not an error here."""
    try:
        return current_attendee(request)
    except HTTPException:
        return None
