"""A fault switch for the demo: make the match endpoint slow or failing on purpose,
then find it with Dash0. Off unless CHAOS_ENABLED=true, and changing it needs ADMIN_TOKEN.
State is in memory, which is fine because the API runs as one replica."""

import hmac
import time

from fastapi import APIRouter, Header, HTTPException

from .config import settings
from .models import Chaos

router = APIRouter()
mode = "off"


def apply() -> None:
    """Called inside the match.query span, so the delay shows up exactly there."""
    if mode == "slow":
        time.sleep(1.5)
    elif mode == "error":
        raise HTTPException(503, "Chaos mode: match service unavailable")


@router.get("/api/chaos")
def get_chaos() -> Chaos:
    return Chaos(mode=mode)


@router.post("/api/chaos")
def set_chaos(body: Chaos, x_admin_token: str = Header(default="")) -> Chaos:
    global mode
    allowed = settings.chaos_enabled and settings.admin_token
    if not allowed or not hmac.compare_digest(x_admin_token, settings.admin_token):
        raise HTTPException(403, "Chaos is disabled or the admin token is wrong")
    mode = body.mode
    return Chaos(mode=mode)
