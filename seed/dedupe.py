"""Safe, idempotent deduplication utility for Hallway Elasticsearch indices.

Finds duplicate attendee profiles created by concurrent seed runs, keeps the earliest
original document for each name, and cleans up the orphan duplicates.

Usage:
    python seed/dedupe.py            # Dry run: reports duplicates without modifying data
    python seed/dedupe.py --apply    # Applies the deduplication
"""

import argparse
import os
import sys
from collections import defaultdict

from elasticsearch import Elasticsearch

ES_URL = os.getenv("ES_URL", "http://localhost:9200")
ES_API_KEY = os.getenv("ES_API_KEY", "")
INDEX_PREFIX = os.getenv("INDEX_PREFIX", "hallway")

ATTENDEES_INDEX = f"{INDEX_PREFIX}-attendees"
EDGES_INDEX = f"{INDEX_PREFIX}-edges"
CREWS_INDEX = f"{INDEX_PREFIX}-crews"


def get_client() -> Elasticsearch:
    return Elasticsearch(
        ES_URL,
        api_key=ES_API_KEY or None,
        request_timeout=30,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Find and deduplicate attendee profiles.")
    parser.add_argument(
        "--apply", action="store_true", help="actually delete duplicates (default is dry-run)"
    )
    args = parser.parse_args()

    client = get_client()
    if not client.ping():
        sys.exit(f"Cannot connect to Elasticsearch at {ES_URL}")

    print(f"Connected to Elasticsearch ({ES_URL})")
    print(f"Scanning {ATTENDEES_INDEX} for duplicate attendee names...")

    resp = client.search(
        index=ATTENDEES_INDEX,
        size=1000,
        query={"match_all": {}},
    )

    hits = resp["hits"]["hits"]
    by_name = defaultdict(list)
    for h in hits:
        name = h["_source"].get("name")
        if name:
            by_name[name].append((h["_id"], h["_source"].get("created_at", "")))

    duplicates = {name: items for name, items in by_name.items() if len(items) > 1}

    if not duplicates:
        print("No duplicate attendee names found. Index is clean!")
        return

    print(f"\nFound {len(duplicates)} names with multiple profiles:")
    to_delete_ids = []
    for name, items in sorted(duplicates.items()):
        # Sort by creation time so we keep the earliest original
        sorted_items = sorted(items, key=lambda x: x[1])
        original_id, orig_created = sorted_items[0]
        orphan_ids = [item[0] for item in sorted_items[1:]]
        to_delete_ids.extend(orphan_ids)
        print(
            f"  • '{name}': keeping {original_id} (created {orig_created}), "
            f"removing {len(orphan_ids)} duplicate(s): {orphan_ids}"
        )

    print(f"\nTotal duplicate documents identified: {len(to_delete_ids)}")

    if not args.apply:
        print("\n[DRY RUN] No changes made. Run with '--apply' to delete duplicates.")
        return

    print("\nApplying deduplication...")
    deleted_attendees = 0
    for doc_id in to_delete_ids:
        try:
            client.delete(index=ATTENDEES_INDEX, id=doc_id, refresh=True)
            deleted_attendees += 1
        except Exception as e:
            print(f"Warning: failed to delete attendee {doc_id}: {e}")

    # Clean up associated edges
    resp_edges = client.delete_by_query(
        index=EDGES_INDEX,
        query={
            "bool": {
                "should": [
                    {"terms": {"source": to_delete_ids}},
                    {"terms": {"target": to_delete_ids}},
                ]
            }
        },
        refresh=True,
    )
    deleted_edges = resp_edges.get("deleted", 0)

    print(
        f"Successfully deleted {deleted_attendees} duplicate attendees "
        f"and {deleted_edges} orphan edges."
    )


if __name__ == "__main__":
    main()
