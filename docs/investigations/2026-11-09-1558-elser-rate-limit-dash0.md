# The matcher failed on every run because the ELSER trial quota ran out

- **When:** first failure 15:58 Mountain Time (22:58 UTC), found at 16:08, 9 November 2026
- **Planted or real:** real. Nobody set this up. We found it while checking the new
  dashboard's queries against the cluster's own data.
- **Where:** cluster namespace `hallway`, CronJob `hallway-matcher` (service
  `hallway-matcher` in Dash0) and Deployment `hallway` (service `hallway-api`)
- **Tool used:** Dash0. Span metrics through its PromQL query API, then the failing spans
  themselves through its span query API, both driven from Claude Code. Agent0 was not used
  for this one.
- **Symptom:** Dash0 counted hundreds of spans with status ERROR an hour for a service
  whose API had returned no 5xx at all. That did not add up, so we broke the errors down.

## What Dash0 showed

Error spans in the last hour, grouped by service, span name and HTTP status:

| Service | Span | Status | Count | What it is |
| --- | --- | --- | --- | --- |
| `hallway-api` | `HEAD` | 404 | 489 | Not a failure. See "Noise" below. |
| `hallway-matcher` | `HEAD` | 404 | 211 | Same. |
| `hallway-matcher` | `POST` | **429** | 12 | Elasticsearch refusing the match query. |
| `hallway-matcher` | `search` | error | 3 | The search that those POSTs belong to. |
| `hallway-matcher` | `matcher.run` | error | 3 | The whole matcher pass, failed. |

`matcher.run` had finished cleanly five times every ten minutes since 13:05. From 15:58 it
failed every time. The span's own error message, copied from Dash0:

> ApiError(429, 'status_exception', 'Received a rate limit status code for request from
> inference entity id [.elser-2-elastic] status [429]. Error message: [You have reached your
> trial limit for this model. Upgrade to continue building and enable full production
> capacity or wait 16s for your trial quota to be refilled.]')

Inside one failed run (span start 23:02:25 UTC), the trace shows one `search` span lasting
13.9 seconds with four `POST .../hallway-attendees/_search` children of about 3.4 seconds
each, all answered 429. That is the Elasticsearch client retrying three times before giving
up. The `matcher.run` span then ends after 15 seconds with the exception, so nobody after
the first refused person gets suggestions in that pass.

`hallway-api` had 15 spans answered 429 in the same ten minutes, and no 5xx responses. So
the API was hitting the same limit in its background work, and no person's request had
failed yet.

## Root cause

The hybrid match query has a semantic half, and each semantic clause is one call to the
ELSER inference endpoint. The scheduled matcher pass asks that query for every attendee
every two minutes: 134 people, up to three semantic clauses each, so about 400 inference
calls per pass. On the Elastic trial that uses up the model's quota. Once it is gone,
Elasticsearch answers 429.

Two things in our code made that worse:

1. The matcher loop had no error handling per person, so one refusal ended the whole pass.
2. A refused query was retried three times, about 14 seconds in total, before failing.
   The same code path serves "Your five", so on stage a person would have waited 14 seconds
   and then seen an error.

Our own plan review said semantic search must never be the only path. It was not the only
path at query-building time, but nothing fell back when the semantic half failed at run time.

## Fix

In `api/hallway/matching.py` and `api/hallway/matcher.py`:

- If Elasticsearch refuses the hybrid query, the same question is asked again with keywords
  only, straight away and without retries. The semantic half is then left out for 60
  seconds, so the next people do not each pay for a failed call.
- The scheduled matcher pass uses keywords only. It no longer spends the quota that a
  person's own "Your five" needs. Hybrid matching still runs when someone registers, edits
  their profile, or opens their five.
- One person failing no longer stops the pass. The span records how many were skipped as
  `matcher.failed`.

Two tests cover it: a refused hybrid query still returns matches and is not tried again
inside the pause, and the scheduled pass never sends a semantic query.

## Noise we found on the way

The 700 `HEAD` spans with status 404 are `client.exists(...)` calls. "This edge does not
exist yet" is a normal answer, but the HTTP instrumentation marks any 404 as an error. They
are not failures. Our dashboard's error panel and the SLO count server responses only, so
they are not affected, but an error count that includes client spans is misleading for
this service.

## Check it yourself

In Dash0, filter spans to `service.name = hallway-matcher` and status ERROR, from 15:55
Mountain Time. After the fix is deployed, `matcher.run` should be clean again and
`http.response.status_code = 429` should only appear on `hallway-api`, at most once a minute.
