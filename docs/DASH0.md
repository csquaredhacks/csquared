# Dash0: what we send, what we built, and how to check it

Hallway sends traces, metrics and logs straight to Dash0 over OTLP. There is no collector
to run. The dashboard, the two check rules and the SLO live in this repository as files
and are put into Dash0 with one command.

## What is instrumented

| Signal | Where it comes from |
| --- | --- |
| Traces | `opentelemetry-instrument` wraps the API and the matcher: every HTTP request, every Elasticsearch call, every OpenAI call. We add our own spans: `match.query`, `match.icebreaker`, `graph.bfs`, `graph.me`, `matcher.run`. Each request span carries `attendee.id`. |
| Logs | Python logging is exported over OTLP with the trace id attached, so a log line opens its trace. |
| Metrics | HTTP server metrics come for free. Ours are in the table below. |
| Browser | `web/src/rum.ts` starts the Dash0 web SDK when `DASH0_RUM_URL` and `DASH0_RUM_TOKEN` are set. |

Our own metrics, all defined in [`api/hallway/telemetry.py`](../api/hallway/telemetry.py):

| Metric | Type | Labels | Meaning |
| --- | --- | --- | --- |
| `hallway.funnel` | gauge | `stage`: `registered`, `in_group`, `planned`, `met`, `checked_in` | The product in five numbers. The same numbers as the organizer board at `/crowd`. |
| `hallway.room.occupancy` | gauge | `room`: one of `ROOMS` | People checked in to each room. The same numbers as the room map at `/rooms`. |
| `hallway.edges.total` | counter | `kind`: `suggested`, `invited`, `planned`, `connected` | Relationships written. |
| `hallway.crew.joins` | counter | none | People who accepted an arrival group. |
| `hallway.matcher.pairs` | counter | none | New suggested pairs written by the matcher. |

Labels only ever take values from a small fixed set. No attendee id, name, community or
free text is a label.

The two gauges recompute themselves from Elasticsearch just before they are exported, at
most every 30 seconds. So Dash0 has numbers even when nobody has `/rooms` or `/crowd`
open, and right after a pod restarts.

## The dashboard, check rules and SLO

They are in [`deploy/dash0/`](../deploy/dash0/):

| File | What it is |
| --- | --- |
| `dashboard.json` | Dashboard "Hallway". Top: the funnel as five numbers and over time. Middle: rooms, new relationships, arrival groups, matcher. Bottom: p95 of `GET /api/matches` against the 800 ms target, server errors, requests and latency by endpoint. |
| `check-matches-slow.json` | Check rule: p95 of `GET /api/matches` over 5 minutes. Degraded above 800 ms, failed above 1500 ms. |
| `check-server-errors.json` | Check rule: share of 5xx responses. Degraded above 1%, failed above 5%. |
| `slo-availability.json` | SLO: 99% of API requests finish without a server error, over 28 days. |
| `apply.sh` | Sends the four files to the Dash0 API. Each has a fixed id, so running it again updates instead of copying. |

Put them into Dash0:

```bash
make dash0
```

It needs two lines in `.env`: `DASH0_API_URL` (Dash0, Settings, Endpoints, API) and
`DASH0_AUTH_TOKEN`. If your ingest token cannot write dashboards, add a second token as
`DASH0_API_TOKEN`.

Every query filters on `deployment_environment_name="hackathon"`. That is `otel.environment`
in [`deploy/chart/hallway/values.yaml`](../deploy/chart/hallway/values.yaml). If you change
one, change the other.

Two things we learned from the real data, and wrote the queries around:

- Latency panels use Dash0's span metric `dash0.spans.duration` (seconds), not
  `http.server.request.duration`. The Python instrumentation we run reports that one in
  milliseconds under the new name, which is easy to misread.
- Endpoints are grouped by `dash0_operation_name` (for example `GET /api/matches`). The raw
  `http_target` label contains attendee ids, so we never group by it.

## Check it yourself

1. Open Dash0, Dashboards, "Hallway". The top row should match `<url>/crowd`.
2. Check in to a room on a phone. "People in each room" moves within a minute.
3. Make matching slow (command in [`DEMO.md`](DEMO.md)), open "Your five" a few times, and
   wait two minutes. The p95 panel crosses the 800 ms line and the check rule
   "Hallway: matches are slow" turns degraded. Ask Agent0 why matches are slow. The answer
   is in the `match.query` span. Save what it said in `docs/investigations/`.
4. Turn chaos off again.

## Not done by this repository

- **Browser monitoring** needs `DASH0_RUM_URL` and `DASH0_RUM_TOKEN` in the Secret. Use an
  ingest-only token for it: it is sent to every browser.
- **Pod logs and cluster metrics** come from the Dash0 Kubernetes operator, installed from
  Dash0's onboarding page.
- **Notifications** for the check rules: add a notification channel in Dash0 if you want
  to be paged. Without one the rules still show their state in Dash0.
