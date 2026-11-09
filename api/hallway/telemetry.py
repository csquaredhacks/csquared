"""Custom spans and metrics. Auto-instrumentation (HTTP, Elasticsearch, logs) comes from
running the process under `opentelemetry-instrument`; without it these calls are no-ops."""

import time
from collections.abc import Callable

from opentelemetry import metrics, trace
from opentelemetry.metrics import CallbackOptions, Observation

tracer = trace.get_tracer("hallway")
meter = metrics.get_meter("hallway")

edges_total = meter.create_counter(
    "hallway.edges.total", description="Edges written, by kind (connected or suggested)"
)
matcher_pairs = meter.create_counter(
    "hallway.matcher.pairs", description="New suggested pairs written by the matcher"
)
crew_joins = meter.create_counter(
    "hallway.crew.joins", description="People who accepted an arrival group"
)

# The two gauges below are filled when someone opens the room map or the organizer board.
# So that Dash0 still gets numbers when nobody has those pages open (and right after a
# restart), main.py registers a function per gauge that recomputes it from Elasticsearch.
# It runs at most every REFRESH_SECONDS, just before the gauge is exported.
REFRESH_SECONDS = 30
refreshers: dict[str, Callable[[], object]] = {}
_refreshed_at: dict[str, float] = {}


def _refresh(name: str) -> None:
    recompute = refreshers.get(name)
    if recompute is None or time.monotonic() - _refreshed_at.get(name, -REFRESH_SECONDS) < (
        REFRESH_SECONDS
    ):
        return
    _refreshed_at[name] = time.monotonic()
    try:
        recompute()
    except Exception:  # noqa: BLE001 - a metric must never break; keep the last values
        pass


_room_occupancy: dict[str, int] = {}


def set_room_occupancy(values: dict[str, int]) -> None:
    """Called whenever occupancy is computed; the gauge below reports the latest values."""
    _room_occupancy.clear()
    _room_occupancy.update(values)


def _observe_rooms(_: CallbackOptions):
    _refresh("rooms")
    return [Observation(count, {"room": room}) for room, count in _room_occupancy.items()]


meter.create_observable_gauge(
    "hallway.room.occupancy", callbacks=[_observe_rooms], description="People checked in, by room"
)

_funnel: dict[str, int] = {}


def set_funnel(values: dict[str, int]) -> None:
    """Called whenever the organizer board is computed. Stage names are a small fixed
    set; no attendee id, affiliation or free text is ever a label."""
    _funnel.clear()
    _funnel.update(values)


def _observe_funnel(_: CallbackOptions):
    _refresh("funnel")
    return [Observation(count, {"stage": stage}) for stage, count in _funnel.items()]


meter.create_observable_gauge(
    "hallway.funnel",
    callbacks=[_observe_funnel],
    description="People or pairs at each stage: registered, in_group, planned, met, checked_in",
)


def tag_attendee(attendee_id: str) -> None:
    """Put the attendee id on the current span so any trace can be found by person."""
    trace.get_current_span().set_attribute("attendee.id", attendee_id)
