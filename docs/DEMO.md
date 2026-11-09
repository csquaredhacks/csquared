# Demo script (three minutes)

**Before you walk up:** kiosk view open on the projector (`<url>/graph?kiosk=1`), Dash0
dashboard in a second tab, Radar in a third, cluster seeded, chaos off.

| Time | Say | Do |
|---|---|---|
| 0:00 | "Conferences are great if you already know people. Hallway is for everyone else. Scan this." | Point at the QR on the kiosk screen. Judges register on their phones. |
| 0:30 | "One form. No account, no app. You already have five people to meet, and it tells you why." | Show Your Five on a phone. Read one reason and one icebreaker. |
| 1:00 | "That reason is not made up by an LLM. One Elasticsearch query cross-matches what I need against what you offer, BM25 and semantic, fused with RRF, and Elasticsearch tells us which part matched." | Show `matching.py` for ten seconds. |
| 1:20 | "Meet someone, scan their code." | Scan a teammate's QR. On the big screen the dashed line turns solid. |
| 1:40 | "One image, one Helm release, one Secret, running on Kubernetes. Radar is how we watched it all day." | Radar tab: the three workloads. |
| 2:00 | "Everything is traced. Earlier we made matching slow on purpose and asked Agent0 why." | Dash0: dashboard, then the saved investigation with the `match.query` span. |
| 2:25 | "And these are the problems we did not plant." | `docs/investigations/`: the real ones, with what Radar, Dash0 and Gitar each told you. |
| 2:45 | "Every PR today was reviewed by Gitar against our own rules. Nobody at this conference goes solo. Thank you." | Kiosk view again. |

## Commands for the planned incidents

Slow matches (Dash0). Replace the URL and token:

```bash
curl -X POST "$URL/api/chaos" -H "X-Admin-Token: $ADMIN_TOKEN" -H "content-type: application/json" -d '{"mode":"slow"}'
```

```bash
curl -X POST "$URL/api/chaos" -H "X-Admin-Token: $ADMIN_TOKEN" -H "content-type: application/json" -d '{"mode":"off"}'
```

Out of memory (Radar):

```bash
make oom-demo
```

```bash
make oom-fix
```

CI break (Gitar): on a branch, rename a field in `api/hallway/models.py` (for example
`Match.icebreaker` to `Match.opener`, and the one place in `routes/matches.py` that sets it)
and push without running `make types`. The `types` and `web` jobs fail. Let Gitar diagnose
and apply the fix. Then decide as a team whether to keep the rename.
