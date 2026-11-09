"""Exercise the CLI against a local in-memory HTTP fixture; no API or Elasticsearch needed."""

import io
import sys
from contextlib import redirect_stderr, redirect_stdout
from functools import partial
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest

from deploy import smoke

SHELL = b'''<!doctype html><title>Hallway</title><div id="root"></div>
<script type="module" crossorigin src="/assets/index-test.js"></script>'''


@pytest.fixture
def demo(monkeypatch):
    routes = {path: (200, "text/html", SHELL) for path in ("/", "/plan", "/graph")}
    routes["/assets/index-test.js"] = (200, "text/javascript", b'console.log("Hallway");')
    routes["/healthz"] = (200, "application/json", b'{"ok": true, "es": "green"}')
    requests = []

    def respond(request):
        requests.append((request.method, request.url.path))
        assert request.method == "GET"
        assert "authorization" not in request.headers
        reply = routes.get(request.url.path, (404, "text/plain", b"missing"))
        if isinstance(reply, Exception):
            raise reply
        status, content_type, body = reply
        return httpx.Response(
            status, headers={"Content-Type": content_type, "Location": "/"}, content=body,
        )

    monkeypatch.setattr(
        smoke.httpx, "Client", partial(httpx.Client, transport=httpx.MockTransport(respond)),
    )
    return "http://127.0.0.1:8000", routes, requests


def run(base):
    stdout, stderr = io.StringIO(), io.StringIO()
    code = 0
    with patch.object(sys, "argv", ["smoke.py", "--api", base]):
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                smoke.main()
            except SystemExit as exc:
                code = 1
                print(exc, file=sys.stderr)
    return SimpleNamespace(returncode=code, stdout=stdout.getvalue(), stderr=stderr.getvalue())


@pytest.mark.parametrize("suffix", ["", "/"])
def test_ready_demo_uses_only_get(demo, suffix):
    base, _, requests = demo
    result = run(base + suffix)
    assert result.returncode == 0, result.stderr
    assert "Demo smoke check passed" in result.stdout
    assert requests == [("GET", path) for path in (
        "/", "/plan", "/graph", "/assets/index-test.js", "/healthz",
    )]


@pytest.mark.parametrize("path,status", [
    ("/", 503), ("/plan", 404), ("/graph", 500), ("/plan", 302),
    ("/assets/index-test.js", 404), ("/healthz", 503),
])
def test_http_failure(demo, path, status):
    base, routes, _ = demo
    routes[path] = (status, "text/html", SHELL)
    result = run(base)
    assert result.returncode == 1
    assert f"expected HTTP 200, got {status}" in result.stderr


@pytest.mark.parametrize("path,content_type,body,message", [
    ("/", "text/html", b"<h1>Proxy error</h1>", "Join /: expected"),
    ("/graph", "application/json", b"{}", "Graph /graph: expected"),
    ("/assets/index-test.js", "text/html", SHELL, "expected nonempty JavaScript"),
    ("/assets/index-test.js", "text/javascript", b"", "expected nonempty JavaScript"),
    ("/healthz", "application/json", b'{"ok": true, "es": "red"}', "not ready"),
    ("/healthz", "application/json", b'{"ok": false, "es": "green"}', "not ready"),
    ("/healthz", "application/json", b'{"ok": true}', "not ready"),
    ("/healthz", "application/json", b"[]", "not ready"),
    ("/healthz", "text/html", SHELL, "expected JSON"),
])
def test_invalid_content(demo, path, content_type, body, message):
    base, routes, _ = demo
    routes[path] = (200, content_type, body)
    result = run(base)
    assert result.returncode == 1
    assert message in result.stderr


@pytest.mark.parametrize("error", [httpx.ConnectError("refused"), httpx.ReadTimeout("timeout")])
def test_connection_failure(demo, error):
    base, routes, _ = demo
    routes["/"] = error
    result = run(base)
    assert result.returncode == 1
    assert f"Join /: GET failed ({type(error).__name__})" in result.stderr


def test_external_asset_is_not_requested(demo):
    base, routes, requests = demo
    routes["/"] = (200, "text/html", SHELL.replace(
        b"/assets/index-test.js", b"https://example.invalid/assets/app.js",
    ))
    result = run(base)
    assert result.returncode == 1
    assert "same-origin" in result.stderr
    assert len(requests) == 3


@pytest.mark.parametrize("base", [
    "file:///tmp/demo", "http://user:password@localhost", "http://localhost?token=example",
])
def test_invalid_url_is_not_requested(demo, base):
    _, _, requests = demo
    result = run(base)
    assert result.returncode == 1
    assert "without credentials, query or fragment" in result.stderr
    assert requests == []
