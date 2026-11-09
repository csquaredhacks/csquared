"""Hallway: one process serves the JSON API and the built web app."""

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import chaos, es
from .config import settings
from .models import Health
from .routes import attendees, edges, graph, matches, recap, rooms

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Create indices in the background so the pod starts (and /healthz answers)
    # even if Elasticsearch is slow or unreachable for the first minute.
    threading.Thread(
        target=es.ensure_indices_with_retry, args=(es.get_client(),), daemon=True
    ).start()
    yield


app = FastAPI(title="Hallway", lifespan=lifespan)
for module in (attendees, matches, edges, graph, rooms, recap, chaos):
    app.include_router(module.router)


@app.get("/healthz")
def healthz() -> Health:
    """Always 200 while the process is alive; `es` says whether the datastore is reachable."""
    try:
        reachable = es.get_client().ping()
    except Exception:  # noqa: BLE001
        reachable = False
    return Health(ok=True, es="green" if reachable else "red")


# --- the web app (built by Vite into web/dist) ---------------------------------------
dist = settings.web_dist.resolve()
if (dist / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

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
