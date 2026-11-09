from fastapi.testclient import TestClient

from hallway import es
from hallway.main import app


def test_health_reports_missing_indices(monkeypatch):
    class Client:
        indices = None

        def ping(self):
            return True

    class Indices:
        def exists(self, index):
            return False

    client = Client()
    client.indices = Indices()
    monkeypatch.setattr(es, "get_client", lambda: client)
    assert TestClient(app).get("/healthz").json() == {"ok": True, "es": "red"}


def test_unbounded_index_retry_recovers(monkeypatch):
    attempts = []

    def ensure(_client):
        attempts.append(1)
        if len(attempts) < 3:
            raise ConnectionError("not ready")

    monkeypatch.setattr(es, "ensure_indices", ensure)
    monkeypatch.setattr(es.time, "sleep", lambda _: None)
    assert es.ensure_indices_with_retry(object(), seconds=None)
    assert len(attempts) == 3
