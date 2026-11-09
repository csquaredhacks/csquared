"""Elasticsearch is the only datastore: three indices, created on startup."""

import logging
import time
from datetime import UTC, datetime
from functools import lru_cache

from elasticsearch import Elasticsearch

from .config import settings

log = logging.getLogger("hallway.es")

ATTENDEES = f"{settings.index_prefix}-attendees"
EDGES = f"{settings.index_prefix}-edges"
CHECKINS = f"{settings.index_prefix}-checkins"


def now() -> str:
    """UTC ISO-8601, the only timestamp format we store."""
    return datetime.now(UTC).isoformat(timespec="seconds")


@lru_cache
def get_client() -> Elasticsearch:
    return Elasticsearch(settings.es_url, api_key=settings.es_api_key or None, request_timeout=15)


def attendee_mapping(elser_id: str) -> dict:
    """Plain text fields for BM25, plus (when ELSER is configured) semantic_text copies
    of the same text, so one document can be searched both ways."""
    props: dict = {
        "id": {"type": "keyword"},
        "secret": {"type": "keyword", "index": False},
        "recovery_code": {"type": "keyword"},
        "name": {"type": "text"},
        "working_on": {"type": "text"},
        "asks": {"type": "text"},
        "offers": {"type": "text"},
        "fun_fact": {"type": "text"},
        "tags": {"type": "keyword"},
        "groups": {"type": "keyword"},
        "comfort": {"type": "keyword"},
        "on_graph": {"type": "boolean"},
        "created_at": {"type": "date"},
    }
    if elser_id:
        for source, target in [
            ("working_on", "profile_semantic"),
            ("asks", "asks_semantic"),
            ("offers", "offers_semantic"),
        ]:
            props[source]["copy_to"] = target
            props[target] = {"type": "semantic_text", "inference_id": elser_id}
    return {"properties": props}


EDGE_MAPPING = {
    "properties": {
        "id": {"type": "keyword"},
        "source": {"type": "keyword"},
        "target": {"type": "keyword"},
        "kind": {"type": "keyword"},
        "reason": {"type": "text"},
        "icebreaker": {"type": "text"},
        "created_at": {"type": "date"},
    }
}

CHECKIN_MAPPING = {
    "properties": {
        "attendee_id": {"type": "keyword"},
        "name": {"type": "keyword"},
        "room": {"type": "keyword"},
        "at": {"type": "date"},
    }
}


def ensure_indices(client: Elasticsearch) -> None:
    wanted = {
        ATTENDEES: attendee_mapping(settings.elser_id),
        EDGES: EDGE_MAPPING,
        CHECKINS: CHECKIN_MAPPING,
    }
    for name, mapping in wanted.items():
        if not client.indices.exists(index=name):
            client.indices.create(index=name, mappings=mapping)
            log.info("created index %s", name)


def ensure_indices_with_retry(client: Elasticsearch, seconds: int = 60) -> bool:
    """Elasticsearch may not be reachable the moment the pod starts. Keep trying for a
    minute instead of crash-looping; /healthz reports es:"red" in the meantime."""
    deadline = time.monotonic() + seconds
    while True:
        try:
            ensure_indices(client)
            return True
        except Exception as error:  # noqa: BLE001 - any failure here means "try again"
            if time.monotonic() > deadline:
                log.error("giving up creating indices: %s", error)
                return False
            log.warning("elasticsearch not ready (%s), retrying", error)
            time.sleep(3)
