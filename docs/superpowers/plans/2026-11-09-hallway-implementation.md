# Hallway Implementation Plan (v2: cluster on Radar, one image, zero-friction setup)

> **Current source of truth:** [the working plan](../../WORKING_PLAN.md).
> Use its build order and acceptance criteria for new work.

> **Superseded on the day (v3).** The code no longer follows this plan in several places: there is no OTel Collector, the session cookie carries a secret, matching is hybrid, and the email field is gone. Read [`docs/REVIEW.md`](../../REVIEW.md) for what changed and why, [`docs/RUNBOOK.md`](../../RUNBOOK.md) for today's tasks, and [`docs/API.md`](../../API.md) for the contract. This file is kept as a record of the original plan.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **For the humans:** this is a one-day hackathon plan. Tasks are grouped into four parallel **lanes** (Platform, API, Web, Story). Each lane is one person. Each task states exactly what it produces so the next lane can build against it. Tests are smoke checks; the demo is the test. Every task ends in a PR so Gitar reviews it. Phases carry durations, not clock times, so start Phase 0 whenever you read this.

**Goal:** Ship Hallway, a conference matchmaking + live connection graph + room occupancy app, running on the Radar-connected Kubernetes cluster with Elasticsearch as the only datastore, instrumented into Dash0, reviewed by Gitar on every PR, demoable by 5:30 PM.

**Architecture:** One container image (`hallway`) runs FastAPI, which serves `/api/*` and the Vite-built React app at `/`. The same image runs as a `matcher` CronJob. A `cloudflared` quick-tunnel Deployment gives the app a public HTTPS URL with no account or ingress. All three plus an OTel Collector are deployed with a single Helm release reading a single Kubernetes Secret.

**Tech Stack:** Python 3.12, FastAPI, `elasticsearch` 9.x, `opentelemetry-distro`, `opentelemetry-exporter-otlp`, `openai`; React 18 + Vite + TypeScript, `react-router-dom`, `react-force-graph-2d`, `qrcode.react`; Helm 3; GitHub Actions + GHCR; Gitar; Radar; Dash0; Elastic Cloud serverless.

**Spec:** `docs/superpowers/specs/2026-11-09-hallway-design.md`

## Global Constraints

- Every Elasticsearch search sets `size`; every `rrf` retriever sets `rank_window_size` (Gitar rule 1).
- Every API handler runs inside a span carrying `attendee.id` when known (Gitar rule 2).
- Any change to a response model in `api/hallway/models.py` regenerates `web/src/api/types.ts` in the same PR (Gitar rule 3).
- No secrets in the repo. Secrets live in `.env` (gitignored) locally and in the Kubernetes Secret `hallway-secrets` (Gitar rule 4).
- All timestamps UTC ISO-8601 (Gitar rule 5).
- Matches return at most 5. Edge ids are `min(id):max(id):kind`.
- Attendee identity is a cookie `hallway_id` plus a recovery code; **no accounts, no passwords, no OAuth**.
- One image, one Helm release, one Secret, one public URL. Nothing else to install for an attendee.
- Chaos endpoint only works when `CHAOS_ENABLED=true`.
- Nothing merges without a Gitar review having run on the PR.

## Review Focus

Inputs the spec implies that no smoke test exercises. Watch for these in Gitar reviews and the bug bash.

1. **Attendee with empty `asks` or `offers`**: the RRF query must omit that retriever rather than send an empty `semantic` query. Test in Task A3.
2. **Scanning your own QR, or the same pair twice**: no self-edge (400), no duplicate (idempotent id). Test in Task A4.
3. **Scanning a QR before registering**: `/connect/<id>` must remember the target, send the person through registration, and then connect, not drop the scan. Test in Task W3.
4. **Check-in to an unknown room**: 400 against the configured room list, so metric label cardinality stays bounded. Test in Task A6.
5. **Elasticsearch unreachable at startup**: retry index creation for 60 s; `/healthz` reports `es:"red"` instead of crash-looping. Test in Task A1.

---

## Setup, kept as simple as possible

### For attendees (the people at the conference)
1. Point your phone camera at the QR on the screen. It opens `https://<tunnel>.trycloudflare.com/`.
2. Fill one form: name, what you're working on, what you need, what you can offer. Everything else optional. Submit.
3. You're on **Your Five**. Your profile has a QR. Someone scans it with their camera app and you're connected. That's it.
4. Lost your session (new phone, cleared cookies)? Type the 6-character recovery code shown on your profile at `/recover`.

Nothing to install. No account. No email required. Works on any phone with a camera app and a browser.

### For the team (local dev)
```bash
git clone <repo> && cd hallway
cp .env.example .env        # fill ES_URL, ES_API_KEY, ELSER_ID, OPENAI_API_KEY, DASH0_AUTH_TOKEN
make dev                    # api on :8000 with hot reload, web on :5173 proxying /api → :8000
make seed                   # 60 synthetic attendees + edges + check-ins into your ES
```
Local dev talks to the same Elastic Cloud trial (no local Elasticsearch; ELSER needs the cloud).

### For deploying (and for judges reading the README)
```bash
make secrets NS=<namespace>   # creates Kubernetes Secret hallway-secrets from .env
make deploy  NS=<namespace>   # helm upgrade --install hallway deploy/chart/hallway
make url     NS=<namespace>   # prints the public https://*.trycloudflare.com URL from the tunnel pod log
make seed    API=<that url>
```
Three commands to a running, public, observable app. `make deploy` also installs the OTel Collector sub-release.

---

## Phases and lanes

| Phase (duration) | Platform | API | Web | Story |
|---|---|---|---|---|
| **0. Bootstrap (30 min)** | P1 repo, Gitar, CI, Makefile | A0 Elastic trial + ELSER check | W0 Vite scaffold + types pipeline | S0 accounts, `.env` handoff |
| **1. Hello on the cluster (45 min)** | P2 Helm chart + tunnel + Radar MCP | A1 skeleton, indices, healthz, static serving | W1 register, profile, QR, recover | S1 seed data |
| **2. Vertical slice (60 min)** | P3 OTel collector → Dash0 | A2 attendees, A3 matches | W2 Your Five | S2 prompts |
| **3. Connections (45 min)** | P4 Gitar rules live, real image deployed | A4 edges | W3 `/connect/<id>` flow | S3 Gitar rules doc, README skeleton |
| **4. Graph + agent (60 min)** | P5 Dash0 dashboard + SLO + MCP | A5 graph + path, A7 matcher CronJob | W4 graph page | S4 demo script, seed the cluster |
| **5. Rooms + chaos (45 min)** | P6 planned OOM investigation in Radar | A6 rooms + metric, A8 chaos, A9 recap | W5 rooms, W6 recap | S5 planned CI break → Gitar auto-apply |
| **6. Freeze (last 60 min)** | bug bash, Agent0 chaos rehearsal | | | S6 README final, screenshots, submit, rehearse twice |

**Cut line:** if Phase 4 isn't done with 90 minutes left, drop A9/W6 (recap), then A6/W5 (rooms). Never drop matches (A3/W2) or graph (A5/W4).

---

## File structure

```
hallway/
├── .github/workflows/ci.yml       # ruff, pytest, tsc, vite build, helm lint; push image on main
├── .gitar/rules/*.md              # Gitar repo rules
├── .env.example
├── Makefile                       # dev, types, seed, secrets, deploy, url
├── Dockerfile                     # multi-stage: node builds web/ → python image copies dist into api/hallway/static
├── api/
│   ├── pyproject.toml
│   ├── hallway/
│   │   ├── main.py                # app, lifespan, mounts /api routers and StaticFiles at /
│   │   ├── config.py              # Settings from env
│   │   ├── es.py                  # client, mappings, ensure_indices()
│   │   ├── models.py              # Pydantic models (source of truth for TS types)
│   │   ├── telemetry.py           # tracer, meter, instruments
│   │   ├── matching.py            # build_match_query(), explain_why()
│   │   ├── llm.py                 # icebreaker(), recap_nudges()
│   │   ├── prompts.py
│   │   ├── matcher.py             # CronJob entrypoint
│   │   ├── chaos.py               # mode + sleep()/maybe_fail()
│   │   ├── static/                # built web app (gitignored; produced by Dockerfile / make dev)
│   │   └── routes/{attendees,matches,edges,graph,rooms,recap,chaos}.py
│   └── tests/
├── web/
│   ├── index.html                 # Dash0 RUM snippet, PWA manifest link
│   ├── public/manifest.webmanifest
│   └── src/
│       ├── api/{client.ts, types.ts(generated)}
│       ├── pages/{Register,Profile,YourFive,Connect,Recover,Graph,Rooms,Recap}.tsx
│       └── components/{QrCard,MatchCard,RoomGrid}.tsx
├── deploy/
│   ├── chart/hallway/             # Chart.yaml, values.yaml, templates/
│   └── otel-collector-values.yaml
├── seed/{attendees.json, seed.py}
└── docs/{DEMO.md, GITAR_RULES.md, investigations/}
```

---

## Lane P — Platform (repo, CI, Kubernetes, Radar, Dash0 plumbing, Gitar)

### Task P1: Repo bootstrap, Gitar, CI, Makefile (Phase 0)

**Files:** `.github/workflows/ci.yml`, `Makefile`, `.gitignore`, `.env.example`, `Dockerfile` (stub), `README.md`

**Produces:**
- Gitar installed on the repo with auto-apply on.
- CI on every PR: jobs `api` (`uv sync && ruff check . && pytest -q`), `web` (`npm ci && npx tsc --noEmit && npm run build`), `helm` (`helm lint deploy/chart/hallway`), `image` (docker build; on `main` also push `ghcr.io/<org>/hallway:<sha>` and `:latest`). Jobs guard on `hashFiles` so they pass before the directories exist.
- `Makefile` targets exactly as in the Setup section above plus `types`:
  - `dev`: runs `uvicorn hallway.main:app --reload --port 8000` (loads `.env`) and `npm --prefix web run dev` concurrently.
  - `types`: `curl -s localhost:8000/openapi.json | npx openapi-typescript -o web/src/api/types.ts`.
  - `seed`: `python seed/seed.py --api $(API)`.
  - `secrets`: `kubectl -n $(NS) create secret generic hallway-secrets --from-env-file=.env --dry-run=client -o yaml | kubectl apply -f -`.
  - `deploy`: `helm upgrade --install hallway deploy/chart/hallway -n $(NS) --set image.tag=$(TAG)` then the collector sub-install (P3).
  - `url`: `kubectl -n $(NS) logs deploy/tunnel | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' | tail -1`.
- `.env.example` lists `ES_URL`, `ES_API_KEY`, `ELSER_ID`, `OPENAI_API_KEY`, `DASH0_AUTH_TOKEN`, `DASH0_OTLP_ENDPOINT`, `ROOMS`, `CHAOS_ENABLED`, `PUBLIC_URL`.

- [ ] **Step 1:** Push `main`. Install the Gitar GitHub App (app.gitar.ai → GitHub → this repo). Turn on auto-apply.
- [ ] **Step 2:** Write the files above. Open PR "ci: skeleton". Confirm Gitar comments. Screenshot → `docs/investigations/`. Merge.

Run: PR page. Expected: green CI, a Gitar review comment.

### Task P2: Helm chart, tunnel, Radar MCP (Phase 1)

**Files:** `deploy/chart/hallway/{Chart.yaml,values.yaml}`, `templates/{deployment,service,cronjob,tunnel,_helpers.tpl}.yaml`

**Produces:**
- `values.yaml`: `image.repository: ghcr.io/<org>/hallway`, `image.tag: latest`, `replicas: 1`, `resources.limits.memory: 256Mi`, `matcher.schedule: "*/2 * * * *"`, `secretName: hallway-secrets`, `env.ROOMS: "Main Stage,Room A,Room B,Coffee Bar,Quiet Room"`, `env.CHAOS_ENABLED: "true"`, `tunnel.enabled: true`.
- `deployment.yaml`: container `hallway`, port 8000, `envFrom.secretRef`, env `OTEL_SERVICE_NAME=hallway`, `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317`, `OTEL_RESOURCE_ATTRIBUTES=deployment.environment=hackathon`, readiness probe `GET /healthz`.
- `service.yaml`: ClusterIP `hallway:8000`.
- `cronjob.yaml`: same image, `command: ["opentelemetry-instrument","python","-m","hallway.matcher"]`, `OTEL_SERVICE_NAME=hallway-matcher`, `concurrencyPolicy: Forbid`.
- `tunnel.yaml`: Deployment `tunnel`, image `cloudflare/cloudflared:latest`, args `["tunnel","--no-autoupdate","--url","http://hallway:8000"]`.

- [ ] **Step 1:** Confirm cluster: `kubectl get ns` (use the namespace the Radar booth gave you; export `NS`). Start Radar: `kubectl radar` → `claude mcp add --transport http radar http://localhost:9280/mcp-readonly`. In Claude Code ask "list workloads in namespace $NS". Screenshot.
- [ ] **Step 2:** Write the chart. Temporarily set `image.repository: hashicorp/http-echo` with `args: ["-listen=:8000","-text=hello"]` for a smoke deploy.
- [ ] **Step 3:** `make secrets NS=$NS && make deploy NS=$NS && make url NS=$NS`. Open the URL on a phone: "hello".
- [ ] **Step 4:** Revert to the real image repo. PR "deploy: helm chart + tunnel". Merge.

Run: `helm lint deploy/chart/hallway; kubectl -n $NS get deploy,cronjob,svc`. Expected: lint OK; `hallway` and `tunnel` Available, `matcher` listed; Radar UI shows all three.

### Task P3: OTel Collector → Dash0 (Phase 2)

**Files:** `deploy/otel-collector-values.yaml`; `Makefile` (`deploy` runs the collector install too)

**Produces:** Service `otel-collector` on 4317/4318 in `$NS` exporting traces, metrics, logs to Dash0.

- [ ] **Step 1:** Dash0 → Settings → Endpoints → copy the OTLP gRPC endpoint into `.env` as `DASH0_OTLP_ENDPOINT`; Settings → Auth Tokens → create token (Ingesting) as `DASH0_AUTH_TOKEN`. Re-run `make secrets`.
- [ ] **Step 2:** Values: `mode: deployment`; `config.receivers.otlp` (grpc + http); `processors: [batch, resource]` with `service.namespace: hallway`; `exporters.otlp` with `endpoint: ${env:DASH0_OTLP_ENDPOINT}` and `headers.Authorization: "Bearer ${env:DASH0_AUTH_TOKEN}"`; `extraEnvs` from `hallway-secrets`; pipelines for traces, metrics, logs.
- [ ] **Step 3:** `helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts && helm upgrade --install otel-collector open-telemetry/opentelemetry-collector -n $NS -f deploy/otel-collector-values.yaml`. Add that line to `make deploy`.
- [ ] **Step 4:** Hit `/healthz` on the public URL ten times; confirm `hallway` spans appear in Dash0 Tracing. Screenshot.

Run: `kubectl -n $NS logs deploy/otel-collector | grep -ci 'error'`. Expected: 0.

### Task P4: Real image live, Gitar rules live (Phase 3)

**Files:** `.gitar/rules/{elasticsearch,telemetry,api-contract,secrets,time}.md` (text from `docs/GITAR_RULES.md`, Task S3)

- [ ] **Step 1:** After A1 and W1 merge, CI pushed `ghcr.io/<org>/hallway:<sha>`. `make deploy NS=$NS TAG=<sha>`. Open the public URL on a phone: registration form loads.
- [ ] **Step 2:** Commit the rules. If Gitar's dashboard names a different location for rules, follow the dashboard and keep these files as the readable copy.
- [ ] **Step 3:** Open a deliberately rule-breaking PR (an ES search without `size`); confirm Gitar cites the rule. Screenshot. Close without merging.

### Task P5: Dash0 dashboard, SLO, MCP in Claude Code (Phase 4)

- [ ] **Step 1:** Dashboard "Hallway Live": `hallway.room.occupancy` by `room` (bar), p95 `http.server.request.duration` for `/api/matches/{id}`, rate of `hallway.edges.total` by `kind`, 5xx rate, `matcher.run` span count.
- [ ] **Step 2:** SLO "matches-latency": p95 `/api/matches/{id}` < 800 ms and 99% success, 1 h window.
- [ ] **Step 3:** Dash0 → Settings → Endpoints → MCP; token with read on the dataset. `claude mcp add --transport http dash0 <url> --header "Authorization: Bearer $DASH0_MCP_TOKEN"`. Ask "slowest routes in the last 15 min". Screenshot.

### Task P6: Planned real issue for Radar (Phase 5)

- [ ] **Step 1:** `helm upgrade ... --set resources.limits.memory=48Mi`; watch `kubectl -n $NS get pod -w` for `OOMKilled`.
- [ ] **Step 2:** `radar diagnose deploy/hallway -n $NS` (or Investigate in the Radar UI). Save output to `docs/investigations/radar-oom.md`.
- [ ] **Step 3:** Apply the fix as a PR (`256Mi`) so Gitar reviews it. Merge, redeploy.

Run: `kubectl -n $NS get pod -l app=hallway`. Expected: Running, restarts stable.

---

## Lane A — API (FastAPI + Elasticsearch)

### Task A0: Elastic trial + ELSER check (Phase 0)

- [ ] **Step 1:** Create an Elastic Cloud serverless **Elasticsearch** project; create an API key; note the endpoint.
- [ ] **Step 2:** Dev Tools: `GET _inference` → note the ELSER endpoint id (serverless usually `.elser-2-elastic`). Create a throwaway index with one `semantic_text` field, index one doc, `match` it. If it fails, **decide now**: fall back to OpenAI `text-embedding-3-small` into `dense_vector` (`dims: 1536`, `similarity: cosine`) with `knn` retrievers in A3. Tell the team.
- [ ] **Step 3:** Put `ES_URL`, `ES_API_KEY`, `ELSER_ID` in the shared `.env`.

### Task A1: Skeleton, settings, indices, healthz, static serving (Phase 1)

**Files:** `api/pyproject.toml`, `Dockerfile`, `api/hallway/{main,config,es,telemetry}.py`, `api/tests/test_health.py`

**Produces:**
- `config.Settings`: `es_url`, `es_api_key`, `elser_id`, `rooms: list[str]` (from comma-separated `ROOMS`), `room_capacity: dict[str,int]` (`Main Stage: 150`, `Coffee Bar: 25`, others `40`), `chaos_enabled: bool = False`, `openai_api_key: str | None`, `public_url: str`.
- `es.get_client() -> Elasticsearch`; `es.ensure_indices(client) -> None` (idempotent; spec §5 mappings for `attendees`, `edges`, `checkins`); constants `IDX_ATTENDEES`, `IDX_EDGES`, `IDX_CHECKINS`.
- `telemetry.tracer`, `telemetry.meter`, `telemetry.edges_total` (Counter), `telemetry.matcher_pairs` (Counter), `telemetry.set_room_occupancy(values: dict[str,int])` backed by an ObservableGauge reading a module-level dict.
- `GET /healthz -> {"ok": bool, "es": "green"|"red"}`.
- `main.py` mounts `/api` routers and `StaticFiles(directory="hallway/static", html=True)` at `/` with an SPA fallback to `index.html` for unknown paths (so `/connect/abc` deep links work).
- `Dockerfile`: stage 1 `node:22` builds `web/` → `dist`; stage 2 `python:3.12-slim` installs `api/`, copies `dist` → `api/hallway/static`, `CMD ["opentelemetry-instrument","uvicorn","hallway.main:app","--host","0.0.0.0","--port","8000"]`.

- [ ] **Step 1:** Test `test_healthz_reports_red_when_es_down` (patch `get_client` to raise → 200, `es == "red"`), `test_spa_fallback_serves_index` (`GET /connect/xyz` → 200 HTML).
- [ ] **Step 2:** Implement. Lifespan retries `ensure_indices` for 60 s, logs, never exits.
- [ ] **Step 3:** `cd api && uv run pytest -q`; `docker build -t hallway .` succeeds. PR "api: skeleton + static serving". Merge.

### Task A2: Attendees + recovery code (Phase 2)

**Files:** `api/hallway/models.py`, `api/hallway/routes/attendees.py`, `api/tests/test_attendees.py`

**Produces:**
- `models.AttendeeIn`: `name: str`, `working_on: str`, `asks: str`, `offers: str`, `email: str | None = None`, `tags: list[str] = []`, `groups: list[str] = []`, `fun_fact: str | None = None`, `comfort: list[str] = []`.
- `models.Attendee(AttendeeIn)`: `id: str`, `created_at: datetime`. `models.AttendeeSummary`: `id`, `name`, `groups`.
- `models.Me(Attendee)`: adds `recovery_code: str` (only ever returned to the owner).
- `POST /api/attendees -> Me`: `id = uuid4().hex[:10]`, `recovery_code` = 6 chars from `ABCDEFGHJKMNPQRSTUVWXYZ23456789` stored as `recovery_hash` (sha256), sets cookie `hallway_id` (HttpOnly, SameSite=Lax, 7 days), `refresh="wait_for"`.
- `GET /api/me -> Me` (from cookie; 401 if none), `POST /api/recover {code} -> Me` (terms on `recovery_hash`; sets cookie), `GET /api/attendees/{id} -> Attendee` (404), `GET /api/attendees?q= -> list[AttendeeSummary]` (`match` on `name`, `size: 10`).
- `routes.attendees.get_attendee(client, id) -> Attendee | None`; `routes.attendees.current_attendee(request) -> Attendee` dependency.

- [ ] **Step 1:** Tests: `test_create_sets_cookie_and_returns_recovery_code`, `test_recover_with_code_sets_cookie`, `test_get_unknown_404`.
- [ ] **Step 2:** Implement with spans setting `attendee.id`. `make types`. PR "api: attendees + recovery". Merge.

### Task A3: Matches, the hybrid RRF query (Phase 2)

**Files:** `api/hallway/matching.py`, `api/hallway/routes/matches.py`, `api/tests/test_matching.py`

**Produces:**
- `matching.build_match_query(a: Attendee, exclude_ids: list[str], size: int = 5) -> dict`: spec §6 body; omits any semantic retriever whose source text is blank; always `rank_window_size: 50`, `rank_constant: 20`, `size`; each `standard` query wrapped in `bool` with `must_not: [{"ids": {"values": exclude_ids}}]`.
- `matching.explain_why(a: Attendee, b: Attendee) -> str`: deterministic one-liner, priority: offers↔asks overlap → shared tags → similar working_on.
- `models.Match`: `attendee: AttendeeSummary`, `working_on: str`, `fun_fact: str | None`, `why: str`, `icebreaker: str | None`, `score: float`.
- `GET /api/matches/{id} -> list[Match]`: excludes self + `connected_ids` (A4; until A4 lands, exclude self only); `icebreaker` read from the `suggested` edge `reason` if present, else `null`. Never calls the LLM inline.
- `routes.matches.find_matches(client, a: Attendee) -> list[Match]` for the matcher.

- [ ] **Step 1:** Tests: `test_query_has_size_and_rank_window`, `test_query_skips_blank_asks` (3 retrievers not 4), `test_query_excludes_ids`, `test_endpoint_returns_at_most_5`.
- [ ] **Step 2:** Implement; span `match.query` with `attendee.id`, `match.count`; call `chaos.sleep()` and `chaos.maybe_fail()` inside it (A8 defines them; stub as no-ops now). If A0 chose the fallback, use `knn` retrievers with `query_vector_builder` or precomputed vectors.
- [ ] **Step 3:** `make types`. PR "api: hybrid matches". Merge. Verify `curl $URL/api/matches/<seed id>` returns 5.

### Task A4: Edges (Phase 3)

**Files:** `api/hallway/routes/edges.py`, `api/tests/test_edges.py`

**Produces:**
- `models.EdgeIn`: `to_id: str`, `kind: Literal["connected"] = "connected"` (the `from` side is always the cookie holder; simpler and un-spoofable enough for a hackathon).
- `models.Edge`: `id`, `from_id`, `to_id`, `kind: Literal["connected","suggested"]`, `score: float | None`, `reason: str | None`, `created_at`.
- `edges.edge_id(a, b, kind) -> str` = `f"{min(a,b)}:{max(a,b)}:{kind}"`.
- `edges.upsert_edge(client, a, b, kind, score=None, reason=None) -> tuple[Edge, bool]` (`created` flag; `refresh="wait_for"`); increments `edges_total{kind}` only when created.
- `edges.connected_ids(client, attendee_id) -> list[str]` (`size: 500`).
- `POST /api/edges -> Edge`: 400 if `to_id == me.id`; 404 if target missing. Response includes the target's `AttendeeSummary` as `with_` (alias `with`) so the UI can say "Connected with Sam".

- [ ] **Step 1:** Tests: `test_edge_id_order_independent`, `test_self_edge_400`, `test_duplicate_is_idempotent` (counter +1 once).
- [ ] **Step 2:** Implement; wire `connected_ids` into A3's exclusion. `make types`. PR "api: edges". Merge.

### Task A5: Graph + shortest path (Phase 4)

**Files:** `api/hallway/routes/graph.py`, `api/tests/test_graph.py`

**Produces:**
- `models.GraphNode`: `id`, `name`, `groups`. `models.GraphLink`: `source`, `target`, `kind: Literal["connected","suggested","group"]`. `models.Graph`: `nodes`, `links`.
- `GET /api/graph -> Graph`: nodes = all attendees (`size: 1000`); links = all edges (`size: 5000`) + derived `group` star links (each member → first member of the group, groups ≤ 40 members).
- `GET /api/graph/path?from=&to= -> list[str]`: BFS over `connected` + `group` links; `[]` if none.
- `graph.shortest_path(links: list[GraphLink], a: str, b: str) -> list[str]` pure function.

- [ ] **Step 1:** Tests: `test_path_via_group`, `test_path_empty_when_disconnected`, `test_group_links_are_stars`.
- [ ] **Step 2:** Implement; span `graph.bfs`. `make types`. PR "api: graph". Merge.

### Task A6: Rooms + occupancy metric (Phase 5)

**Files:** `api/hallway/routes/rooms.py`, `api/tests/test_rooms.py`

**Produces:**
- `models.CheckinIn`: `room: str` (attendee from cookie). `models.Room`: `room`, `occupancy: int`, `capacity: int`.
- `POST /api/checkins -> Room`: 400 if room not in `settings.rooms`; index checkin; recompute; `telemetry.set_room_occupancy(all rooms)`.
- `GET /api/rooms -> list[Room]`: latest checkin per attendee (`terms` on `attendee_id` size 2000 + `top_hits` size 1 sorted `at desc`), counted by room; Quiet Room always listed first.
- `rooms.current_occupancy(client) -> dict[str,int]`.

- [ ] **Step 1:** Tests: `test_unknown_room_400`, `test_latest_checkin_wins`.
- [ ] **Step 2:** Implement. `make types`. PR "api: rooms". Merge.

### Task A7: Matcher CronJob (Phase 4, after A4)

**Files:** `api/hallway/matcher.py`, `api/hallway/llm.py`, `api/tests/test_matcher.py`

**Produces:**
- `llm.icebreaker(a: Attendee, b: Attendee, why: str) -> str`: one `gpt-4o-mini` chat call, `max_tokens: 60`, prompts from `prompts.py`; returns `""` on any exception.
- `matcher.run_once(client) -> int`: for each attendee (`size: 1000`) → `find_matches` → `upsert_edge(kind="suggested", score=m.score, reason=icebreaker or why)`; `matcher_pairs += 1` per pair; returns count. Span `matcher.run` with `matcher.attendees`, `matcher.pairs`.
- `python -m hallway.matcher` runs `run_once` once and exits 0.

- [ ] **Step 1:** Test `test_run_once_writes_edges_even_when_llm_raises`.
- [ ] **Step 2:** Implement. PR "matcher: suggested edges". Merge. Confirm a Job completes in Radar and `matcher.run` spans land in Dash0.

### Task A8: Chaos switch (Phase 5)

**Files:** `api/hallway/chaos.py`, `api/hallway/routes/chaos.py`

**Produces:** `chaos.mode: str = "off"`; `chaos.sleep()` (1.5 s if `latency`, adds span event `chaos.latency`); `chaos.maybe_fail()` (raises `RuntimeError("chaos")` 30% of the time if `errors`). `POST /api/chaos {mode} -> {mode}`; `GET /api/chaos -> {mode}`; both 404 unless `settings.chaos_enabled`.

- [ ] **Step 1:** Test `test_chaos_disabled_404`. Implement. PR "api: chaos switch (demo)". Merge.

### Task A9: Recap (Phase 5, first to cut)

**Files:** `api/hallway/routes/recap.py`; `llm.py` adds `recap_nudges(a, met: list[Attendee]) -> list[str]` (3 lines, `[]` on failure)

**Produces:** `models.Recap`: `met: list[AttendeeSummary]`, `nudges: list[str]`. `GET /api/recap -> Recap` for the cookie holder.

- [ ] **Step 1:** Implement, `make types`, PR "api: recap", merge.

---

## Lane W — Web (React + Vite, served by the API image)

### Task W0: Scaffold, client, router, RUM, PWA manifest (Phase 0)

**Files:** `web/` (`npm create vite@latest web -- --template react-ts`), `web/src/api/client.ts`, `web/index.html`, `web/public/manifest.webmanifest`, `web/vite.config.ts` (dev proxy `/api` → `localhost:8000`)

**Produces:**
- `client.ts`: `api.get<T>(path)`, `api.post<T>(path, body)` with `credentials: "include"`; `useMe()` → `Me | null | "loading"` via `GET /api/me`.
- Routes: `/` (Register, or redirect to `/five` if `useMe()` resolves), `/me`, `/five`, `/connect/:id`, `/recover`, `/graph`, `/rooms`, `/recap`, `/u/:id`.
- Dash0 RUM snippet in `index.html` (`serviceName: "hallway-web"`). Manifest with name, theme color, icon so "Add to Home Screen" works (optional for users, free for us).
- Bottom nav on mobile: Five · Scan-me (QR) · Graph · Rooms.

- [ ] **Step 1:** Scaffold; deps `react-router-dom`, `react-force-graph-2d`, `qrcode.react`; `npm run build` passes. PR "web: scaffold". Merge.

### Task W1: Register, profile with QR, recover (Phase 1)

**Files:** `pages/Register.tsx`, `pages/Profile.tsx`, `pages/Recover.tsx`, `components/QrCard.tsx`

**Produces:**
- Register: 4 required fields (name, working on, asks, offers), then an "optional" disclosure with groups (chips with suggestions from `/api/attendees?q=` groups seen so far + free text), tags, fun fact, comfort checkboxes (quiet room, seated meetups, text first, new to conferences). Submit → `POST /api/attendees` → if `sessionStorage.pendingConnect` is set (W3) go to `/connect/<id>`, else `/five`.
- Profile (`/me`): big `QrCard` encoding `${PUBLIC_URL}/connect/${me.id}`, caption "Have them scan this with their camera", the recovery code in a monospace box with "copy", and the profile fields.
- Recover (`/recover`): one input → `POST /api/recover` → `/five`.
- Accessibility: all inputs labelled, visible focus, 16px+ text, Enter submits, no color-only meaning.

- [ ] **Step 1:** Build, `npx tsc --noEmit`, PR "web: register + profile + recover". Merge.

### Task W2: Your Five (Phase 2)

**Files:** `pages/YourFive.tsx`, `components/MatchCard.tsx`

**Produces:** `/five` → `GET /api/matches/{me.id}` → up to 5 `MatchCard`s: name, groups, why, icebreaker (fallback "Ask them about: <fun_fact>"), buttons "Find on graph" (`/graph?focus=<id>`) and "I already know them" (`POST /api/edges`). Poll 30 s. Empty state: "You're the first one here. Share the QR and come back."

- [ ] **Step 1:** Build against a `matches.json` fixture until A3 lands. PR "web: your five". Merge.

### Task W3: The `/connect/:id` flow (Phase 3)

**Files:** `pages/Connect.tsx`

**Produces:** opening `/connect/<id>` (what the camera app does):
1. If `useMe()` is null → store `sessionStorage.pendingConnect = id`, show "Register in 30 seconds to connect with <name>" with the target's name (`GET /api/attendees/<id>`), button → `/`. After registration, Register redirects back here.
2. If registered → `POST /api/edges {to_id: id}` once → "Connected with <name> 🎉" card with their working_on/fun_fact and buttons "See on graph" / "Back to Your Five". If `id === me.id` → "That's your own code" with a link to `/me`.

- [ ] **Step 1:** Test `test_pending_connect_survives_registration` (Vitest or manual: open `/connect/x` logged out, register, land on connected card). PR "web: connect flow". Merge. Test on two real phones through the tunnel.

### Task W4: Graph (Phase 4)

**Files:** `pages/Graph.tsx`

**Produces:** `react-force-graph-2d` from `GET /api/graph`, poll 10 s merging by id (no simulation restart). Node color by first group with legend; `connected` solid, `suggested` dashed, `group` faint. Click → side panel; second click → `GET /api/graph/path` highlight or "No path yet. Could bridge: <3 names from suggested edges>". `?focus=<id>` centers; `?kiosk=1` hides nav, enlarges labels, shows a live counter "N people · M connections".

- [ ] **Step 1:** Build; test with seed data on the big screen. PR "web: live graph". Merge.

### Task W5: Rooms (Phase 5)

**Files:** `pages/Rooms.tsx`, `components/RoomGrid.tsx`

**Produces:** tiles from `GET /api/rooms` (poll 5 s): fill bar, green <50% / amber <85% / red; tap → `POST /api/checkins`. Quiet Room first. `?room=<name>` auto-checks-in (door QR codes, printed by S4).

- [ ] **Step 1:** Build. PR "web: rooms". Merge.

### Task W6: Recap (Phase 5, first to cut)

**Files:** `pages/Recap.tsx`

**Produces:** `/recap` lists `met` with "Copy follow-up" using `nudges`; client-side CSV download of names + emails present.

- [ ] **Step 1:** Build. PR "web: recap". Merge.

---

## Lane S — Story (accounts, seed, prompts, Gitar rules, demo, README)

### Task S0: Accounts + shared `.env` (Phase 0)
- [ ] Dash0 org + Ingesting token + MCP token; Radar Cloud account; cluster kubeconfig + namespace from the Radar booth; OpenAI credits. Fill `.env` in a shared password-manager note. Never paste secrets in chat.

### Task S1: Seed data (Phase 1)
**Files:** `seed/attendees.json`, `seed/seed.py`
- [ ] 60 synthetic attendees, ~8 groups (e.g. "Adobe", "CNCF Utah", "University of Utah", "Sidero", "Flagsmith", "Nebius", "Indie", "Students"), realistic cloud-native asks/offers (eBPF, GitOps, platform eng, observability, AI agents, security, Talos, WASM, founding, hiring). Include 5 **planted pairs** with mirrored asks/offers so the demo match is unmissable. `seed.py --api URL` posts attendees, then ~40 `connected` edges and ~30 check-ins using each seeded attendee's cookie. No real people's data.

### Task S2: Prompts (Phase 2)
**Files:** `api/hallway/prompts.py`
- [ ] `ICEBREAKER_SYSTEM/USER` (inputs a, b, why; one sentence ≤ 40 words, second person, specific, no emojis), `RECAP_SYSTEM/USER` (exactly 3 lines "Message <name>: <concrete follow-up>"). Three example outputs each.

### Task S3: Gitar rules + README skeleton (Phase 3)
**Files:** `docs/GITAR_RULES.md`, `README.md`
- [ ] Five rules as review instructions with rationale and a "flag this" example each. README sections: What it is · Tracks · Architecture · **Setup (attendees / team / deploy: the three blocks from this plan)** · Observability · AI-assistance disclosure (required by the rules).

### Task S4: Demo script + seed the cluster + print QR codes (Phase 4)
**Files:** `docs/DEMO.md`
- [ ] `make seed API=$(make url)`. Open `/graph?kiosk=1` on the big screen. Generate and print: title-slide QR → public URL; one QR per room → `/rooms?room=<name>`. Write the 3-minute script (spec §11) with who holds which phone and the chaos commands:
  ```bash
  curl -X POST $URL/api/chaos -H 'content-type: application/json' -d '{"mode":"latency"}'
  curl -X POST $URL/api/chaos -H 'content-type: application/json' -d '{"mode":"off"}'
  ```

### Task S5: Planned CI break → Gitar auto-apply (Phase 5)
- [ ] PR "api: rename Match.why → Match.reason" touching only `models.py` (don't regenerate types). CI `web` fails on `tsc`. Let Gitar diagnose and auto-apply (or reply asking it to fix). Screenshot diagnosis + fix commit → `docs/investigations/gitar-ci-fix.md`. Merge or close.

### Task S6: README final, screenshots, submit, rehearse (Phase 6)
- [ ] Collect screenshots: Gitar first review (P1), rule citation (P4), CI auto-fix (S5), Radar MCP (P2), `radar diagnose` (P6), Dash0 trace (P3), dashboard + SLO + MCP (P5), Agent0 answering "why did matches get slow?" (rehearsal). Link all from README. Submit the repo URL by **5:30 PM**. Rehearse twice with a timer.

---

## Self-review notes

- **Spec coverage:** §3.1–6 → A2/W1, A3/W2, A4/W3, A5/W4, A6/W5, A9/W6. §6 → A3, A7. §8 → A1 telemetry, P3, P5, A8, W0 RUM. §10 → P1–P6, S3, S5. §11 → S4. §12 fallbacks → A0, P2 (tunnel), S4. Bridge Score (§9) intentionally unplanned; if idle after Phase 5 it's one aggregation in `routes/graph.py` and a badge in `Profile.tsx`.
- **Simplicity check:** attendee path is QR → form → done, with the camera app doing the scanning; deploy path is `make secrets`, `make deploy`, `make url`; one image, one chart, one secret.
- **Type consistency:** `Attendee`, `AttendeeSummary`, `Me`, `Match`, `Edge`, `Graph*`, `Room`, `Recap` defined once in `models.py`; `find_matches`, `upsert_edge`, `connected_ids`, `current_occupancy`, `shortest_path`, `chaos.sleep/maybe_fail`, `set_room_occupancy` match between producing and consuming tasks.
- **Review Focus:** each line has a named test in A3, A4, W3, A6, A1.
