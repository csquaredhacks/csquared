"""Request and response shapes. Changing anything here means running `make types`
so web/src/api/schema.d.ts stays in sync (CI checks this)."""

from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, BaseModel, Field, field_validator

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


CrewStatus = Literal["none", "suggested", "member"]


class Meeting(BaseModel):
    """Agreed by the crew. Stored as given; never derived from a hash of the crew id."""

    place: str
    starts_at: str
    timezone: str
    set_by: str


class MeetingIn(BaseModel):
    place: str = Field(min_length=1, max_length=200)
    starts_at: AwareDatetime  # must carry a UTC offset
    timezone: str = Field(min_length=1, max_length=64)  # IANA name, e.g. America/Denver

    @field_validator("place")
    @classmethod
    def strip_place(cls, value: str) -> str:
        return value.strip()

    @field_validator("timezone")
    @classmethod
    def known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Unknown time zone; use an IANA name like America/Denver") from None
        return value


class Crew(BaseModel):
    """An arrival group. `members` are only people who accepted. Pending suggestions
    and declines are never shown to anyone."""

    id: str
    members: list[Attendee]
    seats_taken: int
    limit: int
    why: str
    meeting: Meeting | None


class CrewOut(BaseModel):
    status: CrewStatus
    crew: Crew | None
    bringing_companion: bool = False


class AcceptIn(BaseModel):
    companion: bool = False  # bringing one friend or companion, who takes a seat too


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
