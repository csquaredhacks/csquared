# Runbook: from now to 5:30 PM

The app on this branch is complete and tested end to end against a real Elasticsearch.
What is left is work only humans can do: accounts, secrets, the cluster, the sponsor tools,
and the story. Four lanes, one person each. Times are Mountain Time.

## Do first, together (15 minutes)

1. Open a pull request from this branch into `main`. Do not squash away history.
2. Install the Gitar GitHub App on the repo (app.gitar.ai) **before** merging, so the first
   PR gets a review. Paste the rules from `docs/GITAR_RULES.md` where the Gitar dashboard asks
   for repository rules. Turn on auto-apply for CI fixes.
3. `cp .env.example .env` on one laptop. Share the filled file over a private channel, never
   through the repo.

## Lanes

**Search (Elasticsearch)**
1. Create an Elastic Cloud serverless Elasticsearch project. Copy the endpoint and an API key into `.env`.
2. In Dev Tools run `GET _inference`. Put the ELSER endpoint id in `ELSER_ID`. If there is none, leave it empty and the app runs on BM25 only.
3. `make dev`, then `make seed`. Open http://localhost:5173, register, check Your Five.
4. If you change `ELSER_ID` after indices exist, delete the three `hallway-*` indices and reseed. Mappings are created once.
5. Warm ELSER before the demo: register one throwaway person ten minutes ahead.
6. Stretch, only after everything else: a `sessions` index with talk abstracts, matched the same way.

**Platform (Kubernetes + Radar)**
1. Image: merge to `main`, CI pushes `ghcr.io/<owner>/hallway`. Make the package public in GitHub (Packages → Package settings → Change visibility). No time for that? `make image-ttl` pushes to an anonymous registry and prints the reference.
2. `make secrets`, `make deploy`, `make url`. Open the URL on a phone over cellular data.
3. Connect Radar's MCP to your coding agent. Use Radar to watch every rollout from now on, and screenshot it.
4. Around 2:30: `make oom-demo`. Watch the pod get OOMKilled in Radar. Run the Radar AI investigation. Save what it said in `docs/investigations/`. `make oom-fix`.

**Observability (Dash0)**
1. Put the Dash0 OTLP endpoint and auth token in `.env` and redeploy. Check that traces for `hallway-api` arrive.
2. Install the Dash0 Kubernetes operator from their onboarding page for pod logs and cluster metrics.
3. For browser monitoring set `DASH0_RUM_URL` and `DASH0_RUM_TOKEN`. Use a token limited to ingest: it is sent to every browser.
4. Build the "Hallway Live" dashboard: `hallway.room.occupancy` by room, `hallway.edges.total` by kind, `hallway.matcher.pairs`, p95 of `GET /api/matches`, error rate. Add an SLO: matches p95 under 800 ms.
5. Around 3:00: someone turns on slow mode (command in `docs/DEMO.md`). Ask Agent0 why matches are slow. It should land on the `match.query` span. Save the conversation in `docs/investigations/`.

**Story (Gitar + demo + submission)**
1. Every change from now on is a small PR. Reply to Gitar's comments in the PR. Screenshot the good ones.
2. Around 2:00 run the planned CI break in `docs/DEMO.md` and let Gitar fix it.
3. Fill in the README: screenshots, AI disclosure, team names.
4. Seed the cluster at 4:15. Print QR codes after that, not before.
5. Rehearse the three minutes twice with a timer. Submit by 5:15, not 5:30.

## Timeline

| Time | Goal |
|---|---|
| now to 1:15 | First PR reviewed and merged. App running locally and on the cluster. Public URL works on a phone. |
| 1:15 to 2:00 | Traces in Dash0. Radar MCP connected. Real Elastic data seeded. Each person has merged one PR. |
| 2:00 to 3:30 | The three incidents, each written up. Dashboard and SLO built. |
| 3:30 to 4:30 | Polish only. Feature freeze at 4:30. |
| 4:30 to 5:15 | Seed, print, rehearse twice, submit. |

## If something is on fire

| Symptom | Do this |
|---|---|
| Matches are empty | `curl <url>/healthz`. If `es` is `red`, check `ES_URL` and the API key. If green, reseed. |
| ELSER errors on register | Set `ELSER_ID` to empty, delete the `hallway-*` indices, redeploy, reseed. |
| Tunnel URL does not load | `kubectl -n hallway rollout restart deploy/hallway-tunnel`, then `make url`. The URL changes. Last resort: `kubectl port-forward svc/hallway 8000` and demo from the laptop. |
| Image will not pull | `make image-ttl`, then `make deploy IMAGE=<printed ref>`. |
| OpenAI is down | Nothing to do. Icebreakers fall back to templates. |
| Venue Wi-Fi is down | Phone hotspot for the laptop. Attendee phones on cellular still reach the tunnel. |
