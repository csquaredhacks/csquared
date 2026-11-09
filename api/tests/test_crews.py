"""Arrival groups (working plan step 3): suggested, then accepted, declined or left.
Each test uses its own made-up topic words so people from other tests don't match."""

from concurrent.futures import ThreadPoolExecutor
from importlib import reload
from threading import Barrier, Event, local

from fastapi.testclient import TestClient

from hallway import crews, es
from hallway.main import app


def _pair(person, topic: str, a_comfort: str = "open", b_comfort: str = "open"):
    a = person(f"Ana {topic}", asks=f"{topic}", working_on=f"{topic}", comfort=a_comfort)
    b = person(f"Ben {topic}", offers=f"{topic}", working_on=f"{topic}", comfort=b_comfort)
    return a, b


def test_nothing_happens_until_you_accept(person):
    (ana, ana_me), (ben, ben_me) = _pair(person, "zorblax")
    assert ana.get("/api/crew").json() == {
        "status": "none",
        "crew": None,
        "bringing_companion": False,
        "left_alone": False,
    }

    out = ana.post("/api/crew/suggest").json()
    assert out["status"] == "suggested"
    assert out["crew"]["members"] == []  # nobody has accepted yet
    # Ben was suggested the same crew, but is not in it until he says yes.
    assert ben.get("/api/crew").json()["status"] == "suggested"

    joined = ana.post("/api/crew/accept", json={}).json()
    assert joined["status"] == "member"
    assert [m["id"] for m in joined["crew"]["members"]] == [ana_me["id"]]
    assert ben.get("/api/crew").json()["crew"]["members"][0]["id"] == ana_me["id"]


def test_concurrent_suggestions_create_one_crew_for_a_pair(person, monkeypatch):
    (ana, ana_me), _ = _pair(person, "racecrew")
    client = es.get_client()
    barrier = Barrier(2)
    original_index = client.index

    def synchronized_index(*args, **kwargs):
        if kwargs.get("index") == es.CREWS:
            barrier.wait(timeout=5)
        return original_index(*args, **kwargs)

    monkeypatch.setattr(client, "index", synchronized_index)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: crews.suggest(client, ana_me), range(2)))

    assert results[0]["id"] == results[1]["id"]
    stored = client.get(index=es.CREWS, id=results[0]["id"])
    assert stored["_version"] == 1


def test_suggestion_create_conflict_returns_existing_crew(monkeypatch):
    class CreateConflict(Exception):
        pass

    class Client:
        def __init__(self):
            self.index_kwargs = None

        def search(self, **_kwargs):
            return {"hits": {"hits": []}}

        def index(self, **kwargs):
            self.index_kwargs = kwargs
            raise CreateConflict

    client = Client()
    me = {"id": "z-person"}
    other = {"id": "a-person"}
    existing = {
        "id": crews.pair_crew_id("a-person", "z-person", b"test-salt"),
        "members": [],
        "invited": ["a-person", "z-person"],
        "declined": [],
    }
    monkeypatch.setattr(crews, "ConflictError", CreateConflict)
    monkeypatch.setattr(crews, "_pair_id_salt", lambda _client: b"test-salt")
    monkeypatch.setattr(crews, "find_matches", lambda *_args, **_kwargs: [(other, 1, "match")])
    monkeypatch.setattr(crews, "_get", lambda _client, _crew_id: (existing, 0, 1))

    result = crews.suggest(client, me)

    assert result == existing
    assert client.index_kwargs["id"] == existing["id"]
    assert client.index_kwargs["document"]["invited"] == [me["id"], other["id"]]
    assert client.index_kwargs["op_type"] == "create"


def test_pair_crew_id_is_stable_and_reveals_no_attendee_id():
    salt = b"unit-test-salt"
    first = crews.pair_crew_id("aaa111", "bbb222", salt)
    assert first == crews.pair_crew_id("bbb222", "aaa111", salt)
    assert "aaa111" not in first and "bbb222" not in first


def test_a_declined_pair_crew_is_not_suggested_again(person, monkeypatch):
    monkeypatch.delenv("CREW_ID_SALT", raising=False)
    (ana, _), (ben, _) = _pair(person, "wobblequince")
    ana.post("/api/crew/suggest")
    ana.post("/api/crew/decline")
    ben.post("/api/crew/decline")

    # A fresh module instance models a process restart without CREW_ID_SALT.
    reload(crews)
    out = ana.post("/api/crew/suggest").json()
    assert out["status"] == "none"  # the old pair crew was not handed back


def test_legacy_declined_pair_is_not_suggested_again(person):
    (ana, ana_me), (ben, ben_me) = _pair(person, "legacydecline")
    client = es.get_client()
    legacy_crew = {
        "id": "old-random-pair-id",
        "members": [],
        "companions": [],
        "invited": [],
        "declined": [ana_me["id"], ben_me["id"]],
        "meeting": None,
        "created_at": es.now(),
    }
    client.index(
        index=es.CREWS,
        id=legacy_crew["id"],
        document=legacy_crew,
        refresh=True,
    )

    out = ana.post("/api/crew/suggest").json()

    assert out["status"] == "none"


def test_declined_group_does_not_block_everyone_as_a_pair(monkeypatch):
    crews_with_declines = [
        {"members": [], "invited": [], "declined": ["ana", "pair-partner"]},
        {
            "members": ["member-one", "member-two"],
            "invited": ["invitee"],
            "declined": ["ana"],
        },
    ]
    monkeypatch.setattr(crews, "_search", lambda *_args, **_kwargs: crews_with_declines)

    assert crews._declined_partners(None, "ana") == {"pair-partner"}


def test_a_second_person_joins_the_first_persons_crew(person):
    (ana, ana_me), (ben, ben_me) = _pair(person, "quillfeather")
    ana.post("/api/crew/suggest")
    ana.post("/api/crew/accept", json={})
    cat, _ = person("Cat quillfeather", offers="quillfeather", working_on="quillfeather")
    out = cat.post("/api/crew/suggest").json()
    assert out["status"] == "suggested"
    assert [m["id"] for m in out["crew"]["members"]] == [ana_me["id"]]


def test_pending_suggestions_and_declines_stay_private(person):
    (ana, _), (ben, ben_me) = _pair(person, "vexmoor")
    ana.post("/api/crew/suggest")
    ana.post("/api/crew/accept", json={})
    ben.post("/api/crew/decline")
    crew = ana.get("/api/crew").json()["crew"]
    text = str(crew)
    assert ben_me["id"] not in text  # Ana never learns Ben was suggested or said no
    assert set(crew) == {"id", "members", "seats_taken", "limit", "why", "meeting"}


def test_one_on_one_person_never_ends_up_in_a_crew_of_three(person):
    (ana, _), (ben, _) = _pair(person, "plinthwhorl", a_comfort="one_on_one")
    ana.post("/api/crew/suggest")
    assert ana.post("/api/crew/accept", json={}).json()["crew"]["limit"] == 2
    assert ben.post("/api/crew/accept", json={}).status_code == 200
    cat, _ = person("Cat plinthwhorl", offers="plinthwhorl", working_on="plinthwhorl")
    out = cat.post("/api/crew/suggest").json()
    # The pair is full, so Cat is not offered it.
    assert out["crew"] is None or len(out["crew"]["members"]) == 0


def test_a_companion_takes_a_seat(person):
    (ana, _), (ben, ben_me) = _pair(person, "brindleglow", a_comfort="one_on_one")
    ana.post("/api/crew/suggest")
    out = ana.post("/api/crew/accept", json={"companion": True}).json()
    assert out["bringing_companion"] is True
    assert out["crew"]["seats_taken"] == 2
    response = ben.post("/api/crew/accept", json={})
    assert response.status_code == 409  # Ana + companion fill a one_on_one crew
    assert ben.get("/api/crew").json()["status"] == "none"  # dead suggestion cleared

    next_crew = {
        "id": f"after-full-{ben_me['id']}",
        "members": [],
        "companions": [],
        "invited": [ben_me["id"]],
        "declined": [],
        "meeting": None,
        "created_at": es.now(),
    }
    es.get_client().index(
        index=es.CREWS,
        id=next_crew["id"],
        document=next_crew,
        refresh=True,
    )
    assert ben.post("/api/crew/accept", json={}).status_code == 200


def test_two_people_racing_for_the_last_seat_cannot_both_get_it(person):
    client = es.get_client()
    (ana, ana_me), _ = _pair(person, "grumbletoast", a_comfort="one_on_one")
    others = [person(f"Racer{i} grumbletoast", offers="grumbletoast") for i in range(2)]
    crew = {
        "id": "race-" + ana_me["id"],
        "members": [ana_me["id"]],
        "companions": [],
        "invited": [me["id"] for _, me in others],
        "declined": [],
        "meeting": None,
        "created_at": es.now(),
    }
    client.index(index=es.CREWS, id=crew["id"], document=crew, refresh=True)

    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(lambda o: o[0].post("/api/crew/accept", json={}).status_code, others))
    assert sorted(codes) == [200, 409]
    stored = client.get(index=es.CREWS, id=crew["id"])["_source"]
    assert len(stored["members"]) == 2


def test_a_success_is_not_returned_for_a_crew_removed_by_a_racing_accept(person, monkeypatch):
    """A second accept must not succeed while the first is still joining another crew."""
    ana, ana_me = person("Ana twocrews", working_on="twocrews")
    client = es.get_client()
    for crew_id in ("twocrews-a", "twocrews-b"):
        client.index(
            index=es.CREWS,
            id=crew_id,
            document={
                "id": crew_id,
                "members": [],
                "companions": [],
                "invited": [ana_me["id"]],
                "declined": [],
                "meeting": None,
                "created_at": es.now(),
            },
            refresh=True,
        )

    turn = local()

    def pending_for(es_client, _attendee_id):
        return crews._get(es_client, turn.crew_id)[0]

    monkeypatch.setattr(crews, "pending_for", pending_for)
    paused, resumed = Event(), Event()
    original_has_room = crews.has_room

    def pause_first_join(es_client, crew, joiner, companion=False):
        if crew["id"] == "twocrews-a":
            paused.set()
            assert resumed.wait(timeout=5)
        return original_has_room(es_client, crew, joiner, companion)

    monkeypatch.setattr(crews, "has_room", pause_first_join)

    def accept_one(crew_id: str) -> str:
        turn.crew_id = crew_id
        try:
            return crews.accept(client, ana_me)["id"]
        except crews.CrewError as error:
            return str(error.status)

    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(accept_one, "twocrews-a")
        assert paused.wait(timeout=5)
        second_result = accept_one("twocrews-b")
        resumed.set()
        first_result = first.result(timeout=5)

    member_of = [c["id"] for c in crews._search(client, "members", ana_me["id"])]
    assert member_of == ["twocrews-a"]
    assert first_result == "twocrews-a"
    assert second_result == "409"
    assert ana.get("/api/crew").json()["crew"]["id"] == "twocrews-a"


def test_a_seat_left_behind_by_a_killed_request_does_not_lock_the_person_out(person):
    """The API can be killed between claiming a seat and joining (the out-of-memory demo
    does that). The leftover seat must not stop the person from ever joining a crew."""
    (ana, ana_me), _ = _pair(person, "orphanseat")
    client = es.get_client()
    client.index(
        index=es.CREWS,
        id=crews._seat_id(ana_me["id"]),
        document={
            "attendee_id": ana_me["id"],
            "crew_id": "a-crew-she-never-joined",
            "claimed_at": "2026-01-01T00:00:00+00:00",
        },
        refresh=True,
    )
    ana.post("/api/crew/suggest")
    assert ana.post("/api/crew/accept", json={}).status_code == 200
    assert ana.get("/api/crew").json()["status"] == "member"


def test_a_fresh_seat_still_blocks_a_second_accept(person):
    (ana, ana_me), _ = _pair(person, "freshseat")
    client = es.get_client()
    client.index(
        index=es.CREWS,
        id=crews._seat_id(ana_me["id"]),
        document={"attendee_id": ana_me["id"], "crew_id": "other", "claimed_at": es.now()},
        refresh=True,
    )
    ana.post("/api/crew/suggest")
    assert ana.post("/api/crew/accept", json={}).status_code == 409


def test_leaving_sticks(person):
    (ana, ana_me), (ben, _) = _pair(person, "snorkelbat")
    ana.post("/api/crew/suggest")
    crew_id = ana.post("/api/crew/accept", json={}).json()["crew"]["id"]
    assert ana.delete("/api/crew").json()["status"] == "none"
    assert ana.get("/api/crew").json()["status"] == "none"  # not reassigned
    ben.post("/api/crew/accept", json={})
    again = ana.post("/api/crew/suggest").json()
    assert again["crew"] is None or again["crew"]["id"] != crew_id

    next_crew = {
        "id": f"after-leave-{ana_me['id']}",
        "members": [],
        "companions": [],
        "invited": [ana_me["id"]],
        "declined": [],
        "meeting": None,
        "created_at": es.now(),
    }
    es.get_client().index(
        index=es.CREWS,
        id=next_crew["id"],
        document=next_crew,
        refresh=True,
    )
    assert ana.post("/api/crew/accept", json={}).status_code == 200


def test_when_the_other_person_leaves_i_am_told_and_nothing_is_changed_for_me(person):
    (ana, ana_me), (ben, _) = _pair(person, "mossgarnet")
    ana.post("/api/crew/suggest")
    first = ana.post("/api/crew/accept", json={}).json()
    assert first["left_alone"] is False  # alone only because nobody else answered yet
    ben.post("/api/crew/accept", json={})
    ben.delete("/api/crew")

    mine = ana.get("/api/crew").json()
    assert mine["left_alone"] is True
    assert mine["status"] == "member"  # still in the same crew: nobody moved me
    assert mine["crew"]["id"] == first["crew"]["id"]
    assert [m["id"] for m in mine["crew"]["members"]] == [ana_me["id"]]


def test_asking_for_a_replacement_leaves_the_old_crew_and_only_suggests_a_new_one(person):
    (ana, ana_me), (ben, _) = _pair(person, "larkspindle")
    cho, _ = person("Cho larkspindle", offers="larkspindle", working_on="larkspindle")
    ana.post("/api/crew/suggest")
    old = ana.post("/api/crew/accept", json={}).json()["crew"]["id"]
    ben.post("/api/crew/accept", json={})
    ben.delete("/api/crew")

    out = ana.post("/api/crew/replace").json()
    assert out["status"] in ("suggested", "none")  # never joined on my behalf
    assert out["crew"] is None or out["crew"]["id"] != old
    stored = es.get_client().get(index=es.CREWS, id=old)["_source"]
    assert ana_me["id"] not in stored["members"]
    assert ana.post("/api/crew/replace").status_code == 200  # safe to ask again
    assert TestClient(app).post("/api/crew/replace").status_code == 401


def test_only_members_set_the_meeting_and_it_keeps_its_time_zone(person):
    (ana, _), (ben, _) = _pair(person, "fennelquark")
    ana.post("/api/crew/suggest")
    ana.post("/api/crew/accept", json={})
    meeting = {
        "place": "North entrance, by the ramp",
        "starts_at": "2026-11-10T08:30:00-07:00",
        "timezone": "America/Denver",
    }
    assert ben.put("/api/crew/meeting", json=meeting).status_code == 403  # only suggested
    out = ana.put("/api/crew/meeting", json=meeting).json()
    assert out["crew"]["meeting"]["starts_at"] == "2026-11-10T08:30-07:00"
    assert out["crew"]["meeting"]["timezone"] == "America/Denver"
    bad = ana.put("/api/crew/meeting", json=meeting | {"starts_at": "2026-11-10T08:30:00"})
    assert bad.status_code == 422  # a time without an offset is ambiguous
    assert ana.put("/api/crew/meeting", json=meeting | {"timezone": "Mars/Base"}).status_code == 422
    # 08:30 UTC is not 08:30 in Denver: an offset that disagrees with the zone is refused.
    wrong_offset = meeting | {"starts_at": "2026-11-10T08:30:00+00:00"}
    assert ana.put("/api/crew/meeting", json=wrong_offset).status_code == 422


def test_crew_limit_is_the_smallest_comfort_limit():
    assert crews.crew_limit([{"comfort": "open"}, {"comfort": "small_groups"}]) == 4
    assert crews.crew_limit([{"comfort": "open"}, {"comfort": "one_on_one"}]) == 2
    assert crews.crew_limit([]) == 5


def test_why_uses_only_tags_members_share():
    assert crews.why([{"tags": ["go", "k8s"]}, {"tags": ["k8s"]}]) == "You share k8s"
    assert crews.why([{"tags": ["go"]}, {"tags": ["rust"]}]) == "Suggested from your best matches"
