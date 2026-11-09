# Hallway API contract (v3)

One FastAPI process serves `/api/*`, `/healthz`, and the built web app at `/`.
All JSON. All timestamps UTC ISO-8601. Source of truth for shapes: `api/hallway/models.py`.

## Identity

No accounts. `POST /api/attendees` sets the cookie `hallway_session` (HttpOnly, SameSite=Lax, 7 days).
The cookie value is `<attendee id>.<secret>`. The secret never appears in any response or QR code,
so knowing someone's public id (it is in their QR) does not let you act as them.
"Me" endpoints return 401 without a valid cookie.

## Shapes

```ts
type Comfort = "open" | "small_groups" | "one_on_one";

type RelationKind = "met" | "planned" | "invited_you" | "you_invited" | "suggested";

interface AttendeeIn {            // POST /api/attendees body
  name: string;                   // 1..80 chars, required
  working_on: string;             // required, <= 500
  asks: string;                   // "what I need", may be ""
  offers: string;                 // "what I can give", may be ""
  fun_fact?: string;              // default ""
  tags?: string[];                // default [], lowercased by the server, max 10
  groups?: string[];              // default [], max 5
  comfort?: Comfort;              // default "open"
  on_graph?: boolean;             // opt-in, default false: show me, my plans and my meetings on /api/graph
  show_groups?: boolean;          // opt-in, default false: also show my communities there
}

interface Attendee {              // public profile
  id: string; name: string; working_on: string; asks: string; offers: string;
  fun_fact: string; tags: string[]; groups: string[]; comfort: Comfort;
}

interface Me extends Attendee { recovery_code: string; on_graph: boolean; show_groups: boolean; }

// PATCH /api/me body. Every field is optional: send only what should change. A field left
// out (or null) keeps its value. These are the only editable fields; any other field
// (id, name, recovery_code, ...) is a 422. Text and tags are cleaned as in AttendeeIn.
interface MeUpdate {
  working_on?: string;            // 1..500 chars after trimming
  asks?: string;                  // <= 500, "" clears it
  offers?: string;                // <= 500, "" clears it
  fun_fact?: string;              // <= 300
  tags?: string[];                // max 10, lowercased by the server
  groups?: string[];              // max 5
  comfort?: Comfort;
  on_graph?: boolean;
  show_groups?: boolean;
}

interface Match { attendee: Attendee; score: number; reason: string; icebreaker: string;
                  is_reciprocal: boolean; }   // works both ways, see "Matches" below

interface Edge { id: string; source: string; target: string;
                 kind: "connected" | "planned" | "suggested";
                 reason: string; created_at: string;
                 planned: boolean; }              // true when the two had agreed to meet before they met

interface ConnectResult { edge: Edge; created: boolean; other: Attendee; }

// groups is [] unless the person chose show_groups. There is no connection count: it is not a score.
interface GraphNode { id: string; name: string; groups: string[]; tags: string[]; }
interface GraphLink { source: string; target: string; kind: "connected" | "planned" | "suggested"; reason: string; }
interface Graph { nodes: GraphNode[]; links: GraphLink[]; }   // never contains a pending invitation

// My own view. `via` lists people I have met who could introduce us, nearest first (at most two).
interface Relationship { attendee: Attendee; kind: RelationKind; reason: string; via: PathStep[]; }
interface MyGraph { relationships: Relationship[]; }
interface InvitationResult { kind: "you_invited" | "planned"; other: Attendee; }

interface PathStep { id: string; name: string; }
interface Path { path: PathStep[]; }          // [] when no chain of connected edges exists

interface Room { room: string; count: number; people: PathStep[]; }   // people: up to 8

interface Recap { connections: Attendee[]; groups_bridged: number; nudges: string[]; }

interface CommunityIn { name: string; description: string; luma_url: string; }
interface Community extends CommunityIn { id: string; }

interface Config { rooms: string[]; chaos_enabled: boolean;
                   rum: { url: string; token: string } | null; }

// Arrival groups (working plan step 3). Pending suggestions and declines are never
// returned to anyone; `members` lists only people who accepted.
type CrewStatus = "none" | "suggested" | "member";
interface Meeting { place: string; starts_at: string;   // ISO 8601 with UTC offset
                    timezone: string; set_by: string; }   // IANA zone, e.g. "America/Denver"
interface Crew { id: string; members: Attendee[]; seats_taken: number;  // companions count
                 limit: number;    // smallest comfort limit: one_on_one 2, small_groups 4, open 5
                 why: string; meeting: Meeting | null; }  // null until a member sets it
interface CrewOut { status: CrewStatus; crew: Crew | null; bringing_companion: boolean; }

// Organizer board. Counts only: no name, id, free text or affiliation. A topic or a
// comfort row that describes fewer than three people is left out.
interface Topic { topic: string; asking: number; offering: number; }  // widest gap (asking - offering) first, at most 15
interface Count { key: string; count: number; }
interface Crowd { registered: number;
                  in_groups: number;            // people who accepted an arrival group
                  groups: number; groups_with_meeting: number;
                  invitations: number;          // sent, not yet answered
                  plans: number; meetings: number;  // pairs
                  checked_in: number;           // Hallway room check-ins, not Luma event check-in
                  topics: Topic[]; comfort: Count[]; }
```

## Endpoints

| Method | Path | Auth | Body | Returns | Errors |
|---|---|---|---|---|---|
| GET | `/healthz` | | | `{ok: true, es: "green" \| "red"}` | |
| GET | `/api/config` | | | `Config` | |
| POST | `/api/attendees` | | `AttendeeIn` | 201 `Me` + cookie | 422 |
| POST | `/api/communities` | cookie | `CommunityIn` | 201 `Community` | 401, 422 |
| GET | `/api/communities/{id}` | | | `Community` | 404 |
| GET | `/api/me` | cookie | | `Me` | 401 |
| PATCH | `/api/me` | cookie | `MeUpdate` | `Me` (my own profile after the edit) | 401, 422 unknown field or invalid value |
| POST | `/api/recover` | | `{code: string}` | `Me` + cookie | 404 |
| GET | `/api/attendees/{id}` | | | `Attendee` | 404 |
| GET | `/api/matches` | cookie | | `Match[]` (max 5), each with `is_reciprocal` | 401 |
| POST | `/api/edges` | cookie | `{to_id: string}` | `ConnectResult` | 400 self, 401, 404 |
| GET | `/api/graph` | | | `Graph` | |
| GET | `/api/graph/path?to={id}` | cookie | | `Path` (me → to) | 401 |
| GET | `/api/graph/me` | cookie | | `MyGraph` | 401 |
| POST | `/api/invitations` | cookie | `{to_id: string}` | `InvitationResult` | 400 self or already met, 401, 404, 429 after 20 waiting |
| POST | `/api/invitations/{id}/accept` | cookie | | `InvitationResult` | 401, 404 no invitation from them |
| DELETE | `/api/invitations/{id}` | cookie | | 204 (decline, take back, or cancel a plan) | 401, 404 |
| POST | `/api/checkins` | cookie | `{room: string}` | `Room` | 400 unknown room, 401 |
| GET | `/api/rooms` | | | `Room[]` (every configured room, even empty) | |
| GET | `/api/recap` | cookie | | `Recap` | 401 |
| GET | `/api/crew` | cookie | | `CrewOut`: my crew, else my pending suggestion, else none | 401 |
| POST | `/api/crew/suggest` | cookie | | `CrewOut` (no change if I already have a crew or suggestion) | 401 |
| POST | `/api/crew/accept` | cookie | `{companion?: boolean}` | `CrewOut` (`member`) | 401, 404 no suggestion, 409 full or already in a crew |
| POST | `/api/crew/decline` | cookie | | `CrewOut` (`none`); that crew is not suggested again | 401 |
| DELETE | `/api/crew` | cookie | | `CrewOut` (`none`); you are not reassigned | 401 |
| PUT | `/api/crew/meeting` | cookie | `{place, starts_at, timezone}` | `CrewOut` | 401, 403 not a member, 422 no offset, unknown zone, or an offset that is not the zone's offset at that time |
| GET | `/api/crowd` | | | `Crowd` | |
| GET | `/api/chaos` | | | `{mode: "off" \| "slow" \| "error"}` | |
| POST | `/api/chaos` | header `X-Admin-Token` | `{mode}` | `{mode}` | 403 |

Errors are `{"detail": "<message>"}`.

`PATCH /api/me` only ever changes the person in the session cookie. When `working_on`, `asks`,
`offers`, `tags` or `groups` change, matching uses the new text at once, and in the background
that person's `suggested` edges are deleted and written again, because a suggestion stores a
reason that quotes the old text. Suggestions other people had for them return on the next
matcher run. Invitations, plans and meetings are never touched by an edit.

## Matches

Every query in the match request is named, and Elasticsearch reports which names matched
each person. `reason` and `is_reciprocal` are both read from that report, never guessed.
`is_reciprocal` is true when both `asks_to_offers` (my asks against their offers) and
`offers_to_asks` (my offers against their asks) matched. It is the same evidence as `reason`,
and as loose: without ELSER one shared word is enough for a query to match. Filler
words ("and", "with", "need", ...) are removed from the word query first, so they never
count as a match.

## The four relationships

They are stored as edges of different kinds and are never merged.

| Kind | Meaning | Who can see it |
|---|---|---|
| `suggested` | The matcher thinks two people should meet. Nobody agreed to anything. | Public, between people on the graph. |
| `invited` | One person asked to meet another. | Only those two, in `/api/graph/me`. Never in `/api/graph`. |
| `planned` | The invitation was accepted, or both invited each other. | Public, between people on the graph. |
| `connected` | One scanned the other's code. They met. | Public, between people on the graph. |

Community membership is not an edge. The graph page draws it from `GraphNode.groups`.
Meeting someone removes the suggestion, invitation and plan for that pair, and the new
`connected` edge records `planned: true` if a plan existed. Introducers in `via` are found
only through meetings between people who are on the public graph.

## Web routes (served by the same process, SPA fallback)

`/` register (or redirect to `/five` if already registered), `/five`, `/me` (QR, recovery code,
edit what you need and offer; `/me#edit` opens at the form), `/connect/:id`,
`/recover`, `/graph` (`?kiosk=1` full screen, `?focus=<id>`), `/rooms` (`?room=<name>` checks in), `/recap`.
A profile QR encodes `<origin>/connect/<my id>`.

`/communities/new` creates an invitation for a registered attendee.
`/communities/:id` is its shareable public page. Registration happens on Luma;
Hallway does not verify an RSVP or enroll a community member in this flow.

## Planned: pre-conference additions (v4)

Not built yet. Build against these shapes. The design and the order are in
[`PRE_CONFERENCE.md`](PRE_CONFERENCE.md). Move each block up into the sections above when it merges.

```ts
// B. Crews: built as arrival groups; see Shapes and Endpoints above.

// C. Waves: built as invitations. See "The four relationships" above. Still planned:
interface Recap { /* existing fields */ planned: number; planned_met: number; still_to_meet: Attendee[]; }

// D. Crowd board: built as the organizer board; see Shapes and Endpoints above.

// E. Phase
type Phase = "before" | "live" | "after";
interface Config { /* existing fields */ phase: Phase; }
```

| Method | Path | Auth | Body | Returns | Errors |
|---|---|---|---|---|---|
| POST | `/api/phase` | header `X-Admin-Token` | `{phase}` | `{phase}` | 403 |

Web routes built: `/plan` (replaces `/five`, which redirects) and `/crowd`.
