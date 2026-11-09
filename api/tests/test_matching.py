import json

from elastic_transport import ApiResponseMeta
from elasticsearch import ApiError

from hallway import es, matcher, matching
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


# ---- When Elasticsearch refuses the hybrid query, matching carries on with keywords ----


class _RateLimited:
    """Wraps the real client. Any search that contains a semantic query is refused the
    way the ELSER trial quota refuses it; everything else goes to Elasticsearch."""

    def __init__(self, real):
        self.real = real
        self.semantic_attempts = 0

    def options(self, **_):
        return self

    def search(self, **kwargs):
        if "semantic" in json.dumps(kwargs.get("body", {})):
            self.semantic_attempts += 1
            raise ApiError("rate limited", ApiResponseMeta(429, "1.1", {}, 0.1, None), {})
        return self.real.search(**kwargs)

    def __getattr__(self, name):
        return getattr(self.real, name)


def test_a_refused_hybrid_query_falls_back_to_keywords(person, monkeypatch):
    _, ana = person("Ana Fallback", asks="glorptastic help", working_on="glorptastic")
    _, ben = person("Ben Fallback", offers="glorptastic help", working_on="glorptastic")
    monkeypatch.setattr(matching.settings, "elser_id", ".elser-2-elastic")
    monkeypatch.setattr(matching, "_semantic_paused_until", 0.0)
    client = _RateLimited(es.get_client())

    found = matching.find_matches(client, ana)
    assert ben["id"] in [other["id"] for other, _score, _reason in found]
    assert client.semantic_attempts == 1

    # Within the pause the semantic half is not tried again: no slow failed call per person.
    matching.find_matches(client, ana)
    assert client.semantic_attempts == 1


def test_the_scheduled_matcher_pass_never_uses_semantic_search(person, monkeypatch):
    person("Ana Reconcile", asks="blorfing", working_on="blorfing")
    person("Ben Reconcile", offers="blorfing", working_on="blorfing")
    monkeypatch.setattr(matching.settings, "elser_id", ".elser-2-elastic")
    monkeypatch.setattr(matching, "_semantic_paused_until", 0.0)
    client = _RateLimited(es.get_client())
    matcher.run_once(client, llm_budget=0)
    assert client.semantic_attempts == 0
