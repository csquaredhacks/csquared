"""The organizer board: what the crowd needs, in counts only.

Everything here is an aggregate. No name, id, free text or affiliation leaves this
module, and a number that describes fewer than MIN_PEOPLE people is left out, so a
small group cannot be picked out of the totals.
"""

from elasticsearch import Elasticsearch

from . import es
from .telemetry import set_funnel

CANDIDATES = 100  # the most used tags are the words we look for in asks and offers
TOPICS = 15  # how many topics the board shows
MIN_PEOPLE = 3
MAX_CREWS = 2000


def _attendees(client: Elasticsearch) -> tuple[int, list[str], dict[str, int]]:
    """How many people registered, their most used tags, and how they like to meet."""
    found = client.search(
        index=es.ATTENDEES,
        size=0,
        track_total_hits=True,
        aggs={
            "tags": {"terms": {"field": "tags", "size": CANDIDATES}},
            "comfort": {"terms": {"field": "comfort"}},
        },
    )
    aggs = found["aggregations"]
    tags = [b["key"] for b in aggs["tags"]["buckets"]]
    comfort = {b["key"]: b["doc_count"] for b in aggs["comfort"]["buckets"]}
    return found["hits"]["total"]["value"], tags, comfort


def _topics(client: Elasticsearch, tags: list[str]) -> list[dict]:
    """For each topic, how many people ask about it and how many offer it. One request:
    a `filters` aggregation with two phrase filters per topic. A topic is kept only when
    at least MIN_PEOPLE people are behind it. It counts words, not meaning, and the page
    says so."""
    if not tags:
        return []
    filters = {}
    for number, tag in enumerate(tags):
        phrase = tag.replace("-", " ")
        filters[f"asks:{number}"] = {"match_phrase": {"asks": phrase}}
        filters[f"offers:{number}"] = {"match_phrase": {"offers": phrase}}
    buckets = client.search(
        index=es.ATTENDEES, size=0, aggs={"topics": {"filters": {"filters": filters}}}
    )["aggregations"]["topics"]["buckets"]
    topics = []
    for number, tag in enumerate(tags):
        asking = buckets[f"asks:{number}"]["doc_count"]
        offering = buckets[f"offers:{number}"]["doc_count"]
        if asking + offering >= MIN_PEOPLE:
            topics.append({"topic": tag, "asking": asking, "offering": offering})
    # The widest gap first: that is the session an organizer can still schedule.
    return sorted(topics, key=lambda t: (t["offering"] - t["asking"], t["topic"]))[:TOPICS]


def _groups(client: Elasticsearch) -> tuple[int, int, int]:
    """People who accepted an arrival group, groups with at least one member, and how
    many of those have agreed where and when to meet."""
    hits = client.search(
        index=es.CREWS,
        query={"exists": {"field": "members"}},
        size=MAX_CREWS,
        source=["members", "meeting"],
    )["hits"]["hits"]
    crews = [h["_source"] for h in hits if h["_source"].get("members")]
    people = sum(len(c["members"]) for c in crews)
    return people, len(crews), sum(1 for c in crews if c.get("meeting"))


def _edges(client: Elasticsearch) -> dict[str, int]:
    buckets = client.search(
        index=es.EDGES, size=0, aggs={"kinds": {"terms": {"field": "kind"}}}
    )["aggregations"]["kinds"]["buckets"]
    return {b["key"]: b["doc_count"] for b in buckets}


def refresh_funnel(client: Elasticsearch) -> None:
    """Refresh the organizer funnel using counts, without loading the full board."""
    registered = client.count(index=es.ATTENDEES)["count"]
    in_groups = client.search(
        index=es.CREWS,
        size=0,
        query={"exists": {"field": "members"}},
        aggs={"members": {"value_count": {"field": "members"}}},
    )["aggregations"]["members"]["value"]
    edges = _edges(client)
    checked_in = client.count(index=es.CHECKINS)["count"]
    set_funnel(
        {
            "registered": registered,
            "in_group": int(in_groups),
            "planned": edges.get("planned", 0),
            "met": edges.get("connected", 0),
            "checked_in": checked_in,
        }
    )


def board(client: Elasticsearch) -> dict:
    registered, tags, comfort = _attendees(client)
    in_groups, groups, groups_with_meeting = _groups(client)
    edges = _edges(client)
    checked_in = client.count(index=es.CHECKINS)["count"]
    result = {
        "registered": registered,
        "in_groups": in_groups,
        "groups": groups,
        "groups_with_meeting": groups_with_meeting,
        "invitations": edges.get("invited", 0),
        "plans": edges.get("planned", 0),
        "meetings": edges.get("connected", 0),
        "checked_in": checked_in,
        "topics": _topics(client, tags),
        "comfort": [
            {"key": key, "count": count}
            for key, count in sorted(comfort.items())
            if count >= MIN_PEOPLE
        ],
    }
    # The same numbers feed the hallway.funnel gauge, so Dash0 shows what this page shows.
    set_funnel(
        {
            "registered": registered,
            "in_group": in_groups,
            "planned": result["plans"],
            "met": result["meetings"],
            "checked_in": checked_in,
        }
    )
    return result
