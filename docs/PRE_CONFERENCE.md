# Pre-conference first (plan v4)

> **Historical plan.** Read [the working plan](WORKING_PLAN.md) for current scope
> and build order, including community signup, Luma, accessibility, and accepted
> arrival plans. Its consent, capacity, meeting-location, and migration requirements
> replace conflicting shortcuts below. This document is retained for design history.

**The change:** Hallway's main promise now happens *before* the conference, not during it.
You get the link in your ticket email. By the time you walk in, you already know who to
find, you have a few people to walk in with, and the organizers already know what the
crowd needs. The live graph and room map stay, but they are now the payoff, not the pitch.

**Why this is the stronger product**

- The hard part of a conference for a first-timer is the first ten minutes. Anything that
  starts at the door starts too late.
- Every other team will demo something that happens during the event. We are the ones who
  fixed the week before.
- It gives organizers something they can act on while there is still time to act:
  what to schedule, which rooms to reserve, who is coming alone.
- The data is better. People write careful asks and offers at home. They do not at a
  registration desk.

## The journey

| When | Attendee | Organizer |
|---|---|---|
| **Before** (the week before) | Register in a minute. Meet your five. Wave at the ones you want to meet. Get a crew to walk in with. Pre-connect with people you already know by sending them your link. | Crowd board: what people ask for against what they offer, who prefers small groups, how many are still without a crew. |
| **During** | Scan a QR to turn a plan into a real connection. Check in to rooms. | Live graph on the venue screen. Room map. |
| **After** | Recap: who you planned to meet, who you met, who you missed. | The same numbers, as a funnel in Dash0. |

## What already exists and is pre-conference today

These need no new API. They only need to be presented as the "before" experience.

| Feature | Where | Why it is a pre-conference feature |
|---|---|---|
| One-form registration, no account | `/` | It works from a link in an email, days ahead, on any device. |
| Your five, with a true reason and an icebreaker | `/five` | You can read it on the train to the venue. |
| Suggested links on the graph | matcher | The graph has shape before anyone has met. |
| Recovery code | `/recover` | You register on a laptop at home and open it on your phone at the venue. |
| Your link `/connect/<id>` | `/me` | Send it to a colleague who is also going. They are connected to you before day one. |
| Comfort preference | registration form | Collected early, so crews and rooms can respect it. |

## Build order

Do them in this order. Each is its own small pull request, so Gitar reviews each one.
**Cut line: 3:30 PM.** Anything not merged by then is dropped, and the demo script has a
fallback line for it.

| # | Feature | API | Web | Rough time | Track it helps |
|---|---|---|---|---|---|
| A | Reframe: "Before you arrive" page, new copy, seed in two acts | none | yes | 30 min | all |
| B | Crews: a few people to walk in with | yes | yes | 75 min | overall, Merge Forward, Elasticsearch |
| C | Waves: "I want to meet you", private until mutual | yes | yes | 75 min | overall, Dash0 funnel |
| D | Crowd board for organizers | yes | yes | 60 min | Elasticsearch, overall |
| E | Phase switch: before, live, after | yes | yes | 30 min | demo |
| F | Sessions: talks for you, and who of your five is going | yes | yes | stretch | Elasticsearch |

### A. Reframe (no new API)

- Rename the Your Five page to **Before you arrive**. New route `/plan`. Keep `/five` as a redirect.
- The page is a short checklist. Each item is a section on the page:
  1. Meet your five.
  2. Meet your crew. Shows "coming soon" until B is merged.
  3. Already know someone who is going? Send them your link. Uses the existing `/connect/<id>`.
  4. Save your recovery code, so you can open Hallway on your phone at the venue.
- Registration headline: "Going to a conference? Meet your people before you get there."
- Navigation order becomes: Plan, Me, Graph, Rooms, Recap.
- Seed in two acts, so the demo can show the week before and the day itself:
  - `make seed-before` registers the 60 fictional attendees. No connections, no check-ins. With C merged, it also sends waves.
  - `make seed-live` adds connections and check-ins for the same people.
  - `seed/seed.py` gets a `--phase before|live|all` flag. `make seed` keeps doing both.

### B. Crews

*Nobody walks in alone.* Everyone gets a crew of two to five people and a place to meet.

Data: one new field on the attendee document, `crew_id` (keyword), and `crew_opt_out` (boolean).
No new index. A crew is "every attendee with the same `crew_id`".

One rule, in a new file `api/hallway/crews.py`, function `assign_crew(client, a)`:

1. If `a` has a crew or has opted out, stop.
2. Run the existing match query for `a`, size 10.
3. Walk the matches in order. Join the first one whose crew has room for you.
4. If none has room, take the first match with no crew and start a new crew with them.
5. If there is nobody, do nothing. The next run will try again.

"Room for you" respects comfort. A crew's limit is the smallest limit among its members:
`one_on_one` is 2, `small_groups` is 4, `open` is 5.

Where it runs: in the background right after registration, and in the matcher CronJob for
anyone still without a crew. Two people joining the same crew in the same second can make
it one too large. We accept that and say so.

The crew's meeting point is not stored. It is worked out from the crew id:
room = `ROOMS[int(crew_id, 16) % len(ROOMS)]`, time = the `CREW_MEET_WHEN` setting,
default "30 minutes before the opening keynote". The reason shown is the tags that at
least two members share, or "You are each other's best matches" when there are none.

Tests to write first: a second person joins the first person's crew; a `one_on_one` person
never ends up in a crew of three; a full crew is skipped; leaving a crew sticks.

After merging: the attendee mapping changed, so delete the three `hallway-*` indices and reseed.

### C. Waves

A wave is one tap on a person in your five. It says "I want to meet you" and nothing else.
There is no message text, so there is no inbox to moderate and no way to harass anyone.

- A wave is a directed edge. Kind `wave`, id `<from>><to>:wave`.
- The other person sees it on their plan page. Nobody else ever does.
- When both people have waved, it is **mutual**. Only mutual waves appear on the public
  graph, as a dotted "planned" link.
- Scanning each other's QR at the event deletes the waves and marks the new connection `planned: true`.
- At most 20 outgoing waves per person.
- Recap gains: how many meetings you planned, how many happened, and who you still have to find.

Tests to write first: a one-sided wave is in neither `/api/graph` nor the other person's
public profile; two waves make it mutual; connecting clears the waves and sets `planned`;
the twenty-first wave is refused.

### D. Crowd board

A page for organizers, useful days before doors open: `/crowd`.

- How many people have registered, how many have a crew, how many waves were sent.
- **Asked for against offered, per topic.** The topics are the 15 most used tags. For each
  one we count the attendees whose asks mention it and the attendees whose offers mention
  it. The biggest gaps are listed first. "Fourteen people want help with eBPF, two offer
  it" is a session an organizer can still schedule.
- Comfort breakdown, so the right number of quiet spaces is reserved.

It is two Elasticsearch requests with `size: 0`. The first is a `terms` aggregation on
`tags`. The second is one `filters` aggregation with two `match` filters per topic.
Only counts are returned, and a topic is shown only when at least three people are behind it.

### E. Phase switch

`Config` gains `phase`: `before`, `live` or `after`. It starts from the `EVENT_PHASE`
setting and can be changed with `POST /api/phase`, which needs the admin token, exactly
like the chaos switch. The web app uses it for three things only: which page is home,
the order of the navigation, and the kiosk headline. In `before` the kiosk shows
"N people registered, M plans made".

## What the sponsor tools get out of this

| Tool | New material |
|---|---|
| Elasticsearch | The match query now also builds crews. The crowd board is aggregations over the same index. Search, graph and analytics from one datastore. |
| Dash0 | A funnel panel: registered, waved, mutual, met in person. New counters: `hallway.edges.total{kind="wave"}`, `hallway.crew.joins`, `hallway.planned.met`. This is product observability, not just latency. |
| Gitar | Three to five more small PRs to review, and a new rule to add to `docs/GITAR_RULES.md` in the waves PR: private intent stays private. A one-sided wave is visible only to the two people involved, and `/api/crowd` returns counts only. |
| Radar | Nothing new. The cluster story is unchanged. |
| Merge Forward | Crews respect comfort. Waves carry no text. One-sided interest is never public. |

## Limits to say out loud

- Crew assignment is greedy. It is not the best possible grouping, and a late registrant can end up in a pair.
- The phase is held in memory, like chaos mode, so the API runs as one replica.
- The crowd board counts words, not meaning, unless semantic search is on.
- Nothing sends email. "The link in your ticket email" is how an organizer would share it. We share it with a QR code.
