"""The organizer board. See hallway/crowd.py for what is counted and what is left out."""

from fastapi import APIRouter

from .. import crowd, es
from ..models import Crowd

router = APIRouter()


@router.get("/api/crowd")
def get_crowd() -> Crowd:
    """Public on purpose: it holds counts only, never a person."""
    return Crowd(**crowd.board(es.get_client()))
