"""The matchmaking query: one Elasticsearch request that cross-matches people.

My ASKS are searched against other people's OFFERS, my OFFERS against their ASKS,
my project against their projects, plus shared tags and groups. Each of those is its
own retriever; Reciprocal Rank Fusion (RRF) merges the ranked lists into one top five.
With ELSER configured, every text retriever runs twice: BM25 (exact words) and
semantic (meaning), so "pods keep getting evicted" finds "happy to explain QoS classes".

Every query is named, and Elasticsearch reports which names matched each hit
(`matched_queries`). That is how the app can honestly say WHY two people were matched.
"""

import logging
import time

from elasticsearch import ApiError, Elasticsearch

from . import edges, es
from .config import settings

log = logging.getLogger("hallway.matching")

# When Elasticsearch refuses the hybrid query (the ELSER trial quota answers 429 when it
# runs out), matching carries on with keywords only and tries semantic again after this.
SEMANTIC_PAUSE_SECONDS = 60
_semantic_paused_until = 0.0

SOURCE_FIELDS = [
    "id", "name", "working_on", "asks", "offers", "fun_fact", "tags", "groups", "comfort",
]  # fmt: skip


# Words that say nothing about what a person needs or offers. Without this, two people
# "match" because both wrote "and" or "with", and the reason shown would not be true.
STOP_WORDS = frozenset(
    """a about after all also am an and any are as at be been both but by can could do does
    for from get had has have he help her here him his how i if in into is it its just like
    looking me more my need needs new no not of on one or our out please she so some someone
    than that the their them then there these they this to too up us use using want wants
    was we were what when where which who why will with would you your""".split()
)


def content_words(text: str) -> str:
    """The text without stop words, for word matching. Semantic search gets the full text."""
    punctuation = ".,;:!?()\"'“”‘’"
    kept = [w for w in text.split() if w.strip(punctuation).lower() not in STOP_WORDS]
    return " ".join(kept)


def _lexical(field: str, text: str, name: str) -> dict:
    return {"standard": {"query": {"match": {field: {"query": text, "_name": name}}}}}


def _semantic(field: str, text: str, name: str) -> dict:
    return {"standard": {"query": {"semantic": {"field": field, "query": text, "_name": name}}}}


def build_match_query(
    a: dict,
    exclude_ids: list[str],
    size: int = 5,
    semantic: bool | None = None,
    only_ids: list[str] | None = None,
) -> dict:
    """Search body for "who should attendee `a` meet". Pure function, easy to test.
    Empty fields are left out: Elasticsearch rejects an empty semantic query."""
    if semantic is None:
        semantic = bool(settings.elser_id)

    retrievers = []
    pairs = [  # (my text, their lexical field, their semantic field, query name)
        (a.get("asks"), "offers", "offers_semantic", "asks_to_offers"),
        (a.get("offers"), "asks", "asks_semantic", "offers_to_asks"),
        (a.get("working_on"), "working_on", "profile_semantic", "similar_work"),
    ]
    for text, lexical_field, semantic_field, name in pairs:
        if not text:
            continue
        words = content_words(text)
        if words:
            retrievers.append(_lexical(lexical_field, words, name))
        if semantic:
            retrievers.append(_semantic(semantic_field, text, name))
    if a.get("tags"):
        retrievers.append(
            {"standard": {"query": {"terms": {"tags": a["tags"], "_name": "shared_tags"}}}}
        )
    if a.get("groups"):
        retrievers.append(
            {"standard": {"query": {"terms": {"groups": a["groups"], "_name": "shared_groups"}}}}
        )

    # Never suggest yourself or someone you are already connected to.
    keep: dict = {"must_not": [{"ids": {"values": exclude_ids}}]}
    if only_ids is not None:
        # Search only inside a given set of people, for example friends of friends.
        keep["filter"] = [{"ids": {"values": only_ids}}]
    return {
        "retriever": {
            "rrf": {
                "retrievers": retrievers,
                "rank_window_size": 50,
                "rank_constant": 20,
                "filter": {"bool": keep},
            }
        },
        "size": size,
        "_source": SOURCE_FIELDS,
    }


def _short(text: str, limit: int = 90) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def explain_why(a: dict, b: dict, matched: set[str]) -> str:
    """One sentence built from which named queries matched. No LLM, so it is always true."""
    if "asks_to_offers" in matched and b.get("offers"):
        return f"They offer what you asked for: “{_short(b['offers'])}”"
    if "offers_to_asks" in matched and b.get("asks"):
        return f"You can help them: they need “{_short(b['asks'])}”"
    shared_tags = sorted(set(a.get("tags", [])) & set(b.get("tags", [])))
    if shared_tags:
        return "You both care about " + ", ".join(shared_tags[:3])
    if "similar_work" in matched:
        return f"You are working on similar things: “{_short(b['working_on'])}”"
    shared_groups = sorted(set(a.get("groups", [])) & set(b.get("groups", [])))
    if shared_groups:
        return f"You are both in {shared_groups[0]}"
    return "Your profiles overlap"


def default_icebreaker(b: dict) -> str:
    """Used when no LLM-written icebreaker exists for the pair."""
    first_name = b["name"].split()[0]
    if b.get("fun_fact"):
        return f"Ask {first_name} about this: {_short(b['fun_fact'])}"
    return f"Ask {first_name} what the hardest part of “{_short(b['working_on'], 60)}” has been."


def is_reciprocal(matched: set[str]) -> bool:
    """True when the match works in both directions: they offer something I asked for
    AND I offer something they asked for. `matched` is the set of query names that
    Elasticsearch reported for the hit, so this is evidence, not a guess."""
    return {"asks_to_offers", "offers_to_asks"} <= matched


def search_people(
    client: Elasticsearch,
    a: dict,
    exclude: list[str],
    size: int,
    only_ids: list[str] | None = None,
    semantic: bool | None = None,
) -> list[dict]:
    """Run the match query and return the hits. Hybrid (keywords plus meaning) when ELSER
    is configured and answering. If Elasticsearch refuses the hybrid query, the same
    question is asked again with keywords only, so a person still gets their five.
    `semantic=False` skips the semantic half without trying it."""
    global _semantic_paused_until
    if semantic is None:
        semantic = bool(settings.elser_id)
    if semantic and time.monotonic() >= _semantic_paused_until:
        body = build_match_query(a, exclude, size, semantic=True, only_ids=only_ids)
        try:
            # No retries: a rate-limited model answers slowly, and the keyword query
            # below is a better use of the person's wait than asking again.
            return client.options(max_retries=0).search(index=es.ATTENDEES, body=body)["hits"][
                "hits"
            ]
        except ApiError as error:
            _semantic_paused_until = time.monotonic() + SEMANTIC_PAUSE_SECONDS
            log.warning(
                "hybrid match query refused (status %s); keywords only for %d seconds",
                error.status_code,
                SEMANTIC_PAUSE_SECONDS,
            )
    body = build_match_query(a, exclude, size, semantic=False, only_ids=only_ids)
    return client.search(index=es.ATTENDEES, body=body)["hits"]["hits"]


def find_matches_detailed(
    client: Elasticsearch,
    a: dict,
    size: int = 5,
    only_ids: list[str] | None = None,
    semantic: bool | None = None,
) -> list[tuple[dict, float, str, set[str]]]:
    """Run the query for attendee `a`. Returns (other attendee, score, reason, matched)
    tuples, where `matched` is the names of the queries that matched that person."""
    exclude = [a["id"], *edges.connected_ids(client, a["id"])]
    found = []
    for h in search_people(client, a, exclude, size, only_ids, semantic):
        other = h["_source"]
        matched = set(h.get("matched_queries", []))
        found.append((other, h["_score"] or 0.0, explain_why(a, other, matched), matched))
    return found


def find_matches(
    client: Elasticsearch,
    a: dict,
    size: int = 5,
    only_ids: list[str] | None = None,
    semantic: bool | None = None,
) -> list[tuple[dict, float, str]]:
    """Returns (other attendee, score, reason) tuples. Most callers unpack exactly these
    three; the ones that need the matched query names call find_matches_detailed."""
    detailed = find_matches_detailed(client, a, size, only_ids, semantic)
    return [(other, score, reason) for other, score, reason, _matched in detailed]
