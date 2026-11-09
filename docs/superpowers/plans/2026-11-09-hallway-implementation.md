# Hallway Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **For the humans:** this is a 6-hour hackathon plan. Tasks are grouped into four parallel **lanes** (Infra, API, Web, Story). Each lane is one person. Every task says what it produces so the next lane can build against it. Tests are smoke checks, not full TDD; the demo is the test. Every task ends in a PR so Gitar reviews it.

**Goal:** Ship Hallway, a conference matchmaking + live connection graph + room occupancy app, running on Kubernetes with Elasticsearch as the only datastore, fully instrumented into Dash0, observed by Radar, and reviewed by Gitar on every PR, demoable at 5:30 PM.

**Architecture:** React/Vite `web` behind nginx calls a FastAPI `api`; `api` and a `matcher` CronJob (same image) talk to Elastic Cloud serverless using `semantic_text` (ELSER) for hybrid RRF matchmaking; everything emits OTLP to an in-cluster OTel Collector that exports to Dash0. Three workloads + collector deployed via one Helm chart into the provided namespace.

**Tech Stack:** Python 3.12, FastAPI, `elasticsearch` 9.x client, `opentelemetry-distro` + `opentelemetry-exporter-otlp`, `openai`; React 18, Vite, TypeScript, `react-force-graph-2d`, `qrcode.react`, `html5-qrcode`; Helm 3; GitHub Actions; Gitar; Radar; Dash0.

**Spec:** `docs/superpowers/specs/2026-11-09-hallway-design.md`

## Global Constraints

- Every Elasticsearch search sets `size`; every `rrf` retriever sets `rank_window_size` (Gitar rule 1).
- Every API handler runs inside a span carrying `attendee.id` when known (Gitar rule 2).
- A change to any response model in `api/hallway/models.py` regenerates `web/src/api/types.ts` in the same PR (Gitar rule 3).
- No secrets in the repo. Secrets come from the Kubernetes Secret `hallway-secrets` and local `.env` (gitignored) (Gitar rule 4).
- All timestamps UTC ISO-8601; session times carry a time zone (Gitar rule 5).
- Matches return at most 5 results. Edges ids are `min(id):max(id):kind`.
- Chaos endpoint only works when `CHAOS_ENABLED=true`.
- Nothing is merged without a Gitar review having run on the PR (it does not have to be green; it has to have run).

## Review Focus

Things the spec implies that no task's smoke test exercises. Watch for these in Gitar reviews and the 4:00 PM bug bash.

1. **Attendee with empty `asks` or `offers`** — the RRF query must skip that retriever rather than send an empty `semantic` query (ES rejects empty query strings). Test added to Task A3.
2. **Scanning your own QR or the same pair twice** — must not create a self-edge or a duplicate; the id scheme makes the second case an upsert, the first must 400. Test added to Task A4.
3. **Graph path between disconnected people** — `GET /api/graph/path` returns `[]`, not 500, and the UI says "no path yet, here's who could bridge". Test added to Task A5.
4. **Check-in to an unknown room name** — must 400 against the room list in config, otherwise the gauge grows unbounded label cardinality. Test added to Task A6.
5. **ES unavailable at startup** — `api` must retry index creation for 60 s and `/healthz` must report `es:"red"` rather than crash-looping (otherwise Radar shows a CrashLoop we did not plan). Test added to Task A1.

---

## Timeline (Mountain Time)

| Time | Infra lane | API lane | Web lane | Story lane |
|---|---|---|---|---|
| 11:00–11:30 | I1 Repo, Gitar, CI skeleton | A0 Elastic trial + ELSER check | W0 Vite scaffold | S0 Dash0 + Radar accounts, secrets handoff |
| 11:30–12:30 | I2 Helm chart + hello deploy, Radar MCP | A1 ES indices + healthz, A2 attendees | W1 Register form + profile/QR | S1 Seed data generator |
| 12:30–1:30 | I3 OTel collector → Dash0 | A3 Matches (hybrid RRF) | W2 Your Five page | S2 Icebreaker + recap prompts |
| 1:30–2:00 | I4 Deploy real images, Gitar rules | A4 Edges + QR connect | W3 QR scanner | S3 Gitar rules doc, README skeleton |
| 2:00–2:45 | lunch / panel (one person keeps CI green) | | | |
| 2:45–3:45 | I5 Dashboard + SLO in Dash0 | A5 Graph + path, A7 Matcher CronJob | W4 Graph page | S4 Demo script v1, seed the cluster |
| 3:45–4:30 | I6 Planned OOM investigation (Radar) | A6 Rooms + metrics, A8 Chaos, A9 Recap | W5 Rooms grid + W6 Recap | S5 Planned CI break (Gitar auto-apply) |
| 4:30–5:00 | bug bash, chaos rehearsal with Agent0 | | | S6 README final, screenshots |
| 5:00–5:30 | freeze, submit by 5:30 | | | rehearse 3-min demo twice |

Cut line if behind at 3:45: drop W6/A9 (recap) first, then A6/W5 (rooms). Never drop A3/W2 (matches) or A5/W4 (graph).

---

## File structure

```
hallway/
├── .github/workflows/ci.yml          # ruff, pytest, tsc, vite build, helm lint
├── .gitar/rules/                     # Gitar repo rules (one .md per rule)
├── Makefile                          # dev, types, seed, deploy
├── api/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── hallway/
│   │   ├── __init__.py
│   │   ├── main.py                   # FastAPI app, lifespan creates indices
│   │   ├── config.py                 # Settings from env (ES_URL, ES_API_KEY, ELSER_ID, ROOMS, CHAOS_ENABLED, OPENAI_API_KEY)
│   │   ├── es.py                     # client + index mappings + ensure_indices()
│   │   ├── models.py                 # Pydantic request/response models (source of truth for TS types)
│   │   ├── telemetry.py              # tracer, meters, gauges
│   │   ├── routes/attendees.py
│   │   ├── routes/matches.py
│   │   ├── routes/edges.py
│   │   ├── routes/graph.py
│   │   ├── routes/rooms.py
│   │   ├── routes/recap.py
│   │   ├── routes/chaos.py
│   │   ├── matching.py               # build_match_query(), explain_why()
│   │   ├── llm.py                    # icebreaker(), recap_nudges()
│   │   └── matcher.py                # CronJob entrypoint
│   └── tests/                        # pytest, ES mocked via responses on the transport
├── web/
│   ├── Dockerfile                    # vite build → nginx
│   ├── nginx.conf                    # /api → api:8000
│   ├── index.html                    # Dash0 RUM snippet
│   └── src/
│       ├── api/client.ts, api/types.ts (generated)
│       ├── pages/Register.tsx, Profile.tsx, YourFive.tsx, Scan.tsx, Graph.tsx, Rooms.tsx, Recap.tsx
│       └── components/QrCard.tsx, MatchCard.tsx, RoomGrid.tsx
├── deploy/
│   ├── chart/hallway/                # Deployments, Services, CronJob, Ingress, values.yaml
│   └── otel-collector-values.yaml
├── seed/
│   ├── attendees.json                # 60 synthetic attendees
│   └── seed.py
└── docs/
    ├── DEMO.md
    └── GITAR_RULES.md
```

---

## Lane I — Infra (Kubernetes, Radar, Dash0 plumbing, Gitar, CI)

### Task I1: Repo bootstrap, Gitar install, CI skeleton (11:00–11:30)

**Files:**
- Create: `.github/workflows/ci.yml`, `Makefile`, `.gitignore`, `README.md` (title + one paragraph + "setup: see below" placeholder that S6 fills)

**Produces:** a `main` branch with branch protection off (speed), CI running on every PR, Gitar commenting on every PR.

- [ ] **Step 1:** Push the two spec/plan docs to `main`. Install the Gitar GitHub App on this repo (app.gitar.ai → connect GitHub → select repo). Turn on **auto-apply** in the Gitar repo settings.
- [ ] **Step 2:** Write `.github/workflows/ci.yml` with four jobs: `api` (`uv sync`, `ruff check`, `pytest`), `web` (`npm ci`, `npx tsc --noEmit`, `npm run build`), `helm` (`helm lint deploy/chart/hallway`), `docker` (build both images, no push). Jobs must tolerate the directories not existing yet (`if: hashFiles('api/pyproject.toml') != ''`).
- [ ] **Step 3:** Open PR "ci: skeleton" and confirm Gitar posts a review comment. Screenshot it for the demo. Merge.

Run: open the PR page. Expected: a Gitar comment within ~2 minutes and a green CI run.

### Task I2: Helm chart and hello-world deploy, Radar connected (11:30–12:30)

**Files:**
- Create: `deploy/chart/hallway/Chart.yaml`, `values.yaml`, `templates/{web,api}-deployment.yaml`, `templates/{web,api}-service.yaml`, `templates/matcher-cronjob.yaml`, `templates/ingress.yaml`, `templates/_helpers.tpl`

**Produces:** `helm upgrade --install hallway deploy/chart/hallway -n $NS` works; `values.yaml` keys `image.api`, `image.web`, `ingress.host`, `api.resources.limits.memory` (default `256Mi`), `matcher.schedule` (`*/2 * * * *`), `secretName: hallway-secrets`, `env.ROOMS` (`"Main Stage,Room A,Room B,Coffee Bar,Quiet Room"`).

- [ ] **Step 1:** `kubectl config use-context <provided>`; confirm namespace with `kubectl get ns`. Run `kubectl radar` and `claude mcp add --transport http radar http://localhost:9280/mcp-readonly`. From Claude Code ask Radar "what is running in namespace $NS" to prove the MCP works. Screenshot.
- [ ] **Step 2:** Write the chart with `api` image defaulting to `ghcr.io/<org>/hallway-api:latest` and `web` to `ghcr.io/<org>/hallway-web:latest`, both with `imagePullPolicy: Always`. Env on `api` and the CronJob: `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317`, `OTEL_SERVICE_NAME`, `OTEL_RESOURCE_ATTRIBUTES=deployment.environment=hackathon`, plus `envFrom.secretRef: hallway-secrets`.
- [ ] **Step 3:** Create the secret out-of-band (never committed):
  ```bash
  kubectl create secret generic hallway-secrets -n $NS \
    --from-literal=ES_URL=... --from-literal=ES_API_KEY=... \
    --from-literal=ELSER_ID=... --from-literal=OPENAI_API_KEY=... \
    --from-literal=DASH0_AUTH_TOKEN=...
  ```
- [ ] **Step 4:** Deploy with placeholder images (`nginx` for web, `hashicorp/http-echo` for api) and verify in the Radar UI that two Deployments and one CronJob are healthy.
- [ ] **Step 5:** Add a `docker` job step to CI that pushes images to GHCR on `main` only. PR "deploy: helm chart", merge.

Run: `helm lint deploy/chart/hallway && kubectl get deploy,cronjob -n $NS`. Expected: lint passes; `web`, `api` Available, `matcher` CronJob listed.

### Task I3: OTel Collector to Dash0 (12:30–1:30)

**Files:**
- Create: `deploy/otel-collector-values.yaml`

**Produces:** Service `otel-collector:4317` (gRPC) and `:4318` (HTTP) in the namespace, exporting to Dash0.

- [ ] **Step 1:** In Dash0: Settings → Endpoints → copy OTLP gRPC endpoint; Settings → Auth Tokens → create token with *Ingesting* scope. Put the token in `hallway-secrets` (I2 step 3).
- [ ] **Step 2:** Write values: `mode: deployment`, receivers `otlp` (grpc+http), processors `batch` + `resource` (add `service.namespace=hallway`), exporter `otlp` with `endpoint: <dash0 endpoint>` and `headers.Authorization: "Bearer ${env:DASH0_AUTH_TOKEN}"`, `extraEnvs` from the secret. Pipelines for traces, metrics, logs.
- [ ] **Step 3:** `helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts && helm upgrade --install otel-collector open-telemetry/opentelemetry-collector -n $NS -f deploy/otel-collector-values.yaml`.
- [ ] **Step 4:** Send a test span with `telemetrygen traces --otlp-endpoint otel-collector:4317 --otlp-insecure` from a throwaway pod and confirm it appears in Dash0 Tracing. Screenshot.

Run: `kubectl logs deploy/otel-collector -n $NS | tail`. Expected: no `401`/`permission denied` lines; test trace visible in Dash0.

### Task I4: Real images deployed, Gitar rules live (1:30–2:00)

**Files:**
- Create: `.gitar/rules/elasticsearch.md`, `.gitar/rules/telemetry.md`, `.gitar/rules/api-contract.md`, `.gitar/rules/secrets.md`, `.gitar/rules/time.md` (text from `docs/GITAR_RULES.md`, Task S3)

**Produces:** `api` and `web` running from GHCR images; Gitar reviewing against project rules.

- [ ] **Step 1:** After A1 and W1 merge, confirm CI pushed images; `helm upgrade --install ... --set image.api.tag=<sha>`.
- [ ] **Step 2:** Commit `.gitar/rules/*.md`. If the Gitar dashboard shows a different location for repo rules, follow the dashboard and keep these files as the human-readable copy.
- [ ] **Step 3:** Open a deliberately rule-breaking PR (an ES search without `size`) and confirm Gitar's review cites the rule. Screenshot. Close the PR without merging.

Run: `curl https://<ingress.host>/healthz`. Expected: `{"ok":true,"es":"green"}`.

### Task I5: Dash0 dashboard and SLO (2:45–3:45)

**Produces:** Dashboard "Hallway Live" and SLO "matches-latency".

- [ ] **Step 1:** Dashboard panels: `hallway.room.occupancy` by `room` (bar), `http.server.request.duration` p95 for route `/api/matches/{id}`, `hallway.edges.total` rate by `kind`, error rate by route, matcher run count.
- [ ] **Step 2:** SLO: p95 latency of `POST|GET /api/matches/{id}` < 800 ms, 99% success, 1 h window.
- [ ] **Step 3:** Add Dash0 MCP to Claude Code (Settings → Endpoints → MCP; token with read on the dataset): `claude mcp add --transport http dash0 <url> --header "Authorization: Bearer $DASH0_MCP_TOKEN"`. Ask "which routes are slowest in the last 15 minutes" to prove it works. Screenshot.

### Task I6: Planned real issue for Radar (3:45–4:30)

- [ ] **Step 1:** `helm upgrade ... --set api.resources.limits.memory=48Mi`. Wait for `OOMKilled` (`kubectl get pod -n $NS -w`).
- [ ] **Step 2:** Run `radar diagnose deploy/api -n $NS` (and/or click Investigate in the Radar UI). Save the transcript to `docs/investigations/radar-oom.md`.
- [ ] **Step 3:** Apply the fix Radar proposes (bump limit back to `256Mi`) via a PR so Gitar sees it too. Merge, redeploy.

Run: `kubectl get pod -n $NS -l app=api`. Expected: `Running`, restarts not increasing.

---

## Lane A — API (FastAPI + Elasticsearch)

### Task A0: Elastic trial + ELSER check (11:00–11:30)

- [ ] **Step 1:** Create an Elastic Cloud serverless **Elasticsearch** project. Create an API key. Note the endpoint URL.
- [ ] **Step 2:** In Kibana Dev Tools: `GET _inference` and note the ELSER endpoint id (expected `.elser-2-elastic` on serverless). Create a throwaway index with one `semantic_text` field, index one doc, run a `match` on it. If this fails, **decide now**: switch to OpenAI `text-embedding-3-small` + `dense_vector` (`dims: 1536`, `index: true`, `similarity: cosine`) and `knn` retrievers in A3. Tell the team.
- [ ] **Step 3:** Hand `ES_URL`, `ES_API_KEY`, `ELSER_ID` to Infra for the secret.

### Task A1: API skeleton, settings, indices, healthz (11:30–12:00)

**Files:**
- Create: `api/pyproject.toml`, `api/Dockerfile`, `api/hallway/{__init__,main,config,es,telemetry}.py`, `api/tests/test_health.py`

**Produces:**
- `config.Settings` (pydantic-settings) with `es_url: str`, `es_api_key: str`, `elser_id: str`, `rooms: list[str]` (parsed from comma-separated `ROOMS`), `chaos_enabled: bool = False`, `openai_api_key: str | None`.
- `es.get_client() -> Elasticsearch`, `es.ensure_indices(client) -> None` (idempotent, creates `attendees`, `edges`, `checkins` with the spec §5 mappings), `es.INDEX_ATTENDEES = "attendees"` etc.
- `telemetry.tracer`, `telemetry.meter`, `telemetry.room_occupancy` (ObservableGauge or `set`-style gauge), `telemetry.edges_total` (Counter), `telemetry.matcher_pairs` (Counter).
- `GET /healthz -> {"ok": bool, "es": "green"|"red"}`.

- [ ] **Step 1:** Write `api/tests/test_health.py::test_healthz_reports_red_when_es_down` using `TestClient` with `get_client` patched to raise. Assert status 200 and `es == "red"`.
- [ ] **Step 2:** Implement. Lifespan: loop up to 60 s calling `ensure_indices`, log and continue (do not exit) on failure. Dockerfile `CMD ["opentelemetry-instrument","uvicorn","hallway.main:app","--host","0.0.0.0","--port","8000"]`.
- [ ] **Step 3:** `cd api && uv run pytest -q`. Expected: pass. PR "api: skeleton", merge.

### Task A2: Attendees (12:00–12:30)

**Files:**
- Create: `api/hallway/models.py`, `api/hallway/routes/attendees.py`, `api/tests/test_attendees.py`

**Produces:**
- `models.AttendeeIn` (`name: str`, `email: str | None`, `working_on: str`, `asks: str`, `offers: str`, `tags: list[str] = []`, `groups: list[str] = []`, `fun_fact: str | None`, `comfort: list[str] = []`), `models.Attendee(AttendeeIn)` + `id: str`, `created_at: datetime`.
- `POST /api/attendees -> Attendee` (id = `uuid4().hex[:10]`; sets cookie `hallway_id`), `GET /api/attendees/{id} -> Attendee` (404 if missing), `GET /api/attendees?q= -> list[AttendeeSummary]` where `AttendeeSummary = {id, name, groups}` (`match` on `name`, `size: 10`).
- `routes.attendees.get_attendee(client, id) -> Attendee | None` for reuse.

- [ ] **Step 1:** Test `test_create_attendee_returns_id_and_sets_cookie` and `test_get_unknown_404`.
- [ ] **Step 2:** Implement; every handler wrapped in `with tracer.start_as_current_span(...)` setting `attendee.id`. Index with `refresh="wait_for"` so the graph shows the node immediately.
- [ ] **Step 3:** Run `make types` (Task W0 defines it) to regenerate `web/src/api/types.ts`. Commit both. PR "api: attendees", merge.

### Task A3: Matches — the hybrid RRF query (12:30–1:30)

**Files:**
- Create: `api/hallway/matching.py`, `api/hallway/routes/matches.py`, `api/tests/test_matching.py`

**Produces:**
- `matching.build_match_query(a: Attendee, exclude_ids: list[str], size: int = 5) -> dict` — returns the spec §6 body. Skips any `semantic` retriever whose source text is empty. Always includes `rank_window_size: 50`, `rank_constant: 20`, `size`.
- `matching.explain_why(a: Attendee, b: Attendee, hit: dict) -> str` — deterministic one-liner from which retrievers matched (use `_rank` positions if available, else which fields overlap).
- `models.Match = {attendee: AttendeeSummary + working_on + fun_fact, why: str, icebreaker: str | None, score: float}`.
- `GET /api/matches/{id} -> list[Match]` — excludes self and ids already `connected`; `icebreaker` is read from the `suggested` edge's `reason` if the matcher has written one, else `null` (never waits on the LLM).
- `routes.matches.find_matches(client, a: Attendee) -> list[Match]` for the matcher to reuse.

- [ ] **Step 1:** Tests: `test_query_has_size_and_rank_window`, `test_query_skips_empty_asks` (attendee with `asks=""` yields 3 retrievers, not 4), `test_query_excludes_ids` (every `standard` query contains `must_not` terms with the ids), `test_matches_endpoint_returns_at_most_5`.
- [ ] **Step 2:** Implement. Custom span `match.query` with attributes `attendee.id`, `match.count`. If the trial rejected `semantic` inside `standard` in A0, use `{"match": {"offers_semantic": {"query": ...}}}` instead.
- [ ] **Step 3:** `uv run pytest -q`; regenerate types; PR "api: hybrid matches", merge. Try it against real data: `curl $API/api/matches/<id>`.

### Task A4: Edges (1:30–2:00)

**Files:**
- Create: `api/hallway/routes/edges.py`, `api/tests/test_edges.py`

**Produces:**
- `models.EdgeIn = {from_id: str, to_id: str, kind: Literal["connected"]}` (serialized as `from`/`to` via aliases), `models.Edge = EdgeIn + {id, score: float | None, reason: str | None, created_at}`.
- `edges.edge_id(a: str, b: str, kind: str) -> str` = `f"{min(a,b)}:{max(a,b)}:{kind}"`.
- `edges.upsert_edge(client, a, b, kind, score=None, reason=None) -> Edge` (index with explicit `_id`, `refresh="wait_for"`); increments `telemetry.edges_total{kind}` only on create.
- `edges.connected_ids(client, attendee_id) -> list[str]` (`size: 500`).
- `POST /api/edges -> Edge` — 400 if `from == to`; 404 if either attendee missing.

- [ ] **Step 1:** Tests: `test_edge_id_is_order_independent`, `test_self_edge_400`, `test_duplicate_scan_is_idempotent` (two posts → same id, counter incremented once).
- [ ] **Step 2:** Implement. Regenerate types. PR "api: edges", merge.

### Task A5: Graph + shortest path (2:45–3:30)

**Files:**
- Create: `api/hallway/routes/graph.py`, `api/tests/test_graph.py`

**Produces:**
- `models.GraphNode = {id, name, groups: list[str]}`, `models.GraphLink = {source: str, target: str, kind: Literal["connected","suggested","group"]}`, `models.Graph = {nodes, links}`.
- `GET /api/graph -> Graph` — nodes = all attendees (`size: 1000`, `_source` limited); links = all `connected` + `suggested` edges (`size: 5000`) plus derived `group` links: for each group with ≤ 40 members, link each member to the group's first member (a star, so the cluster reads visually without O(n²) links).
- `GET /api/graph/path?from=&to= -> list[str]` — BFS over `connected` + `group` links; `[]` if no path.
- `graph.shortest_path(links: list[GraphLink], a: str, b: str) -> list[str]` pure function.

- [ ] **Step 1:** Tests: `test_path_found_through_group`, `test_path_empty_when_disconnected`, `test_group_links_are_stars`.
- [ ] **Step 2:** Implement with span `graph.bfs` (attributes `nodes`, `links`, `path.len`). Regenerate types. PR "api: graph", merge.

### Task A6: Rooms + occupancy metric (3:45–4:15)

**Files:**
- Create: `api/hallway/routes/rooms.py`, `api/tests/test_rooms.py`

**Produces:**
- `models.CheckinIn = {attendee_id: str, room: str}`, `models.Room = {room: str, occupancy: int, capacity: int}`.
- `POST /api/checkins -> Room` — 400 if `room not in settings.rooms`. Indexes a checkin, recomputes occupancy, sets `telemetry.room_occupancy` for **every** room (so rooms people left go down).
- `GET /api/rooms -> list[Room]` — occupancy via `terms(attendee_id, size 2000)` + `top_hits(size 1, sort at desc)`, counting by latest room. Capacity from a static dict in `config` (`Main Stage: 150`, others `40`, `Coffee Bar: 25`).
- `rooms.current_occupancy(client) -> dict[str, int]` for the matcher/metrics.

- [ ] **Step 1:** Tests: `test_unknown_room_400`, `test_latest_checkin_wins` (attendee checks into A then B → A:0, B:1).
- [ ] **Step 2:** Implement. Regenerate types. PR "api: rooms", merge.

### Task A7: Matcher CronJob (3:00–3:45, parallel with A5 if two API people; otherwise after A5)

**Files:**
- Create: `api/hallway/matcher.py`, `api/hallway/llm.py`, `api/tests/test_matcher.py`

**Produces:**
- `llm.icebreaker(a: Attendee, b: Attendee, why: str) -> str` — one OpenAI chat call, `max_tokens: 60`, prompt from Task S2; returns `""` on any exception (never raises).
- `matcher.run_once(client) -> int` — for every attendee (`size: 1000`): `find_matches` → for each match `upsert_edge(kind="suggested", score, reason=icebreaker or why)`; increments `matcher_pairs`; returns pairs written. Wrapped in span `matcher.run`.
- `python -m hallway.matcher` entrypoint; CronJob template in I2 runs it under `opentelemetry-instrument`.

- [ ] **Step 1:** Test `test_run_once_writes_suggested_edges_and_never_raises_on_llm_error` (patch `llm.icebreaker` to raise → edges still written with `reason=why`).
- [ ] **Step 2:** Implement. PR "matcher: suggested edges cronjob", merge. Verify in Radar that a Job completes and in Dash0 that `matcher.run` spans arrive.

### Task A8: Chaos switch (4:15–4:30)

**Files:**
- Create: `api/hallway/routes/chaos.py`; Modify: `api/hallway/matching.py` (inject `chaos.sleep()` inside `match.query`), `api/hallway/es.py` (wrap `search` to raise on `errors` mode 30% of the time)

**Produces:** `POST /api/chaos {mode}` → `{mode}`; 404 unless `CHAOS_ENABLED=true`. Module-level `chaos.mode: str = "off"`. `latency` = `time.sleep(1.5)` recorded as span event `chaos.latency`.

- [ ] **Step 1:** Test `test_chaos_disabled_404`.
- [ ] **Step 2:** Implement. PR "api: chaos switch (demo)", merge. Set `CHAOS_ENABLED=true` in `values.yaml` for the hackathon deployment only.

### Task A9: Recap (4:15–4:30, drop first if behind)

**Files:**
- Create: `api/hallway/routes/recap.py`; Modify: `api/hallway/llm.py` (add `recap_nudges`)

**Produces:** `models.Recap = {met: list[AttendeeSummary], nudges: list[str]}`; `GET /api/recap/{id}` — `met` = attendees across `connected` edges; `nudges` = `llm.recap_nudges(a, met) -> list[str]` (3 lines, "message X about Y", empty list on failure).

- [ ] **Step 1:** Implement, regenerate types, PR "api: recap", merge.

---

## Lane W — Web (React + Vite)

### Task W0: Scaffold, API client, types pipeline (11:00–11:30)

**Files:**
- Create: `web/` via `npm create vite@latest web -- --template react-ts`, `web/Dockerfile`, `web/nginx.conf`, `web/src/api/client.ts`, `Makefile` target `types`

**Produces:**
- `make types` = `curl $API/openapi.json | npx openapi-typescript -o web/src/api/types.ts` (API lane runs it after each model change).
- `client.ts`: `api.get<T>(path)`, `api.post<T>(path, body)` with `credentials: "include"`; `useMe()` hook reading the `hallway_id` cookie.
- Router with routes `/`, `/me`, `/five`, `/scan`, `/graph`, `/rooms`, `/recap`, `/u/:id`.
- `index.html` has the Dash0 RUM snippet (from Dash0 → Settings → RUM) with `serviceName: "hallway-web"`.
- nginx proxies `/api/` to `http://api:8000/`.

- [ ] **Step 1:** Scaffold, add deps: `react-router-dom`, `react-force-graph-2d`, `qrcode.react`, `html5-qrcode`. `npm run build` passes. PR "web: scaffold", merge.

### Task W1: Register + profile with QR (11:30–12:30)

**Files:**
- Create: `web/src/pages/Register.tsx`, `web/src/pages/Profile.tsx`, `web/src/components/QrCard.tsx`

**Produces:** `/` is the registration form (fields per `AttendeeIn`; tags/groups as chip inputs; comfort as checkboxes: "quiet room", "seated meetups", "text first", "new to conferences"). On submit → `POST /api/attendees` → navigate `/five`. `/me` and `/u/:id` show the profile; `QrCard` renders a QR of `${origin}/scan?connect=<id>`.

- [ ] **Step 1:** Build; all inputs have `<label>`s; form submits with Enter; tab order correct (Merge Forward). `npx tsc --noEmit` passes. PR "web: register + profile", merge.

### Task W2: Your Five (12:30–1:30)

**Files:**
- Create: `web/src/pages/YourFive.tsx`, `web/src/components/MatchCard.tsx`

**Produces:** `/five` fetches `GET /api/matches/{me}` and shows up to 5 `MatchCard`s: name, groups, "why" line, icebreaker (or "Ask them about: <fun_fact>" if null), buttons "Find them on the graph" (→ `/graph?focus=<id>`) and "I know them" (→ `POST /api/edges`). Refresh every 30 s.

- [ ] **Step 1:** Build with a `matches.json` fixture while A3 lands. PR "web: your five", merge.

### Task W3: QR scanner (1:30–2:00)

**Files:**
- Create: `web/src/pages/Scan.tsx`

**Produces:** `/scan` opens the camera via `html5-qrcode`; on decode of a URL with `?connect=<id>` → `POST /api/edges {from: me, to: id, kind: "connected"}` → toast "Connected with <name>" → link to `/graph`. If opened directly as `/scan?connect=<id>` (from scanning with the phone's camera app), skip the camera and connect immediately. Requires HTTPS or localhost for camera access: note this for Infra (ingress TLS or the Cloudflare tunnel fallback).

- [ ] **Step 1:** Build, test on two phones. PR "web: scan to connect", merge.

### Task W4: Graph page (2:45–3:45)

**Files:**
- Create: `web/src/pages/Graph.tsx`

**Produces:** `/graph` renders `react-force-graph-2d` from `GET /api/graph` (poll every 10 s, merge nodes so the simulation doesn't restart). Node color by first group (fixed palette, legend). `connected` links solid, `suggested` dashed, `group` faint. Click node → side panel with profile. Click a second node → `GET /api/graph/path` → highlight path or show "No path yet. People who could bridge: <top 3 suggested>". `?focus=<id>` centers and highlights. Big-screen mode: `?kiosk=1` hides chrome and enlarges labels.

- [ ] **Step 1:** Build. PR "web: live graph", merge. Test with seed data on the big screen.

### Task W5: Rooms grid (3:45–4:15)

**Files:**
- Create: `web/src/pages/Rooms.tsx`, `web/src/components/RoomGrid.tsx`

**Produces:** `/rooms` shows a tile per room from `GET /api/rooms` (poll 5 s): fill bar `occupancy/capacity`, color green→amber→red at 50%/85%; tap tile → `POST /api/checkins`. "Quiet Room" tile is always shown first (Merge Forward). `?room=<name>` auto-checks-in (for door QR codes).

- [ ] **Step 1:** Build. PR "web: rooms", merge.

### Task W6: Recap (4:15–4:30, drop first if behind)

**Files:**
- Create: `web/src/pages/Recap.tsx`

**Produces:** `/recap` lists `met` with "Copy follow-up" buttons using `nudges`, and a "Download contacts (CSV)" link (client-side CSV of names + emails present).

- [ ] **Step 1:** Build. PR "web: recap", merge.

---

## Lane S — Story (accounts, seed data, prompts, Gitar rules, demo, README)

### Task S0: Accounts and secrets handoff (11:00–11:30)

- [ ] Create Dash0 account (if not done before arrival), Radar Cloud account, get the provided cluster kubeconfig + namespace from the Radar booth, confirm OpenAI credits. Put all secrets in a shared password-manager note, never in Slack/Discord in plain text. Hand to Infra.

### Task S1: Seed data (11:30–12:30)

**Files:**
- Create: `seed/attendees.json`, `seed/seed.py`, Makefile target `seed`

**Produces:** 60 synthetic attendees spanning ~8 groups (companies/communities like "Adobe", "CNCF Utah", "University of Utah", "Sidero", "Flagsmith", "Nebius", "Indie", "Students"), realistic `working_on`/`asks`/`offers` across cloud-native topics (eBPF, GitOps, platform eng, observability, AI agents, security, Talos, WASM, startups/founding, hiring). Include 5 "planted pairs" whose asks/offers mirror each other exactly so the demo match is unmissable. `seed.py` posts them to `$API/api/attendees` and adds ~40 `connected` edges and ~30 check-ins.

- [ ] **Step 1:** Generate with an LLM, hand-check for plausibility and no real people's personal data. `make seed API=https://<host>`.

### Task S2: Prompts (12:30–1:30)

**Files:**
- Create: `api/hallway/prompts.py` (API lane imports it)

**Produces:** `ICEBREAKER_SYSTEM`, `ICEBREAKER_USER` template (inputs: a, b, why; output: one sentence ≤ 40 words, second person, specific, no emojis, no "I noticed"), `RECAP_SYSTEM`, `RECAP_USER` (inputs: a, met; output: exactly 3 lines, each "Message <name>: <concrete follow-up>"). Include 3 example outputs for each in the file as docstrings.

### Task S3: Gitar rules + README skeleton (1:30–2:00)

**Files:**
- Create: `docs/GITAR_RULES.md`, modify `README.md`

**Produces:** the five rules from Global Constraints written as review instructions, each with a one-line rationale and a "what to flag" example. README sections: What it is, Tracks, Architecture diagram, Run locally, Deploy, Observability, AI-assistance disclosure (required by the rules: Claude Code + Gitar + Agent0 + Radar used, and how).

### Task S4: Demo script v1 + seed the cluster (2:45–3:45)

**Files:**
- Create: `docs/DEMO.md` (spec §11, with exact URLs, who holds which phone, and the chaos commands)

- [ ] Run `make seed` against the deployed API. Open `/graph?kiosk=1` on the big screen. Print the registration QR large on the title slide.

### Task S5: Planned CI break for Gitar auto-apply (3:45–4:30)

- [ ] **Step 1:** Open PR "api: rename Match.why → Match.reason" changing only `models.py` (do **not** regenerate types). CI `web` job fails on `tsc`.
- [ ] **Step 2:** Watch Gitar diagnose the CI failure and (with auto-apply on) push a fix commit regenerating/adjusting `types.ts` and `MatchCard.tsx`. If auto-apply does not fire, reply on the PR asking Gitar to fix it. Screenshot the diagnosis and the fix commit.
- [ ] **Step 3:** Decide: merge (keep `reason`) or close. Either way, save screenshots to `docs/investigations/gitar-ci-fix.md`.

### Task S6: README final, screenshots, submission (4:30–5:30)

- [ ] Collect: Gitar review screenshot (I1), rules-violation review (I4), CI auto-fix (S5), Radar MCP query (I2), `radar diagnose` transcript (I6), Dash0 trace (I3), dashboard + SLO (I5), Agent0/MCP latency diagnosis (4:30 rehearsal). Put them in `docs/investigations/` and link from README.
- [ ] Submit the repo URL by **5:30 PM**. Rehearse the 3-minute demo twice with a timer.

---

## Self-review notes

- **Spec coverage:** §3 items 1–6 → A2/W1, A3/W2, A4/W3, A5/W4, A6/W5, A9/W6. §6 → A3, A7. §8 → A1 (telemetry), I3, I5, A8, W0 (RUM). §9 Bridge Score is stretch and has no task on purpose; if someone is idle after 4:30, it is one terms aggregation in `routes/graph.py` plus a badge in `Profile.tsx`. §10 → I1–I6, S3, S5. §11 → S4. §12 fallbacks are referenced in A0, W3, I2.
- **Type consistency:** `Attendee`, `AttendeeSummary`, `Match`, `Edge`, `Graph*`, `Room`, `Recap` are defined once in `models.py` and consumed by name above; `find_matches`, `upsert_edge`, `connected_ids`, `current_occupancy`, `shortest_path` signatures match between producing and consuming tasks.
- **Review Focus:** each of the five lines has a named test in A3, A4, A5, A6, A1.
