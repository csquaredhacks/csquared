"""Recovery throttling through the API, without a running Elasticsearch."""

from collections import deque
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from hallway.auth import COOKIE
from hallway.main import app
from hallway.models import AttendeeIn
from hallway.routes import attendees


@pytest.fixture
def recovery(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(attendees, "monotonic", lambda: now[0])
    monkeypatch.setattr(
        attendees, "_recovery_failures", deque(maxlen=attendees.RECOVERY_FAILURE_LIMIT)
    )
    doc = AttendeeIn(name="Lost Phone", working_on="testing recovery").model_dump() | {
        "id": "test-attendee",
        "secret": "session-secret",
        "recovery_code": "ABC234",
    }
    backend = Mock()

    def search(*, index, query, size):
        hits = [{"_source": doc}] if query["term"]["recovery_code"] == doc["recovery_code"] else []
        return {"hits": {"hits": hits}}

    backend.search.side_effect = search
    backend.get.return_value = {"_source": doc}
    monkeypatch.setattr(attendees.es, "get_client", lambda: backend)
    return TestClient(app), backend, now, doc


def test_failed_recovery_is_bounded_despite_forwarding_headers(recovery):
    client, backend, now, doc = recovery
    for attempt in range(attendees.RECOVERY_FAILURE_LIMIT):
        response = client.post(
            "/api/recover",
            json={"code": f"{attempt:06d}"},
            headers={
                "X-Forwarded-For": f"192.0.2.{attempt + 1}",
                "CF-Connecting-IP": f"192.0.2.{attempt + 1}",
                "Forwarded": f"for=192.0.2.{attempt + 1}",
            },
        )
        assert response.status_code == 404

    # A fresh client and even a valid code cannot bypass the exhausted shared budget.
    response = TestClient(app).post("/api/recover", json={"code": doc["recovery_code"]})
    assert response.status_code == 429
    assert response.headers["Retry-After"] == str(attendees.RECOVERY_WINDOW_SECONDS)
    assert "set-cookie" not in response.headers
    assert backend.search.call_count == attendees.RECOVERY_FAILURE_LIMIT

    now[0] += attendees.RECOVERY_WINDOW_SECONDS - 0.5
    response = client.post("/api/recover", json={"code": "ZZZZZZ"})
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "1"
    now[0] += 0.5
    assert client.post("/api/recover", json={"code": "ZZZZZZ"}).status_code == 404
    assert len(attendees._recovery_failures) == 1
    assert client.post("/api/recover", json={"code": "abc234"}).status_code == 200


def test_successful_recovery_preserves_session_and_failure_budget(recovery):
    client, backend, _, doc = recovery
    for _ in range(attendees.RECOVERY_FAILURE_LIMIT - 1):
        assert client.post("/api/recover", json={"code": "ZZZZZZ"}).status_code == 404
    for _ in range(attendees.RECOVERY_FAILURE_LIMIT + 1):
        response = client.post("/api/recover", json={"code": "abc234"})
        assert response.status_code == 200
        assert response.json()["recovery_code"] == doc["recovery_code"]
        assert "secret" not in response.json()
        assert client.cookies[COOKIE] == f"{doc['id']}.{doc['secret']}"
    assert client.get("/api/me").json()["id"] == doc["id"]
    # Success neither consumes nor resets the failed-guess budget.
    assert client.post("/api/recover", json={"code": "ZZZZZZ"}).status_code == 404
    assert client.post("/api/recover", json={"code": "ZZZZZZ"}).status_code == 429


def test_concurrent_failed_recovery_cannot_exceed_budget(recovery):
    _, backend, _, _ = recovery

    def guess(_):
        return TestClient(app).post("/api/recover", json={"code": "ZZZZZZ"}).status_code

    with ThreadPoolExecutor(max_workers=16) as pool:
        statuses = list(pool.map(guess, range(attendees.RECOVERY_FAILURE_LIMIT * 2)))
    assert statuses.count(404) == attendees.RECOVERY_FAILURE_LIMIT
    assert statuses.count(429) == attendees.RECOVERY_FAILURE_LIMIT
    assert backend.search.call_count == attendees.RECOVERY_FAILURE_LIMIT
