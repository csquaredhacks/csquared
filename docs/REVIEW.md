# Plan review (v3): what changed and why

Written at midday on build day, with about five hours left. The v2 plan was sound in shape
but had problems that experienced judges would spot. Each one below is fixed in the code on
this branch, not just noted.

## Defects found in the v2 plan

| # | Problem in v2 | Why it matters | What v3 does |
|---|---|---|---|
| 1 | The session cookie was the attendee id, and the id is printed in every QR code. | Anyone who scanned you could set that cookie and act as you. A security engineer finds this in one minute. | Cookie is `<id>.<secret>`. The secret is never in a response or QR. Covered by a test. |
| 2 | The matcher only ran every two minutes. | The live demo is three minutes long. A new person would show no suggested links on the big screen. | The matcher also runs as a background task the moment someone registers. The CronJob stays as the reconcile pass. |
| 3 | "Why you matched" was going to be written by an LLM. | An LLM can invent a reason. Judges ask "how do you know that is why?" | Every Elasticsearch sub-query is named. `matched_queries` on each hit says which ones fired. The reason is built from that, so it is always true. The LLM only writes the optional icebreaker. |
| 4 | Semantic search was the only path. | If ELSER is misconfigured at 4 PM, nothing matches and the demo is dead. | Every signal runs as BM25 and, when `ELSER_ID` is set, also as semantic. Unset `ELSER_ID` and it still works. This is also a better hybrid-search story. |
| 5 | An OTel Collector was part of the chart. | One more thing to deploy, configure and debug, with no judging value. | The app exports OTLP straight to Dash0. Install the Dash0 Kubernetes operator from their onboarding page for cluster logs and metrics. |
| 6 | The tunnel URL changes whenever the tunnel pod restarts. | Printed QR codes die. | The tunnel is its own Deployment that app upgrades never roll. Every on-screen QR is built from the current origin. Print QR codes last. |
| 7 | The chaos endpoint was open on a public URL. | Anyone in the room could break the demo. | Needs `CHAOS_ENABLED=true` and an `X-Admin-Token` header. |
| 8 | Attendee documents had an email field. | The rules say keep private data out. No feature used it. | Removed. |
| 9 | Check-ins were an append-only log read back and deduplicated. | Extra code and a query that grows all day. | One check-in document per attendee, keyed by attendee id. Moving rooms overwrites it. |
| 10 | Matches were fetched by attendee id in the URL. | Anyone could read anyone's matches. | `GET /api/matches` uses the session. |

## Scope that was cut

PWA manifest, sessions index, NFC, points economy, LinkedIn import, resume upload, wayfinding
arrows. None of them move a judging criterion. Recap stayed because it cost forty lines.

## What to say to senior judges

- **Lead with simplicity.** One image, one Helm release, one Secret, one URL. No database
  besides Elasticsearch. Say what you chose not to build.
- **Be honest about the planned incidents.** Say "we planted this fault to show the workflow"
  and separately show the real problems you hit, logged in `docs/investigations/`. Real ones
  score higher than staged ones. Write them down the moment they happen.
- **Know the one query.** Everyone on the team should be able to explain
  `api/hallway/matching.py` line by line: retrievers, RRF, why BM25 and semantic together,
  how `matched_queries` gives the reason.
- **Name the limits before they ask.** Recovery codes are not rate limited. Chaos state is
  in memory, so one replica. The graph endpoint loads every edge, fine for a conference,
  not for a stadium. Quick tunnels have no uptime guarantee.
