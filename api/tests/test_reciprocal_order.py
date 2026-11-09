"""Matches that work both ways come first, and the cap of five comes after the sort."""


def _ids(matches):
    return [m["attendee"]["id"] for m in matches]


def test_a_two_way_match_is_ranked_before_a_one_way_match(person):
    topic = "kelpforge"  # made-up words, so people from other tests do not match
    ana, _ = person("Ana kelpforge", asks=topic, offers="zephyrweave", working_on="anaonlywork")
    # Ben needs what Ana offers and offers what Ana needs: both directions.
    _, ben = person("Ben kelpforge", asks="zephyrweave", offers=topic, working_on="benonlywork")
    # Carla offers what Ana needs but needs nothing Ana offers: one direction only.
    _, carla = person("Carla kelpforge", offers=topic, working_on="carlaonlywork")

    matches = ana.get("/api/matches").json()
    by_id = {m["attendee"]["id"]: m for m in matches}
    assert by_id[ben["id"]]["is_reciprocal"] is True
    assert by_id[carla["id"]]["is_reciprocal"] is False
    assert _ids(matches).index(ben["id"]) < _ids(matches).index(carla["id"])


def test_a_two_way_match_is_not_pushed_off_the_page_by_stronger_one_way_matches(person):
    topic = "driftloom"
    ana, _ = person(
        "Ana driftloom",
        asks=topic,
        offers="quillsmith",
        working_on="driftloom studio",
        tags=["driftloom"],
    )
    # Seven people who can help Ana but need nothing from her. They also share her work
    # and tag, so on raw score they outrank Ben. The cap must come after the sort.
    for i in range(7):
        person(
            f"One-way {i} driftloom",
            offers=topic,
            working_on="driftloom studio",
            tags=["driftloom"],
        )
    _, ben = person("Ben driftloom", asks="quillsmith", offers=topic, working_on="benonlywork")

    matches = ana.get("/api/matches").json()
    assert len(matches) <= 5
    assert matches[0]["attendee"]["id"] == ben["id"]
    assert matches[0]["is_reciprocal"] is True
    assert all(m["is_reciprocal"] is False for m in matches[1:])
