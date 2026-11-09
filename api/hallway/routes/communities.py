"""Communities: an affiliation people choose for themselves (working plan step 2).

One document per community:

    {id, name, description, luma_url, owner_id, members: [attendee ids], created_at}

- `owner_id` is the organizer who created it. Only they may edit it. Never returned.
- `members` are people who joined by their own request. The id always comes from the
  session cookie, so nobody can add someone else. The organizer is not a member unless
  they join too. Only the count is ever returned.

Joining a community does not change the `groups` on a person's profile. Those are
words the person typed and they show on the public profile; a community name added
there could not be taken out again on leaving without guessing who put it there.

Joining, leaving and editing go through `_update`, which writes back only if the
document did not change in between (if_seq_no/if_primary_term), so two people joining
at the same moment are both kept.
"""

import secrets

from elasticsearch import ConflictError, Elasticsearch, NotFoundError
from fastapi import APIRouter, Depends, HTTPException

from .. import es
from ..auth import current_attendee, optional_attendee
from ..models import Community, CommunityIn, CommunityUpdate

router = APIRouter()

MAX_JOINED = 50  # communities one person can be a member of at once
MAX_LISTED = 100  # most communities /api/me/communities returns
RETRIES = 5


def _view(doc: dict, viewer: dict | None) -> Community:
    """The public shape. Members become a count, and the owner becomes a yes or no
    about the caller only."""
    members = doc.get("members", [])  # communities created before members existed
    return Community(
        id=doc["id"],
        name=doc["name"],
        description=doc["description"],
        luma_url=doc["luma_url"],
        member_count=len(members),
        is_member=viewer is not None and viewer["id"] in members,
        is_organizer=viewer is not None and viewer["id"] == doc["owner_id"],
    )


def _get(client: Elasticsearch, community_id: str) -> tuple[dict, int, int]:
    try:
        found = client.get(index=es.COMMUNITIES, id=community_id)
    except NotFoundError:
        raise HTTPException(404, "No such community") from None
    return found["_source"], found["_seq_no"], found["_primary_term"]


def _update(client: Elasticsearch, community_id: str, change) -> dict:
    """Read, apply `change(doc)`, write back only if nobody wrote in between. On a
    conflict, read again and re-apply, so somebody else's join is never overwritten."""
    for _ in range(RETRIES):
        doc, seq_no, term = _get(client, community_id)
        change(doc)
        try:
            client.index(
                index=es.COMMUNITIES,
                id=community_id,
                document=doc,
                refresh=True,
                if_seq_no=seq_no,
                if_primary_term=term,
            )
            return doc
        except ConflictError:
            continue
    raise HTTPException(409, "This community changed while you were saving. Try again.")


@router.post("/api/communities", status_code=201)
def create_community(body: CommunityIn, attendee: dict = Depends(current_attendee)) -> Community:
    doc = body.model_dump() | {
        "id": secrets.token_hex(12),
        "owner_id": attendee["id"],
        "members": [],
        "created_at": es.now(),
    }
    es.get_client().index(index=es.COMMUNITIES, id=doc["id"], document=doc, refresh=True)
    return _view(doc, attendee)


@router.get("/api/communities/{community_id}")
def get_community(
    community_id: str, viewer: dict | None = Depends(optional_attendee)
) -> Community:
    """Public invitation page. A signed-in person also learns whether they joined."""
    doc, _, _ = _get(es.get_client(), community_id)
    return _view(doc, viewer)


@router.patch("/api/communities/{community_id}")
def edit_community(
    community_id: str, body: CommunityUpdate, me: dict = Depends(current_attendee)
) -> Community:
    """Only the organizer who created the community may change its invitation."""
    client = es.get_client()
    doc, _, _ = _get(client, community_id)
    if doc["owner_id"] != me["id"]:
        raise HTTPException(403, "Only the organizer who created this community can edit it")
    changes = body.model_dump(exclude_none=True)
    if not changes:
        return _view(doc, me)
    return _view(_update(client, community_id, lambda c: c.update(changes)), me)


@router.post("/api/communities/{community_id}/members")
def join_community(community_id: str, me: dict = Depends(current_attendee)) -> Community:
    """I join. Joining again changes nothing. This is separate from the Luma RSVP."""
    client = es.get_client()
    doc, _, _ = _get(client, community_id)
    if me["id"] in doc.get("members", []):
        return _view(doc, me)
    # A limit per person keeps "my communities" a short, complete list. It is checked
    # before the write, so one person joining many at the very same moment could pass it.
    joined = client.count(index=es.COMMUNITIES, query={"term": {"members": me["id"]}})["count"]
    if joined >= MAX_JOINED:
        raise HTTPException(
            409, f"You are already in {MAX_JOINED} communities. Leave one to join another."
        )

    def add(community: dict) -> None:
        members = community.setdefault("members", [])
        if me["id"] not in members:
            members.append(me["id"])

    return _view(_update(client, community_id, add), me)


@router.delete("/api/communities/{community_id}/members")
def leave_community(community_id: str, me: dict = Depends(current_attendee)) -> Community:
    """I leave. Leaving a community I am not in changes nothing."""
    client = es.get_client()
    doc, _, _ = _get(client, community_id)
    if me["id"] not in doc.get("members", []):
        return _view(doc, me)

    def remove(community: dict) -> None:
        if me["id"] in community.get("members", []):
            community["members"].remove(me["id"])

    return _view(_update(client, community_id, remove), me)


@router.get("/api/me/communities")
def my_communities(me: dict = Depends(current_attendee)) -> list[Community]:
    """The communities I joined and the ones I created, by name. Private to me."""
    mine = {
        "bool": {
            "should": [{"term": {"members": me["id"]}}, {"term": {"owner_id": me["id"]}}],
            "minimum_should_match": 1,
        }
    }
    hits = es.get_client().search(
        index=es.COMMUNITIES, query=mine, size=MAX_LISTED, sort=[{"created_at": "desc"}]
    )["hits"]["hits"]
    return sorted((_view(h["_source"], me) for h in hits), key=lambda c: c.name.lower())
