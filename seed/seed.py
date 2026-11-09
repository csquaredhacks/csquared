"""Seed Hallway with synthetic attendees, in two acts.

    python seed/seed.py --api http://localhost:8000 --phase before   # the week before
    python seed/seed.py --api http://localhost:8000 --phase live     # the day itself
    python seed/seed.py --api http://localhost:8000                  # both, in one go

"before" registers everyone and sends invitations to meet, some of which are accepted.
"live" turns most of those plans into real meetings, adds chance meetings and check-ins.

Every attendee gets its own httpx.Client. The server answers POST /api/attendees with a
session cookie; keeping the client keeps the cookie, so later calls are made *as that person*.
Between the two acts the recovery codes are kept in seed/.sessions.json (git-ignored), and
"live" uses them to log each person back in. Only dependency: `pip install httpx`.
"""

import argparse
import json
import random
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

DATA = Path(__file__).with_name("attendees.json")
SESSIONS = Path(__file__).with_name(".sessions.json")
# Where seeded crews agree to meet. Salt Lake City, the hackathon's home.
MEET_ZONE = "America/Denver"
MEETING_POINTS = [
    "North entrance, by the ramp",
    "Registration desk, left side",
    "Coffee bar, the quiet end",
    "Main Stage doors",
    "Outside Room A, by the benches",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Seed Hallway with synthetic attendees.")
    p.add_argument("--api", default="http://localhost:8000", help="base URL of the app")
    p.add_argument("--phase", choices=["before", "live", "all"], default="all")
    p.add_argument("--invitations", type=int, default=40, help="how many invitations to meet")
    p.add_argument("--connections", type=int, default=45, help="how many meetings in total")
    p.add_argument(
        "--crew-share", type=float, default=0.8, help="share of attendees who look for a crew"
    )
    p.add_argument("--checkins", action="store_true", help="check everyone into a random room")
    p.add_argument("--seed", type=int, default=7, help="random seed: same seed, same graph")
    p.add_argument("--delay", type=float, default=0, help="seconds to wait between requests")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed)
    started = time.monotonic()
    base = args.api.rstrip("/")

    def call(client: httpx.Client, method: str, path: str, body: dict | None = None):
        """One request. Stop with a readable message on any error status."""
        r = client.request(method, path, json=body)
        if r.status_code == 401:
            sys.exit(
                f"{method} {path} -> 401: the session cookie was not sent back. "
                "Over plain http the server must run with COOKIE_SECURE=false."
            )
        if r.is_error:
            sys.exit(f"{method} {path} -> {r.status_code}: {r.text[:300]}")
        time.sleep(args.delay)
        return r.json() if r.content else None

    def pick_pair(people: list[dict]) -> tuple[dict, dict]:
        """70% of pairs share a community, so the graph shows clusters with bridges."""
        source = rng.choice(people)
        others = [p for p in people if p is not source]
        same = [p for p in others if p["groups"] & source["groups"]]
        return source, rng.choice(same if same and rng.random() < 0.7 else others)

    # `people` keeps each attendee's id, communities and logged-in client.
    people: list[dict] = []
    if args.phase in ("before", "all"):
        for attendee in json.loads(DATA.read_text())["attendees"]:
            client = httpx.Client(base_url=base, timeout=30)
            # These people are fictional, so they all opt in to the public graph.
            me = call(
                client, "POST", "/api/attendees", attendee | {"on_graph": True, "show_groups": True}
            )
            people.append(
                {
                    "id": me["id"],
                    "name": attendee["name"],
                    "groups": set(attendee["groups"]),
                    "code": me["recovery_code"],
                    "client": client,
                }
            )
        saved = [{"id": p["id"], "groups": sorted(p["groups"]), "code": p["code"]} for p in people]
        SESSIONS.write_text(json.dumps(saved))
    else:
        if not SESSIONS.exists():
            sys.exit('Run with "--phase before" first: there is nobody to log back in.')
        for saved in json.loads(SESSIONS.read_text()):
            client = httpx.Client(base_url=base, timeout=30)
            call(client, "POST", "/api/recover", {"code": saved["code"]})
            people.append({"id": saved["id"], "groups": set(saved["groups"]), "client": client})
    by_id = {p["id"]: p for p in people}

    # Act one: invitations to meet. About two in three are accepted and become plans.
    invited: set[frozenset[str]] = set()
    plans = 0
    if args.phase in ("before", "all"):
        wanted = min(args.invitations, len(people) * (len(people) - 1) // 2)
        # The planted two-way pairs come first: each asker invites the person whose
        # offer answers their ask, and that invitation is accepted, so the demo's
        # reciprocal matches already have a plan before the random invitations start.
        by_name = {p["name"]: p for p in people}
        for planted in json.loads(DATA.read_text()).get("_planted_pairs", []):
            if len(invited) >= wanted:
                break
            asker = by_name.get(planted["asker"])
            offerer = by_name.get(planted["offerer"])
            if asker is None or offerer is None or asker is offerer:
                continue
            pair = frozenset((asker["id"], offerer["id"]))
            if pair in invited:
                continue
            invited.add(pair)
            call(asker["client"], "POST", "/api/invitations", {"to_id": offerer["id"]})
            call(offerer["client"], "POST", f"/api/invitations/{asker['id']}/accept")
            plans += 1
        while len(invited) < wanted:
            source, target = pick_pair(people)
            pair = frozenset((source["id"], target["id"]))
            if pair in invited:
                continue
            invited.add(pair)
            call(source["client"], "POST", "/api/invitations", {"to_id": target["id"]})
            if rng.random() < 0.65:
                call(target["client"], "POST", f"/api/invitations/{source['id']}/accept")
                plans += 1

    # Still act one: arrival groups. Most people ask for a crew and say yes; a few say
    # no thanks, so the organizer board shows people still without a group. Each crew
    # that forms agrees on a place and time, as its members would in the app.
    crew_ids: set[str] = set()
    joined = declined = 0
    if args.phase in ("before", "all"):
        when = (datetime.now(ZoneInfo(MEET_ZONE)) + timedelta(days=1)).replace(
            hour=8, minute=30, second=0, microsecond=0
        )
        for person in rng.sample(people, k=round(len(people) * args.crew_share)):
            out = call(person["client"], "POST", "/api/crew/suggest")
            if out["status"] == "member" or out["crew"] is None:
                continue
            if rng.random() < 0.12:
                call(person["client"], "POST", "/api/crew/decline")
                declined += 1
                continue
            r = person["client"].post("/api/crew/accept", json={"companion": rng.random() < 0.1})
            if r.status_code == 409:  # filled up a moment ago; that is part of the story
                continue
            if r.is_error:
                sys.exit(f"POST /api/crew/accept -> {r.status_code}: {r.text[:300]}")
            joined += 1
            crew = r.json()["crew"]
            if crew["id"] not in crew_ids and crew["meeting"] is None:
                crew_ids.add(crew["id"])
                call(
                    person["client"],
                    "PUT",
                    "/api/crew/meeting",
                    {
                        "place": rng.choice(MEETING_POINTS),
                        "starts_at": when.isoformat(),
                        "timezone": MEET_ZONE,
                    },
                )

    # Act two: most plans happen, and some people simply meet by chance.
    met: set[frozenset[str]] = set()
    checkins = 0
    if args.phase in ("live", "all"):
        graph = call(people[0]["client"], "GET", "/api/graph")
        for link in graph["links"]:
            # Real people may have made plans too. The seed only acts for its own people.
            ours = link["source"] in by_id and link["target"] in by_id
            if ours and link["kind"] == "planned" and rng.random() < 0.75:
                met.add(frozenset((link["source"], link["target"])))
                call(
                    by_id[link["source"]]["client"], "POST", "/api/edges", {"to_id": link["target"]}
                )
        wanted = min(args.connections, len(people) * (len(people) - 1) // 2)
        while len(met) < wanted:
            source, target = pick_pair(people)
            pair = frozenset((source["id"], target["id"]))
            if pair in met:
                continue
            met.add(pair)
            call(source["client"], "POST", "/api/edges", {"to_id": target["id"]})
        if args.checkins:
            rooms = call(people[0]["client"], "GET", "/api/config")["rooms"]
            for person in people if rooms else []:
                call(person["client"], "POST", "/api/checkins", {"room": rng.choice(rooms)})
                checkins += 1

    for person in people:
        person["client"].close()
    print(
        f"{args.phase}: {len(people)} attendees, {len(invited)} invitations, {plans} plans, "
        f"{joined} crew joins in {len(crew_ids)} crews ({declined} said no thanks), "
        f"{len(met)} meetings, {checkins} check-ins into {args.api} "
        f"in {time.monotonic() - started:.1f}s"
    )


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPError as exc:
        sys.exit(f"Could not reach the API: {exc!r}")
