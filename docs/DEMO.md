# Demo script (three minutes)

The story has two acts. Act one is the week before the conference and takes most of the
time, because that is the product. Act two is the day itself, and it is the payoff.

**Before you walk up:** cluster seeded with `make seed-before` only, phase set to `before`,
chaos off. Kiosk view on the projector (`<url>/graph?kiosk=1`). Dash0 dashboard in a second
tab, Radar in a third, the crowd board in a fourth. A terminal ready with `make seed-live`.

| Time | Say | Do | If the feature was cut |
|---|---|---|---|
| 0:00 | "It is the Thursday before a conference. You have a ticket and you know nobody. Your confirmation email has one link. Scan it." | Point at the QR on the screen. Judges register on their phones. | |
| 0:25 | "It is still Thursday. You already have five people to meet, and each one comes with a reason that is true." | Phone: Before you arrive. Read one reason and one icebreaker. | |
| 0:40 | "And you have a crew. Four people, Coffee Bar, thirty minutes before the keynote. You asked for small groups, so you got one. Nobody walks in alone." | Scroll to the crew section. | Skip this line. |
| 0:55 | "Tap wave. No messages, no inbox, nothing to moderate. If they wave back, it is a plan." | Wave at someone. Show a mutual wave. | "You know who to look for on Monday." |
| 1:10 | "That reason is not written by an LLM. One Elasticsearch query crosses what I need with what you offer, keyword and semantic, fused with RRF, and Elasticsearch tells us which part matched. The same query builds the crews." | Show `matching.py` for ten seconds. | Drop the last sentence. |
| 1:25 | "Organizers get this days ahead. Fourteen people want help with eBPF. Two offer it. That is a session you can still add to the schedule." | Crowd board tab. | "Organizers see the graph take shape before doors open." Show the kiosk. |
| 1:45 | "Now it is Monday." | Switch phase to live. Run `make seed-live`. On the kiosk, dotted plans turn into solid lines. Scan a teammate's QR. | Without E, just run `make seed-live`. |
| 2:05 | "One image, one Helm release, one Secret, on Kubernetes. Radar is how we watched it all day." | Radar tab: the three workloads. | |
| 2:20 | "Everything is traced. This funnel is the product in four numbers: registered, waved, mutual, met in person. And when we made matching slow, Agent0 found the span." | Dash0: funnel panel, then the saved investigation. | Without C, show occupancy and latency instead of the funnel. |
| 2:40 | "These are the problems we did not plant, and every PR today was reviewed by Gitar against our own rules." | `docs/investigations/`, then one Gitar review. | |
| 2:55 | "Sixty people walked in already knowing who to find. Nobody at this conference goes solo. Thank you." | Kiosk view again. | |

Rehearse the switch at 1:45 more than anything else. It is the moment the room sees the
plans become real.

## Commands

Seed the week before, then the day itself:

```bash
make seed-before API=$URL
```

```bash
make seed-live API=$URL
```

Switch the phase (after feature E is merged):

```bash
curl -X POST "$URL/api/phase" -H "X-Admin-Token: $ADMIN_TOKEN" -H "content-type: application/json" -d '{"phase":"live"}'
```

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

CI break (Gitar). Prefer a real one: the pre-conference features change the models, and a
forgotten `make types` fails the `types` job on its own. If none has happened by 3:30,
stage one: on a branch, rename a field in `api/hallway/models.py` (for example
`Match.icebreaker` to `Match.opener`, and the one place in `routes/matches.py` that sets it)
and push without running `make types`. Let Gitar diagnose and apply the fix. Then decide as
a team whether to keep the rename.
