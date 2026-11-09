import secrets

from elasticsearch import NotFoundError
from fastapi import APIRouter, Depends, HTTPException

from .. import es
from ..auth import current_attendee
from ..models import Community, CommunityIn

router = APIRouter()


@router.post("/api/communities", status_code=201)
def create_community(body: CommunityIn, attendee: dict = Depends(current_attendee)) -> Community:
    doc = body.model_dump() | {
        "id": secrets.token_hex(12),
        "owner_id": attendee["id"],
        "created_at": es.now(),
    }
    es.get_client().index(index=es.COMMUNITIES, id=doc["id"], document=doc, refresh=True)
    return Community(**doc)


@router.get("/api/communities/{community_id}")
def get_community(community_id: str) -> Community:
    try:
        doc = es.get_client().get(index=es.COMMUNITIES, id=community_id)["_source"]
    except NotFoundError:
        raise HTTPException(404, "No such community") from None
    return Community(**doc)
