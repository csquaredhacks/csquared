from hallway import es, main


def test_health_reports_missing_indices(monkeypatch):
    class Client:
        def ping(self):
            return True

    class Indices:
        def exists(self, index):
            return False

    client = Client()
    client.indices = Indices()
    monkeypatch.setattr(es, "get_client", lambda: client)
    assert main.healthz().model_dump() == {"ok": True, "es": "red"}


def test_health_stays_red_until_index_setup_completes(monkeypatch):
    class Indices:
        def exists(self, index):
            return True

    class Client:
        indices = Indices()

        def ping(self):
            return True

    client = Client()
    monkeypatch.setattr(es, "get_client", lambda: client)
    main._indices_ready.clear()

    def ensure_indices(_client, seconds):
        assert seconds is None
        assert not main._indices_ready.is_set()
        return True

    monkeypatch.setattr(es, "ensure_indices_with_retry", ensure_indices)
    try:
        assert main.healthz().es == "red"
        main._initialize_indices()
        assert main.healthz().es == "green"
    finally:
        main._indices_ready.clear()


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
