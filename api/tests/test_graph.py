from hallway.edges import edge_id
from hallway.models import GraphLink
from hallway.routes.graph import shortest_path


def link(a: str, b: str, kind: str = "connected") -> GraphLink:
    return GraphLink(source=a, target=b, kind=kind, reason="")


def test_edge_id_is_the_same_from_both_sides():
    assert edge_id("b", "a", "connected") == edge_id("a", "b", "connected") == "a:b:connected"


def test_shortest_path_follows_connected_links_in_either_direction():
    links = [link("a", "b"), link("c", "b"), link("c", "d"), link("a", "x"), link("x", "y")]
    assert shortest_path(links, "a", "d") == ["a", "b", "c", "d"]


def test_suggested_links_are_not_introductions():
    assert shortest_path([link("a", "b", "suggested")], "a", "b") == []


def test_no_path_and_path_to_self():
    assert shortest_path([link("a", "b")], "a", "z") == []
    assert shortest_path([], "a", "a") == ["a"]
