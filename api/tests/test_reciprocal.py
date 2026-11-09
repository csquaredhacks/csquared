"""A match is reciprocal when it works in both directions: they offer what I asked
for, and I offer what they asked for. Elasticsearch says which of the two matched."""

from hallway import es
from hallway.matching import find_matches, find_matches_detailed, is_reciprocal


def test_reciprocal_needs_both_directions():
    assert is_reciprocal({"asks_to_offers", "offers_to_asks", "shared_tags"})
    assert not is_reciprocal({"asks_to_offers", "similar_work", "shared_tags"})
    assert not is_reciprocal({"offers_to_asks"})
    assert not is_reciprocal(set())


def test_a_match_that_works_both_ways_is_marked_reciprocal(person):
    # Made-up words, so nobody registered by another test can match them.
    work = {"working_on": "plonkadoodle research"}
    a_client, a = person("Both A", asks="vexillarium help", offers="brindlewort lessons", **work)
    b_client, b = person("Both B", asks="brindlewort advice", offers="vexillarium tips", **work)
    _, c = person("One Way C", offers="vexillarium notes", **work)  # asks for nothing

    for_a = {m["attendee"]["id"]: m for m in a_client.get("/api/matches").json()}
    assert for_a[b["id"]]["is_reciprocal"] is True
    assert for_a[c["id"]]["is_reciprocal"] is False
    # One-way matches still say truthfully which way they work.
    assert for_a[c["id"]]["reason"].startswith("They offer what you asked for")

    for_b = {m["attendee"]["id"]: m for m in b_client.get("/api/matches").json()}
    assert for_b[a["id"]]["is_reciprocal"] is True
    assert c["id"] not in for_b or for_b[c["id"]]["is_reciprocal"] is False


def test_find_matches_still_returns_three_tuples(person):
    work = {"working_on": "snorkelwhack studies"}
    _, a = person("Shape A", asks="quibberjack help", offers="marrowfen lessons", **work)
    _, b = person("Shape B", asks="marrowfen advice", offers="quibberjack tips", **work)
    client = es.get_client()

    plain = find_matches(client, a)
    assert plain and all(len(row) == 3 for row in plain)
    other, score, reason = plain[0]
    assert other["id"] == b["id"] and score > 0
    assert reason.startswith("They offer what you asked for")

    # The detailed version is the same rows plus the query names Elasticsearch reported.
    detailed = find_matches_detailed(client, a)
    assert [row[:3] for row in detailed] == plain
    assert {"asks_to_offers", "offers_to_asks", "similar_work"} <= detailed[0][3]
