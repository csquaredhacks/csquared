"""All configuration comes from environment variables (see .env.example)."""

import os
from pathlib import Path


def _flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes")


class Settings:
    def __init__(self) -> None:
        self.es_url = os.getenv("ES_URL", "http://localhost:9200")
        self.es_api_key = os.getenv("ES_API_KEY", "")
        # Inference endpoint id for ELSER. Empty means lexical-only matching (no semantic fields).
        self.elser_id = os.getenv("ELSER_ID", "")
        # Lets tests (and several people sharing one cluster) use separate indices.
        self.index_prefix = os.getenv("INDEX_PREFIX", "hallway")
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        rooms = os.getenv("ROOMS", "Main Stage,Room A,Room B,Coffee Bar,Quiet Room")
        self.rooms = [r.strip() for r in rooms.split(",") if r.strip()]
        self.chaos_enabled = _flag("CHAOS_ENABLED")
        self.admin_token = os.getenv("ADMIN_TOKEN", "")
        self.rum_url = os.getenv("DASH0_RUM_URL", "")
        self.rum_token = os.getenv("DASH0_RUM_TOKEN", "")
        self.cookie_secure = _flag("COOKIE_SECURE")
        # Sign in with Google and LinkedIn. A button only appears when both of its
        # values are set; with none set, people join with the plain form.
        self.google_client_id = os.getenv("GOOGLE_CLIENT_ID", "")
        self.google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
        self.linkedin_client_id = os.getenv("LINKEDIN_CLIENT_ID", "")
        self.linkedin_client_secret = os.getenv("LINKEDIN_CLIENT_SECRET", "")
        # The address people open, e.g. https://hallway.example. Only needed when it
        # cannot be read from the request; see signin.redirect_uri.
        self.public_url = os.getenv("PUBLIC_URL", "").strip().rstrip("/")
        # Built web app. Default is <repo>/web/dist for local runs; the image sets WEB_DIST.
        default_dist = Path(__file__).resolve().parents[2] / "web" / "dist"
        self.web_dist = Path(os.getenv("WEB_DIST", str(default_dist)))


settings = Settings()
