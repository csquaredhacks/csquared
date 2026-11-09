from fastapi.testclient import TestClient

from hallway import es
from hallway.auth import current_attendee
from hallway.main import app


def test_community_invitation_requires_a_session_and_hides_the_owner(monkeypatch):
    documents = {}

    class Store:
        def index(self, *, index, id, document, refresh):
            documents[id] = document

        def get(self, *, index, id):
            return {"_source": documents[id]}

    monkeypatch.setattr(es, "get_client", lambda: Store())
    client = TestClient(app)
    data = {
        "name": "Community", "description": "Meet together", "luma_url": "https://luma.com/event"
    }
    assert client.post("/api/communities", json=data).status_code == 401
    app.dependency_overrides[current_attendee] = lambda: {"id": "private-owner"}
    try:
        created = client.post("/api/communities", json=data)
        assert created.status_code == 201
        app.dependency_overrides.clear()
        invitation = client.get(f"/api/communities/{created.json()['id']}")
        assert invitation.status_code == 200
        assert invitation.json() == {"id": created.json()["id"], **data}
    finally:
        app.dependency_overrides.clear()


def test_community_rejects_misleading_luma_links():
    import pytest
    from pydantic import ValidationError

    from hallway.models import CommunityIn

    for url in (
        "javascript:alert(1)", "https://luma.com.example.com/event",
        "http://luma.com/event", "https://luma.com/",
    ):
        with pytest.raises(ValidationError):
            CommunityIn(name="Community", luma_url=url)
