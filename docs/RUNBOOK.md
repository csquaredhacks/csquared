# Runbook: from 1 PM to 5:30 PM

**The plan in one line:** get the app running first, then spend the afternoon on the
pre-conference experience, because that is what we pitch. Design and order of the
pre-conference work: [`PRE_CONFERENCE.md`](PRE_CONFERENCE.md). Times are Mountain Time.

## Where we are

| Part | State |
|---|---|
| API | Done. 21 tests pass against a real Elasticsearch 9.2. |
| Web app | Written and compiles. Not yet clicked through against the real API. |
| Dockerfile, Helm chart, CI | Written. Never built, installed or run. |
| Pre-conference features B to E | Designed, not built. |

So the first job is to run what exists. Nothing below matters if the app is not up.

## Priorities, in order

1. **Baseline runs**: locally, then on the cluster, with a public URL that opens on a phone.
2. **Pre-conference experience**: A, then B, then C, then D. This is the pitch.
3. **Sponsor evidence**: Gitar reviews, Dash0 dashboard and investigation, Radar investigation.
4. **Demo**: seeded in two acts, rehearsed twice.

If two of these compete for the same person, the lower number wins.

## Do first, together (15 minutes)

1. Open a pull request from `claude/pensive-darwin-dn6p59` into `main`. Do not squash away history.
2. Install the Gitar GitHub App on the repo (app.gitar.ai) **before** merging, so the first
   PR gets a review. Paste the rules from `docs/GITAR_RULES.md` where the Gitar dashboard asks
   for repository rules. Turn on auto-apply for CI fixes.
3. Change the image name in `Makefile` and `deploy/chart/hallway/values.yaml` from
   `ghcr.io/biancaravago/hallway` to `ghcr.io/csquaredhacks/hallway`.
4. `cp .env.example .env` on one laptop. Share the filled file over a private channel, never
   through the repo.

## Lanes

Four lanes, one person each. The first two build the pitch.

**Before: API** (Elasticsearch)
1. Create an Elastic Cloud serverless Elasticsearch project. Copy the endpoint and an API key into `.env`.
2. In Dev Tools run `GET _inference`. Put the ELSER endpoint id in `ELSER_ID`. If there is none, leave it empty and the app runs on keyword search only.
3. `make dev`, then `make seed`. Check `GET /api/matches` returns five people with reasons.
4. Build B (crews), then C (waves), then D (crowd board), exactly as specified in `PRE_CONFERENCE.md` and `API.md`. Write the listed tests first. One pull request each.
5. Every time `api/hallway/models.py` changes, run `make types` and commit the result.
6. After B and after C merge, the mappings have changed: delete the three `hallway-*` indices and reseed.
7. Warm ELSER before the demo: register one throwaway person ten minutes ahead.

**Before: Web**
1. `make dev`, open http://localhost:5173, and click through every page with seed data. Fix what is broken. This has never been done.
2. Build A (the "Before you arrive" page, new copy, navigation order). It needs no new API, so start right away.
3. Add the crew section, the wave button and the crowd page as each API lands. Until then, build against the shapes in `API.md`.
4. Keep the accessibility basics on every new control: a label, keyboard focus, enough contrast.

**Cluster** (Kubernetes, Radar, Dash0)
1. Image: `make image`, or merge to `main` and let CI push it. Make the package public in GitHub (Packages, Package settings, Change visibility). No time for that? `make image-ttl` pushes to an anonymous registry and prints the reference.
2. `make secrets`, `make deploy`, `make url`. Open the URL on a phone over cellular data.
3. Connect Radar's MCP to your coding agent. Use Radar to watch every rollout from now on, and screenshot it.
4. Put the Dash0 OTLP endpoint and auth token in `.env`, `make secrets`, redeploy. Check that traces arrive. Install the Dash0 Kubernetes operator from their onboarding page for pod logs and cluster metrics.
5. For browser monitoring set `DASH0_RUM_URL` and `DASH0_RUM_TOKEN`. Use a token limited to ingest: it is sent to every browser.
6. Build the "Hallway" dashboard. Top row is the **pre-conference funnel**: registered, waved, mutual, met in person. Below it: room occupancy by room, new suggested pairs, p95 of `GET /api/matches`, error rate. Add an SLO: matches p95 under 800 ms.
7. After 3:30: `make oom-demo`, watch the pod get OOMKilled in Radar, run the Radar AI investigation, save what it said in `docs/investigations/`, `make oom-fix`.
8. Then slow mode (command in `docs/DEMO.md`). Ask Agent0 why matches are slow. It should land on the `match.query` span. Save the conversation in `docs/investigations/`.

**Story** (Gitar, demo, submission)
1. Every change from now on is a small PR. Reply to Gitar's comments in the PR. Screenshot the good ones.
2. Watch for real CI failures. The pre-conference features change the models, so someone will forget `make types` and the `types` job will fail for real. Let Gitar diagnose and fix it, and write it up. A real failure beats the staged one in `docs/DEMO.md`. Only stage one if none has happened by 3:30.
3. Add the two seed targets from part A: `make seed-before` and `make seed-live`.
4. Fill in the README: screenshots, the status column, AI disclosure, team names.
5. At 4:30 run `make seed-before` on the cluster. Print QR codes after that, not before.
6. Rehearse the three minutes twice with a timer. Submit by 5:15, not 5:30.

## Timeline

| Time | Goal |
|---|---|
| now to 1:45 | Baseline. App runs locally with seed data. First PR open and reviewed by Gitar. Image built, deployed, public URL works on a phone. A started. |
| 1:45 to 3:30 | Pre-conference build: A merged, then B, then C, then D. Traces in Dash0. Radar connected. Dashboard started. |
| **3:30** | **Cut line.** Unmerged features are dropped. Use the fallback lines in the demo script. |
| 3:30 to 4:15 | The incidents, each written up. Funnel panel and SLO finished. E only if everything else is done. |
| 4:15 to 4:30 | Polish only. Feature freeze at 4:30. |
| 4:30 to 5:15 | `make seed-before`, print, rehearse twice, submit. |

The 2 PM panel costs time. Decide now who keeps building through it.

## If something is on fire

| Symptom | Do this |
|---|---|
| Matches are empty | `curl <url>/healthz`. If `es` is `red`, check `ES_URL` and the API key. If green, reseed. |
| ELSER errors on register | Set `ELSER_ID` to empty, delete the `hallway-*` indices, redeploy, reseed. |
| Nobody has a crew after B merges | The mapping is stale. Delete the `hallway-*` indices, reseed, then `make matcher-now`. |
| CI `types` job fails | `make types`, commit `web/src/api/schema.d.ts`. Or let Gitar do it and screenshot it. |
| Tunnel URL does not load | `kubectl -n hallway rollout restart deploy/hallway-tunnel`, then `make url`. The URL changes. Last resort: `kubectl port-forward svc/hallway 8000` and demo from the laptop. |
| Image will not pull | `make image-ttl`, then `make deploy IMAGE=<printed ref>`. |
| A pre-conference feature is half done at 3:30 | Close the PR. Do not merge half a feature. Use the fallback line. |
| OpenAI is down | Nothing to do. Icebreakers fall back to templates. |
| Venue Wi-Fi is down | Phone hotspot for the laptop. Attendee phones on cellular still reach the tunnel. |
