"""Hallway: one process serves the JSON API and the built web app."""

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import chaos, es, telemetry
from . import crowd as crowd_counts
from .config import settings
from .models import Health
from .routes import (
    attendees,
    communities,
    crews,
    crowd,
    edges,
    goals,
    graph,
    matches,
    recap,
    rooms,
    signin,
)

logging.basicConfig(level=logging.INFO)

_indices_ready = threading.Event()


def _initialize_indices() -> None:
    if es.ensure_indices_with_retry(es.get_client(), seconds=None):
        _indices_ready.set()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Create indices in the background so the pod starts (and /healthz answers)
    # even if Elasticsearch is slow or unreachable for the first minute.
    threading.Thread(target=_initialize_indices, daemon=True).start()
    yield


# Keep the two product gauges fresh in Dash0 even when nobody has their page open.
# Both refreshes run while metrics are being exported, so they use a client that gives
# up after two seconds: a slow Elasticsearch must not hold back every other metric.
def _fast_client():
    return es.get_client().options(request_timeout=2, max_retries=0)


def _refresh_rooms() -> None:
    rooms.current_occupancy(_fast_client())


def _refresh_funnel() -> None:
    crowd_counts.refresh_funnel(_fast_client())


telemetry.refreshers["rooms"] = _refresh_rooms
telemetry.refreshers["funnel"] = _refresh_funnel

app = FastAPI(title="Hallway", lifespan=lifespan)
for module in (
    attendees, communities, matches, edges, graph, rooms, recap, crews, crowd, goals, chaos,
    signin,
):
    app.include_router(module.router)


@app.get("/healthz")
def healthz() -> Health:
    """Always 200 while alive; `es` is green when ES responds and the required indices exist."""
    try:
        client = es.get_client()
        ready = _indices_ready.is_set() and client.ping() and client.indices.exists(
            index=[es.ATTENDEES, es.EDGES, es.CHECKINS, es.CREWS, es.COMMUNITIES]
        )
    except Exception:  # noqa: BLE001
        ready = False
    return Health(ok=True, es="green" if ready else "red")


# --- the web app (built by Vite into web/dist) ---------------------------------------
dist = settings.web_dist.resolve()
if (dist / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")
    welcome = dist / "welcome"
    if (welcome / "index.html").is_file():
        app.mount("/welcome", StaticFiles(directory=welcome, html=True), name="welcome")

    @app.get("/{path:path}", include_in_schema=False)
    def web(path: str):
        """Serve a real file if there is one; otherwise index.html, so client-side
        routes like /connect/abc123 work when opened straight from a QR scan."""
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        file = (dist / path).resolve()
        if path and file.is_file() and dist in file.parents:
            return FileResponse(file)
        return FileResponse(dist / "index.html")
