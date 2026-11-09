"""The two product gauges refresh themselves, so Dash0 has numbers even when nobody
has the room map or the organizer board open."""

from hallway import telemetry
from hallway.main import app  # noqa: F401 - importing the app registers the refreshers


def _fresh(monkeypatch):
    monkeypatch.setattr(telemetry, "_refreshed_at", {})
    monkeypatch.setattr(telemetry, "_funnel", {})
    monkeypatch.setattr(telemetry, "_room_occupancy", {})


def test_funnel_gauge_fills_itself_from_elasticsearch(person, monkeypatch):
    person("Ana gauge")
    _fresh(monkeypatch)
    stages = {o.attributes["stage"]: o.value for o in telemetry._observe_funnel(None)}
    assert set(stages) == {"registered", "in_group", "planned", "met", "checked_in"}
    assert stages["registered"] >= 1


def test_room_gauge_reports_every_room_without_a_page_view(indices, monkeypatch):
    _fresh(monkeypatch)
    rooms = {o.attributes["room"] for o in telemetry._observe_rooms(None)}
    assert "Quiet Room" in rooms


def test_refresh_runs_at_most_once_per_interval(monkeypatch):
    calls = []
    monkeypatch.setattr(telemetry, "_refreshed_at", {})
    monkeypatch.setattr(telemetry, "refreshers", {"funnel": lambda: calls.append(1)})
    telemetry._observe_funnel(None)
    telemetry._observe_funnel(None)
    assert calls == [1]


def test_a_failing_refresh_keeps_the_last_values(monkeypatch):
    def broken():
        raise RuntimeError("elasticsearch is down")

    monkeypatch.setattr(telemetry, "_refreshed_at", {})
    monkeypatch.setattr(telemetry, "refreshers", {"funnel": broken})
    monkeypatch.setattr(telemetry, "_funnel", {"registered": 7})
    assert [o.value for o in telemetry._observe_funnel(None)] == [7]
