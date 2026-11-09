"""Read-only deployment check. Run with: make smoke API=https://your-demo-host

Uses only GET, without a session or credentials. Checks the SPA shell and a built
asset, not JavaScript execution or authenticated attendee flows. Requires httpx,
already included in the API dependencies.
"""

import argparse
import json
import sys
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import httpx


class AppShell(HTMLParser):
    def __init__(self):
        super().__init__()
        self.root = False
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div" and attrs.get("id") == "root":
            self.root = True
        if tag == "script" and attrs.get("type") == "module" and attrs.get("src"):
            self.scripts.append(attrs["src"])


def smoke(base: str) -> None:
    base = base.rstrip("/") + "/"
    parsed = urlsplit(base)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Use an http(s) base URL without credentials, query or fragment")

    # Do not let a redirect to a login/error page turn a missing route into a pass.
    with httpx.Client(timeout=10, follow_redirects=False) as client:
        def get(url, label):
            try:
                response = client.get(url)
            except httpx.HTTPError as exc:
                raise ValueError(f"{label}: GET failed ({type(exc).__name__})") from exc
            if response.status_code != 200:
                raise ValueError(f"{label}: expected HTTP 200, got {response.status_code}")
            return response

        asset = None
        for path, name in (("", "Join"), ("plan", "Plan"), ("graph", "Graph")):
            label = f"{name} /{path}"
            response = get(urljoin(base, path), label)
            shell = AppShell()
            shell.feed(response.text)
            if (
                response.headers.get("content-type", "").split(";")[0] != "text/html"
                or not shell.root
                or not shell.scripts
                or "Hallway" not in response.text
            ):
                raise ValueError(f"{label}: expected the Hallway HTML app shell")
            if not path:
                asset = urljoin(base, shell.scripts[0])
            print(f"ok 200: {label}")

        asset_url = urlsplit(asset)
        if (asset_url.scheme, asset_url.netloc) != (parsed.scheme, parsed.netloc):
            raise ValueError("Frontend asset: expected a same-origin module script")
        response = get(asset, "Frontend asset")
        content_type = response.headers.get("content-type", "").split(";")[0]
        if content_type not in {"text/javascript", "application/javascript"} or not response.content:
            raise ValueError("Frontend asset: expected nonempty JavaScript; got empty or wrong type")
        print("ok 200: frontend JavaScript asset")

        response = get(urljoin(base, "healthz"), "/healthz")
        try:
            health = response.json()
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("/healthz: expected JSON readiness response") from exc
        if (
            not isinstance(health, dict)
            or health.get("ok") is not True
            or health.get("es") != "green"
        ):
            raise ValueError('/healthz: not ready; expected ok=true and es="green"')
        print("ok 200: /healthz (Elasticsearch ready)")
    print("Demo smoke check passed (GET only).")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", required=True, help="demo base URL")
    args = parser.parse_args()
    try:
        smoke(args.api)
    except (ValueError, httpx.InvalidURL) as exc:
        sys.exit(f"FAILED: {exc}")


if __name__ == "__main__":
    main()
