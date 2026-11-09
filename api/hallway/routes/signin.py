"""The sign in buttons. How the flow works is explained at the top of ../signin.py."""

import logging

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from .. import es, signin
from ..auth import set_session
from ..models import PendingSignin

log = logging.getLogger("hallway.signin")
router = APIRouter()


def _must_be_configured(provider: str) -> None:
    if provider not in signin.configured():
        raise HTTPException(404, "That sign in is not set up on this server")


def _back_to_form(error: str = "") -> RedirectResponse:
    """Every callback ends on the join page. 303 so the browser makes a plain GET."""
    response = RedirectResponse(f"/?signin_error={error}" if error else "/", status_code=303)
    response.delete_cookie(signin.STATE_COOKIE)  # a state is used once
    return response


# Declared before "/api/signin/{provider}", or "pending" would be read as a provider.
@router.get("/api/signin/pending")
def pending_signin(request: Request) -> PendingSignin | None:
    """Who just signed in and still has to send the profile form. null when nobody did."""
    identity = signin.pending(request)
    return PendingSignin(**identity) if identity else None


@router.delete("/api/signin/pending", status_code=204)
def forget_pending_signin(response: Response) -> None:
    """ "Change": go back to the plain form, as if the button was never pressed."""
    response.delete_cookie(signin.PENDING_COOKIE)


@router.get("/api/signin/{provider}", include_in_schema=False)
def start(provider: str, request: Request) -> RedirectResponse:
    """A plain link, not a fetch: the browser itself has to go to the provider."""
    _must_be_configured(provider)
    state = signin.new_state()
    redirect = signin.redirect_uri(request, provider)
    response = RedirectResponse(signin.authorize_url(provider, redirect, state))
    signin.remember_state(response, provider, state)
    return response


@router.get("/api/signin/{provider}/callback", include_in_schema=False)
def callback(
    provider: str, request: Request, code: str = "", state: str = "", error: str = ""
) -> RedirectResponse:
    _must_be_configured(provider)
    if not signin.state_matches(request, provider, state):
        return _back_to_form("failed")
    if error or not code:  # the person pressed Cancel on the provider's page
        return _back_to_form("cancelled")
    try:
        identity = signin.fetch_identity(provider, code, signin.redirect_uri(request, provider))
    except signin.SigninFailed as failure:
        log.warning("sign in with %s failed: %s", provider, failure)
        return _back_to_form("failed")

    response = _back_to_form()
    doc = signin.find_attendee(es.get_client(), provider, identity["sub"])
    if doc:
        # Been here before: same profile, on any device.
        set_session(response, doc)
        response.delete_cookie(signin.PENDING_COOKIE)
    else:
        # New here: the join page fills in the name, and the profile form finishes it.
        signin.set_pending(response, provider, identity)
    return response
