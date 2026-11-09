"""Sign in with Google or LinkedIn (OpenID Connect, authorization code flow).

1. The button opens /api/signin/<provider>. We send the browser to the provider with a
   random `state`, and keep the same state in a short-lived cookie.
2. The provider sends the browser back to /api/signin/<provider>/callback with a `code`
   and the state. The state must match the cookie, so nobody can finish a sign in that
   this browser did not start.
3. We swap the code for an access token and ask the provider who this is. We keep two
   things: the provider's id for the person (`sub`) and their name.
4. If an attendee already has that id, they get their session back. Otherwise we
   remember the sign in in a signed cookie until they send the profile form.

Hallway keeps no email address, no picture and no token from the provider."""

import base64
import hashlib
import hmac
import json
import secrets
import time
from urllib.parse import urlencode

import httpx
from elasticsearch import Elasticsearch
from fastapi import Request, Response

from . import es
from .config import settings

# Taken from each provider's /.well-known/openid-configuration.
PROVIDERS = {
    "linkedin": {
        "authorize": "https://www.linkedin.com/oauth/v2/authorization",
        "token": "https://www.linkedin.com/oauth/v2/accessToken",
        "userinfo": "https://api.linkedin.com/v2/userinfo",
    },
    "google": {
        "authorize": "https://accounts.google.com/o/oauth2/v2/auth",
        "token": "https://oauth2.googleapis.com/token",
        "userinfo": "https://openidconnect.googleapis.com/v1/userinfo",
    },
}
SCOPE = "openid profile"  # enough for an id and a name; we do not ask for the email

STATE_COOKIE = "hallway_signin_state"
STATE_SECONDS = 10 * 60  # time to get through the provider's page
PENDING_COOKIE = "hallway_signin_pending"
PENDING_SECONDS = 60 * 60  # time to fill in the profile form


class SigninFailed(Exception):
    """The provider did not give us an id for this person."""


def credentials(provider: str) -> tuple[str, str]:
    """(client id, client secret) from the environment; empty when not set up."""
    if provider == "google":
        return settings.google_client_id, settings.google_client_secret
    if provider == "linkedin":
        return settings.linkedin_client_id, settings.linkedin_client_secret
    return "", ""


def configured() -> list[str]:
    """The providers whose buttons can work on this server."""
    return [provider for provider in PROVIDERS if all(credentials(provider))]


def redirect_uri(request: Request, provider: str) -> str:
    """Where the provider sends the browser back to. It must be the same address that
    is registered with the provider, character for character."""
    base = settings.public_url
    if not base:
        # Behind the tunnel the request reaches us as plain http; the header has the
        # scheme the browser really used.
        scheme = request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0].strip()
        base = f"{scheme}://{request.headers['host']}"
    return f"{base}/api/signin/{provider}/callback"


def authorize_url(provider: str, redirect: str, state: str) -> str:
    query = {
        "response_type": "code",
        "client_id": credentials(provider)[0],
        "redirect_uri": redirect,
        "scope": SCOPE,
        "state": state,
    }
    return f"{PROVIDERS[provider]['authorize']}?{urlencode(query)}"


def fetch_identity(provider: str, code: str, redirect: str) -> dict:
    """Swap the code for an access token, then ask the provider who this is.
    Returns {"sub": the provider's id for the person, "name": their name}."""
    client_id, client_secret = credentials(provider)
    form = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    try:
        token = httpx.post(PROVIDERS[provider]["token"], data=form, timeout=10)
        token.raise_for_status()
        who = httpx.get(
            PROVIDERS[provider]["userinfo"],
            headers={"Authorization": f"Bearer {token.json()['access_token']}"},
            timeout=10,
        )
        who.raise_for_status()
        profile = who.json()
        sub = str(profile["sub"])
    except (httpx.HTTPError, KeyError, ValueError, TypeError) as error:
        # Only the kind of error: the response body could hold a token.
        raise SigninFailed(type(error).__name__) from None
    return {"sub": sub, "name": str(profile.get("name") or "").strip()}


def find_attendee(client: Elasticsearch, provider: str, sub: str) -> dict | None:
    """The attendee who joined with this provider account, if there is one."""
    query = {
        "bool": {"filter": [{"term": {"signin_provider": provider}}, {"term": {"signin_sub": sub}}]}
    }
    hits = client.search(index=es.ATTENDEES, query=query, size=1)["hits"]["hits"]
    return hits[0]["_source"] if hits else None


# --- cookies ----------------------------------------------------------------------------


def _set_cookie(response: Response, name: str, value: str, seconds: int) -> None:
    response.set_cookie(
        name,
        value,
        max_age=seconds,
        httponly=True,
        samesite="lax",  # still sent when the provider sends the browser back to us
        secure=settings.cookie_secure,
    )


def new_state() -> str:
    return secrets.token_urlsafe(24)


def remember_state(response: Response, provider: str, state: str) -> None:
    _set_cookie(response, STATE_COOKIE, f"{provider}.{state}", STATE_SECONDS)


def state_matches(request: Request, provider: str, state: str) -> bool:
    expected = request.cookies.get(STATE_COOKIE, "")
    return bool(state) and hmac.compare_digest(expected, f"{provider}.{state}")


def _signature(provider: str, payload: str) -> str:
    """Signed with the provider's client secret, which only this server knows, so a
    browser cannot write its own "I signed in as ..." cookie."""
    key = credentials(provider)[1].encode()
    return hmac.new(key, f"hallway-pending:{payload}".encode(), hashlib.sha256).hexdigest()


def set_pending(response: Response, provider: str, identity: dict) -> None:
    """Remember a sign in that has no profile yet, until the form is sent."""
    data = {"provider": provider, **identity, "expires": int(time.time()) + PENDING_SECONDS}
    payload = base64.urlsafe_b64encode(json.dumps(data).encode()).decode()
    value = f"{payload}.{_signature(provider, payload)}"
    _set_cookie(response, PENDING_COOKIE, value, PENDING_SECONDS)


def pending(request: Request) -> dict | None:
    """The sign in waiting for its profile form: {provider, sub, name}, or None."""
    payload, _, signature = request.cookies.get(PENDING_COOKIE, "").partition(".")
    try:
        data = json.loads(base64.urlsafe_b64decode(payload))
        provider = data["provider"]
        valid = provider in configured() and hmac.compare_digest(
            signature, _signature(provider, payload)
        )
        if not valid or data["expires"] < time.time():
            return None
        return {"provider": provider, "sub": data["sub"], "name": data["name"]}
    except (ValueError, KeyError, TypeError):
        return None
