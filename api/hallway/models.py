"""Request and response shapes. Changing anything here means running `make types`
so web/src/api/schema.d.ts stays in sync (CI checks this)."""

import re
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator

Comfort = Literal["open", "small_groups", "one_on_one"]
EdgeKind = Literal["connected", "suggested"]
ChaosMode = Literal["off", "slow", "error"]


class AttendeeIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    working_on: str = Field(min_length=1, max_length=500)
    asks: str = Field(default="", max_length=500)
    offers: str = Field(default="", max_length=500)
    fun_fact: str = Field(default="", max_length=300)
    tags: list[str] = Field(default_factory=list, max_length=10)
    groups: list[str] = Field(default_factory=list, max_length=5)
    comfort: Comfort = "open"
    on_graph: bool = True

    @field_validator("name", "working_on", "asks", "offers", "fun_fact")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, value: list[str]) -> list[str]:
        return sorted({t.strip().lower() for t in value if t.strip()})

    @field_validator("groups")
    @classmethod
    def clean_groups(cls, value: list[str]) -> list[str]:
        return sorted({g.strip() for g in value if g.strip()})


class Attendee(BaseModel):
    """Public profile. Never contains the session secret or recovery code."""

    id: str
    name: str
    working_on: str
    asks: str
    offers: str
    fun_fact: str
    tags: list[str]
    groups: list[str]
    comfort: Comfort


class Me(Attendee):
    recovery_code: str
    on_graph: bool


class RecoverIn(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class CommunityIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)
    luma_url: str = Field(max_length=2048)

    @field_validator("name", "description", mode="before")
    @classmethod
    def strip_community_text(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    @field_validator("luma_url")
    @classmethod
    def valid_luma_url(cls, value: str) -> str:
        value = value.strip()
        # Reject whitespace and control characters inside the URL.
        if re.search(r"[\s\x00-\x1f]", value):
            raise ValueError("Enter an HTTPS event link from luma.com or lu.ma")
        try:
            url = urlsplit(value)
            if (
                url.scheme != "https"
                or url.hostname not in {"luma.com", "www.luma.com", "lu.ma"}
                or url.username
                or url.password
                or not url.path.strip("/")
                or (url.port is not None and url.port != 443)
            ):
                raise ValueError
        except ValueError as error:
            raise ValueError("Enter an HTTPS event link from luma.com or lu.ma") from error
        return value


class Community(CommunityIn):
    id: str


class Match(BaseModel):
    attendee: Attendee
    score: float
    reason: str
    icebreaker: str


class EdgeIn(BaseModel):
    to_id: str


class Edge(BaseModel):
    id: str
    source: str
    target: str
    kind: EdgeKind
    reason: str
    created_at: str


class ConnectResult(BaseModel):
    edge: Edge
    created: bool
    other: Attendee


class GraphNode(BaseModel):
    id: str
    name: str
    groups: list[str]
    tags: list[str]
    degree: int


class GraphLink(BaseModel):
    source: str
    target: str
    kind: EdgeKind
    reason: str


class Graph(BaseModel):
    nodes: list[GraphNode]
    links: list[GraphLink]


class PathStep(BaseModel):
    id: str
    name: str


class Path(BaseModel):
    path: list[PathStep]


class CheckinIn(BaseModel):
    room: str


class Room(BaseModel):
    room: str
    count: int
    people: list[PathStep]


class Recap(BaseModel):
    connections: list[Attendee]
    groups_bridged: int
    nudges: list[str]


class Rum(BaseModel):
    url: str
    token: str


class Config(BaseModel):
    rooms: list[str]
    chaos_enabled: bool
    rum: Rum | None


class Chaos(BaseModel):
    mode: ChaosMode


class Health(BaseModel):
    ok: bool
    es: Literal["green", "red"]
