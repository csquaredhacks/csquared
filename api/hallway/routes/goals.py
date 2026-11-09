"""A personal goal board. Goals are private: they are stored on my own attendee document
and returned only to me. Nothing completes a goal except me saying so; meeting someone
or scanning a code never ticks one off."""

from fastapi import APIRouter, Depends

from .. import es
from ..auth import current_attendee
from ..models import Goals

router = APIRouter()


@router.get("/api/goals")
def get_goals(me: dict = Depends(current_attendee)) -> Goals:
    return Goals(goals=me.get("goals", []))


@router.put("/api/goals")
def set_goals(body: Goals, me: dict = Depends(current_attendee)) -> Goals:
    """Replace my whole list: add, reword, tick, untick and remove are all this one call."""
    goals = [goal.model_dump() for goal in body.goals]
    es.get_client().update(index=es.ATTENDEES, id=me["id"], doc={"goals": goals}, refresh=True)
    return Goals(goals=goals)
