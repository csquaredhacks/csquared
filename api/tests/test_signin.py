"""Sign in with Google or LinkedIn. The provider is never called in these tests:
`signin.fetch_identity` is replaced, so we test our side of the flow."""

from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from hallway import es, signin
from hallway.config import settings
from hallway.main import app


@pytest.fixture
def providers(monkeypatch):
    """Both providers are set up, and the provider answers with whoever `who` holds."""
    monkeypatch.setattr(settings, "google_client_id", "google-id")
    monkeypatch.setattr(settings, "google_client_secret", "google-secret")
    monkeypatch.setattr(settings, "linkedin_client_id", "linkedin-id")
    monkeypatch.setattr(settings, "linkedin_client_secret", "linkedin-secret")
    monkeypatch.setattr(settings, "public_url", "")
    who = {"sub": "sub-1", "name": "Ada Lovelace"}
    monkeypatch.setattr(signin, "fetch_identity", lambda provider, code, redirect: dict(who))
    return who


def browser() -> TestClient:
    """One device. It keeps its own cookies and does not follow redirects."""
    return TestClient(app, follow_redirects=False)


def start(client: TestClient, provider: str) -> dict:
    """Press the button. Returns the query the provider would receive."""
    response = client.get(f"/api/signin/{provider}")
    assert response.status_code == 307, response.text
    return {k: v[0] for k, v in parse_qs(urlsplit(response.headers["location"]).query).items()}


def sign_in(client: TestClient, provider: str) -> str:
    """The whole round trip. Returns where the person lands afterwards."""
    state = start(client, provider)["state"]
    response = client.get(f"/api/signin/{provider}/callback", params={"code": "c", "state": state})
    assert response.status_code == 303, response.text
    return response.headers["location"]


# --- no Elasticsearch needed ----------------------------------------------------------


def test_config_lists_only_the_providers_that_are_set_up(providers, monkeypatch):
    client = browser()
    assert client.get("/api/config").json()["signin"] == ["linkedin", "google"]
    monkeypatch.setattr(settings, "linkedin_client_secret", "")
    assert client.get("/api/config").json()["signin"] == ["google"]
    monkeypatch.setattr(settings, "google_client_id", "")
    assert client.get("/api/config").json()["signin"] == []


def test_the_button_sends_the_person_to_the_provider(providers):
    client = browser()
    response = client.get("/api/signin/google")
    assert response.headers["location"].startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    query = start(client, "google")
    assert query["client_id"] == "google-id"
    assert query["response_type"] == "code"
    assert query["scope"] == "openid profile"
    assert query["redirect_uri"] == "http://testserver/api/signin/google/callback"
    assert len(query["state"]) >= 20
    assert "secret" not in response.headers["location"]

    linkedin = client.get("/api/signin/linkedin").headers["location"]
    assert linkedin.startswith("https://www.linkedin.com/oauth/v2/authorization?")
    assert "client_id=linkedin-id" in linkedin


def test_the_redirect_address_follows_the_public_url(providers, monkeypatch):
    client = browser()
    # Behind the tunnel the request arrives as http, with the real scheme in a header.
    behind_tunnel = client.get(
        "/api/signin/google", headers={"host": "x.trycloudflare.com", "x-forwarded-proto": "https"}
    )
    assert "redirect_uri=https%3A%2F%2Fx.trycloudflare.com%2Fapi%2Fsignin" in (
        behind_tunnel.headers["location"]
    )
    monkeypatch.setattr(settings, "public_url", "https://hallway.example")
    assert start(client, "google")["redirect_uri"] == (
        "https://hallway.example/api/signin/google/callback"
    )


def test_a_provider_that_is_not_set_up_is_a_404(providers, monkeypatch):
    monkeypatch.setattr(settings, "google_client_secret", "")
    client = browser()
    assert client.get("/api/signin/google").status_code == 404
    assert client.get("/api/signin/google/callback?code=c&state=s").status_code == 404
    assert client.get("/api/signin/github").status_code == 404


def test_a_callback_nobody_asked_for_is_refused(providers, monkeypatch):
    def never(*_):
        raise AssertionError("the provider must not be called for a bad state")

    monkeypatch.setattr(signin, "fetch_identity", never)
    # No button was pressed on this device.
    stranger = browser()
    refused = stranger.get("/api/signin/google/callback?code=c&state=made-up")
    assert (refused.status_code, refused.headers["location"]) == (303, "/?signin_error=failed")
    # The button was pressed, but the state that comes back is not the one we sent.
    client = browser()
    start(client, "google")
    refused = client.get("/api/signin/google/callback?code=c&state=made-up")
    assert refused.headers["location"] == "/?signin_error=failed"
    # A state made for one provider is not accepted by the other.
    state = start(client, "google")["state"]
    refused = client.get(f"/api/signin/linkedin/callback?code=c&state={state}")
    assert refused.headers["location"] == "/?signin_error=failed"
    assert client.get("/api/signin/pending").json() is None


def test_cancelling_at_the_provider_comes_back_with_a_message(providers):
    client = browser()
    state = start(client, "linkedin")["state"]
    response = client.get(f"/api/signin/linkedin/callback?error=access_denied&state={state}")
    assert response.headers["location"] == "/?signin_error=cancelled"
    assert client.get("/api/signin/pending").json() is None


def test_a_provider_failure_comes_back_with_a_message(providers, monkeypatch):
    def broken(*_):
        raise signin.SigninFailed("token exchange failed")

    monkeypatch.setattr(signin, "fetch_identity", broken)
    client = browser()
    assert sign_in(client, "google") == "/?signin_error=failed"


def test_fetch_identity_swaps_the_code_for_a_name(providers, monkeypatch):
    monkeypatch.undo()  # the real fetch_identity, with the HTTP calls replaced below
    monkeypatch.setattr(settings, "google_client_id", "google-id")
    monkeypatch.setattr(settings, "google_client_secret", "google-secret")
    calls = []

    class Answer:
        def __init__(self, body):
            self.body = body

        def raise_for_status(self):
            pass

        def json(self):
            return self.body

    def post(url, data, timeout):
        calls.append((url, data))
        return Answer({"access_token": "token-1"})

    def get(url, headers, timeout):
        calls.append((url, headers))
        return Answer({"sub": 12345, "name": "  Ada Lovelace  ", "email": "not kept"})

    monkeypatch.setattr(signin.httpx, "post", post)
    monkeypatch.setattr(signin.httpx, "get", get)
    identity = signin.fetch_identity("google", "the-code", "http://testserver/cb")
    assert identity == {"sub": "12345", "name": "Ada Lovelace"}
    assert calls[0] == ("https://oauth2.googleapis.com/token", {
        "grant_type": "authorization_code", "code": "the-code",
        "redirect_uri": "http://testserver/cb",
        "client_id": "google-id", "client_secret": "google-secret",
    })  # fmt: skip
    assert calls[1] == (
        "https://openidconnect.googleapis.com/v1/userinfo", {"Authorization": "Bearer token-1"}
    )

    monkeypatch.setattr(signin.httpx, "get", lambda *a, **k: Answer({"name": "No Subject"}))
    with pytest.raises(signin.SigninFailed):
        signin.fetch_identity("google", "the-code", "http://testserver/cb")


def test_a_changed_pending_cookie_is_ignored(providers, monkeypatch):
    monkeypatch.setattr(signin, "find_attendee", lambda *a: None)
    monkeypatch.setattr(es, "get_client", lambda: None)
    client = browser()
    assert sign_in(client, "google") == "/"
    waiting = {"provider": "google", "name": "Ada Lovelace"}
    assert client.get("/api/signin/pending").json() == waiting
    value = client.cookies.get(signin.PENDING_COOKIE)
    payload, _, signature = value.partition(".")
    forged = TestClient(app, cookies={signin.PENDING_COOKIE: f"{payload}x.{signature}"})
    assert forged.get("/api/signin/pending").json() is None
    # Forgetting the sign in goes back to the plain form.
    assert client.delete("/api/signin/pending").status_code == 204
    assert client.get("/api/signin/pending").json() is None


# --- with Elasticsearch ---------------------------------------------------------------

PROFILE = {"name": "Ada Lovelace", "working_on": "an analytical engine"}


def test_first_sign_in_fills_the_form_and_the_next_one_opens_the_same_profile(indices, providers):
    providers["sub"] = "sub-round-trip"
    phone = browser()
    assert sign_in(phone, "google") == "/"
    # Nobody has this Google account yet, so there is no session: the form comes next.
    assert phone.get("/api/me").status_code == 401
    assert phone.get("/api/signin/pending").json() == {"provider": "google", "name": "Ada Lovelace"}

    created = phone.post("/api/attendees", json=PROFILE)
    assert created.status_code == 201, created.text
    me = created.json()
    assert me["signin_provider"] == "google"
    assert phone.get("/api/signin/pending").json() is None  # used once
    stored = es.get_client().get(index=es.ATTENDEES, id=me["id"])["_source"]
    assert (stored["signin_provider"], stored["signin_sub"]) == ("google", "sub-round-trip")
    # Only I can see how I signed in. The provider's id for me is never sent to anyone.
    public = phone.get(f"/api/attendees/{me['id']}").json()
    assert "signin_provider" not in public and "signin_sub" not in public
    assert "sub-round-trip" not in created.text

    # Another device, same Google account: straight into the same profile.
    laptop = browser()
    assert sign_in(laptop, "google") == "/"
    assert laptop.get("/api/me").json() == me
    assert laptop.get("/api/signin/pending").json() is None


def test_the_same_id_at_another_provider_is_another_person(indices, providers):
    providers["sub"] = "sub-shared"
    first = browser()
    sign_in(first, "google")
    me = first.post("/api/attendees", json=PROFILE).json()

    other = browser()
    sign_in(other, "linkedin")
    assert other.get("/api/me").status_code == 401
    assert other.get("/api/signin/pending").json()["provider"] == "linkedin"
    them = other.post("/api/attendees", json=PROFILE | {"name": "Someone Else"}).json()
    assert them["id"] != me["id"] and them["signin_provider"] == "linkedin"


def test_one_account_cannot_make_two_profiles(indices, providers):
    providers["sub"] = "sub-twice"
    tab_one, tab_two = browser(), browser()
    sign_in(tab_one, "google")
    sign_in(tab_two, "google")
    assert tab_one.post("/api/attendees", json=PROFILE).status_code == 201
    again = tab_two.post("/api/attendees", json=PROFILE)
    assert again.status_code == 409
    assert "Sign in" in again.json()["detail"]
    assert tab_two.get("/api/me").status_code == 401


def test_joining_without_signing_in_still_works(indices, providers):
    client = browser()
    me = client.post("/api/attendees", json=PROFILE).json()
    assert me["signin_provider"] is None
    stored = es.get_client().get(index=es.ATTENDEES, id=me["id"])["_source"]
    assert "signin_sub" not in stored
