"""Seed Hallway with synthetic attendees, connections and check-ins.

    python seed/seed.py --api http://localhost:8000 [--connections 45] [--checkins] [--delay 0.2]

Every attendee gets its own httpx.Client. The server answers POST /api/attendees with a
session cookie; keeping the client keeps the cookie, so later calls are made *as that person*.
With --delay it doubles as a gentle load generator. Only dependency: `pip install httpx`.
"""

import argparse
import json
import random
import sys
import time
from pathlib import Path

import httpx

DATA = Path(__file__).with_name("attendees.json")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Seed Hallway with synthetic attendees.")
    p.add_argument("--api", default="http://localhost:8000", help="base URL of the app")
    p.add_argument("--connections", type=int, default=45, help="how many 'connected' edges")
    p.add_argument("--checkins", action="store_true", help="check everyone into a random room")
    p.add_argument("--seed", type=int, default=7, help="random seed: same seed, same graph")
    p.add_argument("--delay", type=float, default=0, help="seconds to wait between requests")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed)
    started = time.monotonic()

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
        return r.json()

    # 1. Register everyone. `people` keeps each attendee's id, groups and logged-in client.
    people = []
    for attendee in json.loads(DATA.read_text())["attendees"]:
        client = httpx.Client(base_url=args.api.rstrip("/"), timeout=30)
        me = call(client, "POST", "/api/attendees", attendee)
        people.append({"id": me["id"], "groups": set(attendee["groups"]), "client": client})

    # 2. Random connections, 70% of them between people who share a group,
    #    so the graph shows clusters with a few bridges between them.
    pairs: set[frozenset[str]] = set()
    wanted = min(args.connections, len(people) * (len(people) - 1) // 2)
    while len(pairs) < wanted:
        source = rng.choice(people)
        others = [p for p in people if p is not source]
        same_group = [p for p in others if p["groups"] & source["groups"]]
        target = rng.choice(same_group if same_group and rng.random() < 0.7 else others)
        pair = frozenset((source["id"], target["id"]))
        if pair in pairs:
            continue  # already connected, pick again
        pairs.add(pair)
        call(source["client"], "POST", "/api/edges", {"to_id": target["id"]})

    # 3. Optional check-ins into the rooms the server is configured with.
    checkins = 0
    if args.checkins:
        rooms = call(people[0]["client"], "GET", "/api/config")["rooms"]
        for person in people if rooms else []:
            call(person["client"], "POST", "/api/checkins", {"room": rng.choice(rooms)})
            checkins += 1

    for person in people:
        person["client"].close()
    print(
        f"Seeded {len(people)} attendees, {len(pairs)} connections, {checkins} check-ins "
        f"into {args.api} in {time.monotonic() - started:.1f}s"
    )


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPError as exc:
        sys.exit(f"Could not reach the API: {exc!r}")
