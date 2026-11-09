"""Request and response shapes. Changing anything here means running `make types`
so web/src/api/schema.d.ts stays in sync (CI checks this)."""

import re
from typing import Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, BaseModel, Field, field_validator, model_validator

Comfort = Literal["open", "small_groups", "one_on_one"]
# Link kinds that may appear on the public graph. A pending invitation is never one of them.
EdgeKind = Literal["connected", "planned", "suggested"]
# How one person relates to me, in my own private view of the graph.
RelationKind = Literal["met", "planned", "invited_you", "you_invited", "suggested"]
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
    # Two separate opt-in choices. Both are off unless the person turns them on.
    on_graph: bool = False  # show me, and who I have met or planned to meet, on the public graph
    show_groups: bool = False  # also show my communities there

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
    show_groups: bool = False


class MeUpdate(BaseModel):
    """PATCH /api/me. Leave a field out to keep it as it is."""

    on_graph: bool | None = None
    show_groups: bool | None = None


class RecoverIn(BaseModel):
    code: str = Field(min_length=6, max_length=6)


def strip_text(value):
    return value.strip() if isinstance(value, str) else value


def check_luma_url(value: str) -> str:
    """Shared by creating and editing a community, so the two can never disagree."""
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


class CommunityIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)
    luma_url: str = Field(max_length=2048)

    @field_validator("name", "description", mode="before")
    @classmethod
    def strip_community_text(cls, value: str) -> str:
        return strip_text(value)

    @field_validator("luma_url")
    @classmethod
    def valid_luma_url(cls, value: str) -> str:
        return check_luma_url(value)


class CommunityUpdate(BaseModel):
    """PATCH /api/communities/{id}. Leave a field out to keep it as it is. A field that
    is sent follows the same rules as in CommunityIn."""

    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    luma_url: str | None = Field(default=None, max_length=2048)

    @field_validator("name", "description", mode="before")
    @classmethod
    def strip_community_text(cls, value: str | None) -> str | None:
        return strip_text(value)

    @field_validator("luma_url")
    @classmethod
    def valid_luma_url(cls, value: str | None) -> str | None:
        return value if value is None else check_luma_url(value)


class Community(CommunityIn):
    """What anyone may see. Members are only ever a count: no names, no ids. The last
    two fields are about the signed-in caller, and false for a visitor."""

    id: str
    member_count: int
    is_member: bool
    is_organizer: bool


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
    planned: bool = False  # true when the two had agreed to meet before they met


class ConnectResult(BaseModel):
    edge: Edge
    created: bool
    other: Attendee


class GraphNode(BaseModel):
    id: str
    name: str
    groups: list[str]  # empty unless the person chose to show their communities
    tags: list[str]


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


class Relationship(BaseModel):
    attendee: Attendee
    kind: RelationKind
    reason: str  # why this person is relevant to me, built from matching evidence
    via: list[PathStep]  # people I have met who could introduce us, nearest first


class MyGraph(BaseModel):
    relationships: list[Relationship]


class InvitationResult(BaseModel):
    kind: Literal["you_invited", "planned"]
    other: Attendee


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

    @model_validator(mode="after")
    def offset_matches_timezone(self) -> "MeetingIn":
        """"09:00+00:00" in America/Denver is two different times. Refuse it instead of
        storing a meeting that people in the group would read differently."""
        in_zone = self.starts_at.astimezone(ZoneInfo(self.timezone))
        if in_zone.utcoffset() != self.starts_at.utcoffset():
            raise ValueError("The UTC offset of starts_at does not match the time zone")
        return self


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
    # True when someone left and I am now the only member. I am told; nothing is changed
    # for me unless I ask for another group.
    left_alone: bool = False


class AcceptIn(BaseModel):
    companion: bool = False  # bringing one friend or companion, who takes a seat too


class Goal(BaseModel):
    text: str = Field(min_length=1, max_length=120)
    done: bool = False  # set only by the person themselves

    @field_validator("text", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        """Before the length check, so a goal made only of spaces is refused."""
        return value.strip() if isinstance(value, str) else value


class Goals(BaseModel):
    """My own goals for this conference. Private to me."""

    goals: list[Goal] = Field(max_length=5)


class Topic(BaseModel):
    topic: str
    asking: int  # people whose asks mention it
    offering: int  # people whose offers mention it


class Count(BaseModel):
    key: str
    count: int


class Crowd(BaseModel):
    """The organizer board. Counts only; anything about fewer than three people is left out."""

    registered: int
    in_groups: int  # people who accepted an arrival group
    groups: int
    groups_with_meeting: int  # groups that agreed where and when to meet
    invitations: int  # sent and not yet answered
    plans: int  # pairs who agreed to meet
    meetings: int  # pairs who met (one scanned the other's code)
    checked_in: int  # people who checked in to a room in Hallway; not Luma event check-in
    topics: list[Topic]  # widest gap between asking and offering first
    comfort: list[Count]


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
