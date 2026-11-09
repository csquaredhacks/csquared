from hallway.matching import build_match_query, default_icebreaker, explain_why

ADA = {
    "id": "ada", "name": "Ada Example", "working_on": "a kubernetes operator",
    "asks": "help with memory limits", "offers": "go mentoring",
    "tags": ["go", "k8s"], "groups": ["Students"], "fun_fact": "",
}  # fmt: skip


def names(body: dict) -> list[str]:
    out = []
    for r in body["retriever"]["rrf"]["retrievers"]:
        (clause,) = r["standard"]["query"].values()
        out.append(clause.get("_name") or next(iter(clause.values())).get("_name"))
    return out


def test_lexical_mode_has_one_retriever_per_signal():
    body = build_match_query(ADA, ["ada"], semantic=False)
    assert names(body) == [
        "asks_to_offers", "offers_to_asks", "similar_work", "shared_tags", "shared_groups",
    ]  # fmt: skip


def test_semantic_mode_adds_a_semantic_retriever_per_text_signal():
    body = build_match_query(ADA, ["ada"], semantic=True)
    assert names(body).count("asks_to_offers") == 2
    semantic = [
        r for r in body["retriever"]["rrf"]["retrievers"] if "semantic" in r["standard"]["query"]
    ]
    assert {r["standard"]["query"]["semantic"]["field"] for r in semantic} == {
        "offers_semantic", "asks_semantic", "profile_semantic",
    }  # fmt: skip


def test_empty_fields_are_left_out():
    # Review focus 1: an attendee with no asks/offers must not send an empty query.
    quiet = ADA | {"asks": "", "offers": "", "tags": [], "groups": []}
    assert names(build_match_query(quiet, ["ada"], semantic=True)) == ["similar_work"] * 2


def test_size_window_and_exclusions_are_always_set():
    body = build_match_query(ADA, ["ada", "bob"], size=5, semantic=False)
    rrf = body["retriever"]["rrf"]
    assert body["size"] == 5
    assert rrf["rank_window_size"] == 50
    assert rrf["filter"]["bool"]["must_not"] == [{"ids": {"values": ["ada", "bob"]}}]


def test_reason_follows_the_matched_queries():
    bob = {"name": "Bob Sample", "working_on": "sre", "asks": "learn go",
           "offers": "requests, limits and QoS", "tags": ["k8s"], "groups": []}  # fmt: skip
    assert "They offer what you asked for" in explain_why(ADA, bob, {"asks_to_offers"})
    assert "they need" in explain_why(ADA, bob, {"offers_to_asks"})
    assert explain_why(ADA, bob, {"shared_tags"}) == "You both care about k8s"
    assert explain_why(ADA, bob | {"tags": []}, set()) == "Your profiles overlap"


def test_default_icebreaker_prefers_the_fun_fact():
    assert "juggles" in default_icebreaker(
        {"name": "Bob S", "fun_fact": "juggles", "working_on": "x"}
    )
    assert "Ask Bob" in default_icebreaker({"name": "Bob S", "fun_fact": "", "working_on": "x"})
