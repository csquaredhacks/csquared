"""Integration tests talk to a real Elasticsearch (ES_URL, default http://localhost:9200)
using throwaway indices. If none is reachable they are skipped; pure tests still run."""

import os
import secrets

# Must be set before `hallway` is imported, because index names are built at import time.
os.environ["INDEX_PREFIX"] = f"test-{secrets.token_hex(4)}"
os.environ["CHAOS_ENABLED"] = "true"
os.environ["ADMIN_TOKEN"] = "test-admin"
os.environ["OPENAI_API_KEY"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from hallway import es  # noqa: E402
from hallway.main import app  # noqa: E402


@pytest.fixture(scope="session")
def indices():
    client = es.get_client()
    try:
        reachable = client.ping()
    except Exception:  # noqa: BLE001
        reachable = False
    if not reachable:
        pytest.skip("Elasticsearch is not reachable; skipping integration tests")
    es.ensure_indices(client)
    yield
    client.indices.delete(index=[es.ATTENDEES, es.EDGES, es.CHECKINS, es.COMMUNITIES], ignore_unavailable=True)


@pytest.fixture
def person(indices):
    """Factory: person("Ada", asks=..., offers=...) registers someone and returns
    (their own HTTP client holding their session cookie, their profile)."""

    def make(name: str, **fields):
        client = TestClient(app)
        body = {"name": name, "working_on": "testing hallway", **fields}
        response = client.post("/api/attendees", json=body)
        assert response.status_code == 201, response.text
        return client, response.json()

    return make
