"""Group messages: read and send inside a community you joined.

One document per message in the MESSAGES index:

    {id, community_id, author_id, author_name, text, created_at}

- Only members of the community may read or send. A missing community is
  404 first; a non-member is 403 after that, so membership is never leaked
  through a different error.
- `author_id` is stored so the author can be checked later, but never
  returned. Members see the author's name, which they already show on
  their profile.
"""

import secrets

from fastapi import APIRouter, Depends, HTTPException, Query

from .. import es
from ..auth import current_attendee
from ..models import Message, MessageIn
from .communities import _get

router = APIRouter()

MAX_LISTED = 100  # most messages one read returns; the default is 50


def _require_member(community_id: str, me: dict) -> dict:
    doc, _, _ = _get(es.get_client(), community_id)
    if me["id"] not in doc.get("members", []):
        raise HTTPException(403, "Only members of this community can use its group chat")
    return doc


def _view(doc: dict) -> Message:
    return Message(
        id=doc["id"],
        author_name=doc["author_name"],
        text=doc["text"],
        created_at=doc["created_at"],
    )


@router.get("/api/communities/{community_id}/messages")
def list_messages(
    community_id: str,
    me: dict = Depends(current_attendee),
    limit: int = Query(50, ge=1, le=MAX_LISTED),
) -> list[Message]:
    """The community's messages, oldest first. Members only."""
    _require_member(community_id, me)
    hits = es.get_client().search(
        index=es.MESSAGES,
        query={"term": {"community_id": community_id}},
        size=limit,
        sort=[{"created_at": "asc"}],
    )["hits"]["hits"]
    return [_view(h["_source"]) for h in hits]


@router.post("/api/communities/{community_id}/messages", status_code=201)
def send_message(
    community_id: str, body: MessageIn, me: dict = Depends(current_attendee)
) -> Message:
    """I send one message to a community I joined. Members only."""
    _require_member(community_id, me)
    doc = {
        "id": secrets.token_hex(12),
        "community_id": community_id,
        "author_id": me["id"],
        "author_name": me["name"],
        "text": body.text,
        "created_at": es.now(),
    }
    es.get_client().index(index=es.MESSAGES, id=doc["id"], document=doc, refresh=True)
    return _view(doc)
