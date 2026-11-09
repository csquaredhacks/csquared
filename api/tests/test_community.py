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
        # user:pass credentials in the URL
        "https://user:pass@luma.com/event",
        # whitespace and control characters
        "https://luma.com/e\nX", "https://luma.com/ e", "https://luma.com/e\t1",
        # invalid or non-443 ports
        "https://luma.com:8443/event", "https://luma.com:abc/event",
    ):
        with pytest.raises(ValidationError):
            CommunityIn(name="Community", luma_url=url)


def test_community_accepts_valid_luma_links():
    from hallway.models import CommunityIn

    # Standard luma.com
    c = CommunityIn(name="Community", luma_url="https://luma.com/event")
    assert c.luma_url == "https://luma.com/event"

    # www.luma.com should also be allowed
    c = CommunityIn(name="Community", luma_url="https://www.luma.com/event")
    assert c.luma_url == "https://www.luma.com/event"

    # lu.ma
    c = CommunityIn(name="Community", luma_url="https://lu.ma/event")
    assert c.luma_url == "https://lu.ma/event"

    # Explicit port 443 is fine
    c = CommunityIn(name="Community", luma_url="https://luma.com:443/event")
    assert c.luma_url == "https://luma.com:443/event"
