# Hallway

**Nobody at a conference goes solo.**

Hallway's goal is to help you find your group before a conference, arrive with
familiar people, and keep growing those connections during and after the event.
Your asks, offers, and chosen communities help you find people to meet. The graph
helps you discover introductions and expand your group as the event continues.

Read the [product brief](docs/PRODUCT_BRIEF.md) for the intended experience, build
priorities, and open decisions. It separates the product direction from what is
currently implemented.

Built in one day at the Cloud Native Hackathon, Salt Lake City, 9 November 2026.

## How it works

```
 phone / laptop / venue screen
            |  https (cloudflared quick tunnel)
            v
 +---------------------------+        +--------------------------+
 |  hallway  (one image)     |  -->   |  Elasticsearch           |
 |  FastAPI: /api/*          |        |  attendees, edges,       |
 |  React app: everything    |        |  checkins. The only      |
 |  else                     |        |  datastore.              |
 +---------------------------+        +--------------------------+
            |  OTLP (traces, metrics, logs)        ^
            v                                      |
          Dash0                     hallway-matcher (CronJob, same image)
```

Everything runs on a Kubernetes cluster that Radar is connected to. It is one Helm release.

| Sponsor tool | What it does in Hallway |
| --- | --- |
| **Elasticsearch** | The only datastore, and the matchmaker. One hybrid query with reciprocal rank fusion crosses *my asks* with *their offers*, *my offers* with *their asks*, similar work, shared tags and shared groups. Each signal runs as keyword search and, when an inference endpoint is configured, as semantic search too. Named queries tell us which signal matched, so the reason shown to the user is true and not made up by a language model. See [`api/hallway/matching.py`](api/hallway/matching.py). |
| **Dash0** | The API runs under OpenTelemetry auto-instrumentation and adds its own spans (`match.query`, `match.icebreaker`, `graph.bfs`, `matcher.run`) and metrics (connections made, room occupancy). The browser sends real user monitoring data. The room map in the product is drawn from the same numbers the dashboard shows. |
| **Radar** | The cluster view during the whole build, and the investigation tool when a pod is killed for using too much memory. See [`docs/investigations/`](docs/investigations/). |
| **Gitar** | Reviews every pull request against our own rules in [`docs/GITAR_RULES.md`](docs/GITAR_RULES.md), and diagnoses CI failures. |

## Run it

### Option 1: on your laptop

You need Python 3.12+, Node 20+, and an Elasticsearch 9 URL (Elastic Cloud serverless works; so does a local one).

```bash
cp .env.example .env
```

Fill in `ES_URL` and `ES_API_KEY`. Everything else is optional. Then:

```bash
python -m venv .venv && . .venv/bin/activate && pip install -e "./api[dev]"
```

```bash
(cd web && npm ci)
```

```bash
make dev
```

Open http://localhost:5173. To fill it with 60 made-up attendees:

```bash
make seed
```

### Option 2: on a Kubernetes cluster

You need `kubectl` pointed at the cluster, `helm`, and Docker.

```bash
make image
```

```bash
make secrets
```

```bash
make deploy
```

```bash
make url
```

`make url` prints a public https address. Share it or turn it into a QR code. No ingress, DNS or account is needed.
If you cannot log in to the GitHub container registry, `make image-ttl` pushes to a free anonymous registry instead and prints the deploy command.

### Option 3: just the tests

```bash
make test
```

```bash
make lint
```

The API tests run against a real Elasticsearch at `ES_URL` and skip themselves if it is not reachable.

## Where things are

| Path | What is in it |
| --- | --- |
| `api/hallway/` | The API. Start with `matching.py`, then `routes/`. |
| `api/tests/` | Tests for matching, graph paths, and every endpoint. |
| `web/src/` | The React app. One file per page in `pages/`. |
| `deploy/chart/hallway/` | The Helm chart: API, matcher CronJob, tunnel. |
| `seed/` | 60 fictional attendees and a script that loads them through the API. |
| `docs/API.md` | The contract between the API and the web app. |
| `docs/RUNBOOK.md` | Who does what today, in order, with a troubleshooting table. |
| `docs/REVIEW.md` | What was wrong with our first plan and how we fixed it. |
| `docs/DEMO.md` | The three-minute demo script and the planned incidents. |
| `docs/GITAR_RULES.md` | The review rules we gave Gitar. |
| `docs/investigations/` | Write-ups of real incidents found with Radar, Dash0 and Gitar. |

## Privacy

- There are no accounts, emails or passwords. A profile is a name and what you choose to write.
- Your session is a random secret in an HttpOnly cookie. Your public id is safe to put in a QR code.
- You can leave the public graph at any time. People who are off the graph are never shown on it.
- All data in this repository and in the demo is fictional.

## AI assistance disclosure

We used AI tools to build this, as the hackathon rules allow.

- **Claude Code** helped review our plan and wrote a large part of the first version of the API, the web app, the Helm chart, the tests and these docs.
- **Gitar** reviews our pull requests and suggests fixes for CI failures.
- **Dash0 Agent0** and **Radar's AI investigation** were used on the incidents in `docs/investigations/`.
- The app itself calls a language model for one thing only: an optional one-line icebreaker. Matching and the reasons shown never depend on it.

Every team member has read the code they present and can explain it. `docs/REVIEW.md` records the design decisions and why we made them.
