"""Arrival groups ("crews"): a few people who agree to walk in together.

Working plan, build step 3. A crew is only ever *suggested* to you. Nothing changes
until you accept, and you can decline or leave at any time without being reassigned.

Stored in its own index (no change to the attendee mapping, no reindex):

    {id, members: [ids], companions: [ids], invited: [ids], declined: [ids],
     meeting: {place, starts_at, timezone, set_by} | null, created_at}

- `members` accepted. `companions` is the subset of members bringing one companion,
  who takes a seat too.
- `invited` holds pending suggestions. It is never returned to anyone: other members
  only see who accepted, so a suggestion that someone declines leaves no trace.
- `declined` stops the same crew from being suggested to the same person again.

Capacity is enforced on accept with optimistic concurrency (if_seq_no/if_primary_term),
so two people accepting the last seat at the same moment cannot both get it. One person
accepting two crews at the same moment ends up in exactly one (`_keep_one_membership`).
"""

import hashlib
import hmac
import os
import secrets

from elasticsearch import ConflictError, Elasticsearch, NotFoundError

from . import es
from .matching import find_matches
from .telemetry import crew_joins

_PAIR_ID_SALT_DOC = "_crew-pair-id-salt"


def _pair_id_salt(client: Elasticsearch) -> bytes:
    """Use a configured key, or load and persist one shared by all API replicas."""
    configured_salt = os.getenv("CREW_ID_SALT")
    if configured_salt:
        return configured_salt.encode()
    try:
        doc = client.get(index=es.CREWS, id=_PAIR_ID_SALT_DOC)
    except NotFoundError:
        salt = os.getenv("CREW_ID_SALT") or secrets.token_hex(32)
        try:
            client.index(
                index=es.CREWS,
                id=_PAIR_ID_SALT_DOC,
                document={"pair_id_salt": salt},
                op_type="create",
                refresh=True,
            )
        except ConflictError:
            # Another replica initialized the key first. Use its persisted value.
            pass
        doc = client.get(index=es.CREWS, id=_PAIR_ID_SALT_DOC)
    return doc["_source"]["pair_id_salt"].encode()


def pair_crew_id(a: str, b: str, salt: bytes) -> str:
    """Same id whichever of the two starts the crew, so concurrent suggestions collapse
    into one document. Keyed and hashed, because attendee ids are public (they are in
    QR codes) and a readable id would reveal who else was suggested or declined."""
    pair = ":".join(sorted([a, b])).encode()
    return hmac.new(salt, pair, hashlib.sha256).hexdigest()[:16]


# A crew's limit is the smallest limit among its members (and the person joining).
COMFORT_LIMIT = {"one_on_one": 2, "small_groups": 4, "open": 5}
MAX_CREWS = 2000
RETRIES = 5


class CrewError(Exception):
    """Carries an HTTP status and a message for the route to return."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def seats_taken(crew: dict) -> int:
    return len(crew["members"]) + len(crew.get("companions", []))


def crew_limit(members: list[dict]) -> int:
    return min((COMFORT_LIMIT[m.get("comfort", "open")] for m in members), default=5)


def _search(client: Elasticsearch, field: str, attendee_id: str) -> list[dict]:
    hits = client.search(
        index=es.CREWS,
        query={"term": {field: attendee_id}},
        size=MAX_CREWS,
        seq_no_primary_term=True,
    )["hits"]["hits"]
    return [h["_source"] for h in hits]


def _declined_partners(client: Elasticsearch, attendee_id: str) -> set[str]:
    """Pairs already declined remain blocked even if their crew id predates key storage."""
    partners: set[str] = set()
    for crew in _search(client, "declined", attendee_id):
        if attendee_id in crew.get("declined", []):
            partners.update(crew.get("members", []))
            partners.update(crew.get("invited", []))
            partners.update(crew.get("declined", []))
    partners.discard(attendee_id)
    return partners


def crew_of(client: Elasticsearch, attendee_id: str) -> dict | None:
    """The crew this person accepted, if any."""
    found = _search(client, "members", attendee_id)
    return found[0] if found else None


def pending_for(client: Elasticsearch, attendee_id: str) -> dict | None:
    """The crew suggested to this person and not yet answered, if any."""
    found = _search(client, "invited", attendee_id)
    return found[0] if found else None


def load_people(client: Elasticsearch, ids: list[str]) -> list[dict]:
    if not ids:
        return []
    docs = client.mget(index=es.ATTENDEES, ids=ids)["docs"]
    return [d["_source"] for d in docs if d.get("found")]


def has_room(client: Elasticsearch, crew: dict, joiner: dict, companion: bool = False) -> bool:
    members = load_people(client, crew["members"])
    limit = crew_limit([*members, joiner])
    return seats_taken(crew) + 1 + int(companion) <= limit


def _save(client: Elasticsearch, crew: dict, seq_no: int | None = None, term: int | None = None):
    kwargs = {}
    if seq_no is not None:
        kwargs = {"if_seq_no": seq_no, "if_primary_term": term}
    client.index(index=es.CREWS, id=crew["id"], document=crew, refresh=True, **kwargs)


def _get(client: Elasticsearch, crew_id: str) -> tuple[dict, int, int]:
    try:
        doc = client.get(index=es.CREWS, id=crew_id)
    except NotFoundError:
        raise CrewError(404, "That crew no longer exists") from None
    return doc["_source"], doc["_seq_no"], doc["_primary_term"]


def _update(client: Elasticsearch, crew_id: str, change) -> dict:
    """Read, apply `change(crew)`, write back only if nobody wrote in between. Retries
    on a conflict, re-running `change` against the fresh copy, so its checks see the
    latest state. `change` raises CrewError to refuse."""
    for _ in range(RETRIES):
        crew, seq_no, term = _get(client, crew_id)
        change(crew)
        try:
            _save(client, crew, seq_no, term)
            return crew
        except ConflictError:
            continue
    raise CrewError(409, "The crew changed while you were joining. Try again.")


def suggest(client: Elasticsearch, me: dict) -> dict | None:
    """Find a crew to suggest to `me`, record the suggestion, and return the crew.

    1. Already in a crew, or already holding a suggestion: return that, change nothing.
    2. Walk my matches in order. The first one who is in a crew with room for me, and
       that I have not declined or left, is suggested.
    3. Otherwise start a new crew suggestion with my first match who has no crew and no
       pending suggestion. Both of us are invited; neither is a member until accepting.
    4. Nobody suitable: return None. Asking again later may find someone.
    """
    current = crew_of(client, me["id"]) or pending_for(client, me["id"])
    if current:
        return current

    matches = [other for other, _score, _reason in find_matches(client, me, size=10)]
    for other in matches:
        crew = crew_of(client, other["id"])
        if crew and me["id"] not in crew.get("declined", []) and has_room(client, crew, me):
            return _update(client, crew["id"], lambda c: _invite(c, me["id"]))

    declined_partners = _declined_partners(client, me["id"])
    pair_salt = None
    for other in matches:
        if (
            other["id"] in declined_partners
            or crew_of(client, other["id"])
            or pending_for(client, other["id"])
        ):
            continue
        if pair_salt is None:
            pair_salt = _pair_id_salt(client)
        crew = {
            "id": pair_crew_id(me["id"], other["id"], pair_salt),
            "members": [],
            "companions": [],
            "invited": [me["id"], other["id"]],
            "declined": [],
            "meeting": None,
            "created_at": es.now(),
        }
        try:
            client.index(
                index=es.CREWS,
                id=crew["id"],
                document=crew,
                op_type="create",
                refresh=True,
            )
        except ConflictError:
            # The other person started this pair's crew a moment ago, or we were paired
            # before. Reuse it unless I already declined or left it.
            existing = _get(client, crew["id"])[0]
            if me["id"] in existing.get("declined", []):
                continue
            if me["id"] in existing.get("invited", []):
                return existing
            return _update(client, crew["id"], lambda c: _invite(c, me["id"]))
        return crew
    return None


def _invite(crew: dict, attendee_id: str) -> None:
    if attendee_id not in crew["invited"]:
        crew["invited"].append(attendee_id)


def accept(client: Elasticsearch, me: dict, companion: bool = False) -> dict:
    if crew_of(client, me["id"]):
        raise CrewError(409, "You are already in a crew. Leave it first.")
    pending = pending_for(client, me["id"])
    if not pending:
        raise CrewError(404, "No crew has been suggested to you")

    def join(crew: dict) -> None:
        if me["id"] not in crew["invited"]:
            raise CrewError(404, "That suggestion was withdrawn")
        if not has_room(client, crew, me, companion):
            raise CrewError(409, "That crew filled up. Ask for a new suggestion.")
        crew["invited"].remove(me["id"])
        crew["members"].append(me["id"])
        if companion:
            crew.setdefault("companions", []).append(me["id"])

    try:
        crew = _update(client, pending["id"], join)
    except CrewError as error:
        if error.status == 409 and "filled up" in error.message:
            # Don't leave a dead suggestion behind: the next suggest finds a new crew.
            _update(client, pending["id"], lambda c: _drop(c, me["id"], "invited"))
        raise
    crew = _keep_one_membership(client, me, crew)
    crew_joins.add(1)
    return crew


def _keep_one_membership(client: Elasticsearch, me: dict, joined: dict) -> dict:
    """Two accepts by the same person, sent at the same moment, can both pass the
    "already in a crew" check above and join two different crews. So look again after
    joining. If I am now in more than one crew, the one with the smallest id is kept and
    I am taken out of the others. Every racing request applies the same rule, so they
    agree on the result whatever order they run in."""
    mine = _search(client, "members", me["id"])
    if len(mine) <= 1:
        return joined
    keep = min(mine, key=lambda c: c["id"])
    for other in mine:
        if other["id"] == keep["id"]:
            continue

        def undo(c: dict) -> None:
            _drop(c, me["id"], "members")
            _drop(c, me["id"], "companions")

        _update(client, other["id"], undo)
    if keep["id"] != joined["id"]:
        raise CrewError(409, "You are already in a crew. Leave it first.")
    return joined


def _drop(crew: dict, attendee_id: str, field: str) -> None:
    if attendee_id in crew.get(field, []):
        crew[field].remove(attendee_id)


def decline(client: Elasticsearch, me: dict) -> None:
    pending = pending_for(client, me["id"])
    if not pending:
        return

    def change(crew: dict) -> None:
        _drop(crew, me["id"], "invited")
        if me["id"] not in crew["declined"]:
            crew["declined"].append(me["id"])

    _update(client, pending["id"], change)


def leave(client: Elasticsearch, me: dict) -> None:
    """Leaving sticks: you are not reassigned, and this crew is not suggested again."""
    crew = crew_of(client, me["id"])
    if not crew:
        decline(client, me)
        return

    def change(c: dict) -> None:
        _drop(c, me["id"], "members")
        _drop(c, me["id"], "companions")
        if me["id"] not in c["declined"]:
            c["declined"].append(me["id"])

    _update(client, crew["id"], change)


def set_meeting(client: Elasticsearch, me: dict, place: str, starts_at: str, tz: str) -> dict:
    crew = crew_of(client, me["id"])
    if not crew:
        raise CrewError(403, "Only crew members can set the meeting point")

    def change(c: dict) -> None:
        if me["id"] not in c["members"]:
            raise CrewError(403, "Only crew members can set the meeting point")
        c["meeting"] = {
            "place": place,
            "starts_at": starts_at,
            "timezone": tz,
            "set_by": me["name"],
        }

    return _update(client, crew["id"], change)


def why(members: list[dict]) -> str:
    """Tags at least two members share, or a plain statement. Never invented."""
    counts: dict[str, int] = {}
    for m in members:
        for tag in set(m.get("tags", [])):
            counts[tag] = counts.get(tag, 0) + 1
    shared = sorted(t for t, n in counts.items() if n >= 2)
    if shared:
        return "You share " + ", ".join(shared[:3])
    return "Suggested from your best matches"
