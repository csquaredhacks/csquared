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

interface AttendeeIn {            // POST /api/attendees body
  name: string;                   // 1..80 chars, required
  working_on: string;             // required, <= 500
  asks: string;                   // "what I need", may be ""
  offers: string;                 // "what I can give", may be ""
  fun_fact?: string;              // default ""
  tags?: string[];                // default [], lowercased by the server, max 10
  groups?: string[];              // default [], max 5
  comfort?: Comfort;              // default "open"
  on_graph?: boolean;             // default true; false hides you from /api/graph
}

interface Attendee {              // public profile
  id: string; name: string; working_on: string; asks: string; offers: string;
  fun_fact: string; tags: string[]; groups: string[]; comfort: Comfort;
}

interface Me extends Attendee { recovery_code: string; on_graph: boolean; }

interface Match { attendee: Attendee; score: number; reason: string; icebreaker: string; }

interface Edge { id: string; source: string; target: string; kind: "connected" | "suggested";
                 reason: string; created_at: string; }

interface ConnectResult { edge: Edge; created: boolean; other: Attendee; }

interface GraphNode { id: string; name: string; groups: string[]; tags: string[]; degree: number; }
interface GraphLink { source: string; target: string; kind: "connected" | "suggested"; reason: string; }
interface Graph { nodes: GraphNode[]; links: GraphLink[]; }

interface PathStep { id: string; name: string; }
interface Path { path: PathStep[]; }          // [] when no chain of connected edges exists

interface Room { room: string; count: number; people: PathStep[]; }   // people: up to 8

interface Recap { connections: Attendee[]; groups_bridged: number; nudges: string[]; }

interface CommunityIn { name: string; description: string; luma_url: string; }
interface Community extends CommunityIn { id: string; }

interface Config { rooms: string[]; chaos_enabled: boolean;
                   rum: { url: string; token: string } | null; }
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
| POST | `/api/recover` | | `{code: string}` | `Me` + cookie | 404 |
| GET | `/api/attendees/{id}` | | | `Attendee` | 404 |
| GET | `/api/matches` | cookie | | `Match[]` (max 5) | 401 |
| POST | `/api/edges` | cookie | `{to_id: string}` | `ConnectResult` | 400 self, 401, 404 |
| GET | `/api/graph` | | | `Graph` | |
| GET | `/api/graph/path?to={id}` | cookie | | `Path` (me → to) | 401 |
| POST | `/api/checkins` | cookie | `{room: string}` | `Room` | 400 unknown room, 401 |
| GET | `/api/rooms` | | | `Room[]` (every configured room, even empty) | |
| GET | `/api/recap` | cookie | | `Recap` | 401 |
| GET | `/api/chaos` | | | `{mode: "off" \| "slow" \| "error"}` | |
| POST | `/api/chaos` | header `X-Admin-Token` | `{mode}` | `{mode}` | 403 |

Errors are `{"detail": "<message>"}`.

## Web routes (served by the same process, SPA fallback)

`/` register (or redirect to `/five` if already registered), `/five`, `/me`, `/connect/:id`,
`/recover`, `/graph` (`?kiosk=1` full screen, `?focus=<id>`), `/rooms` (`?room=<name>` checks in), `/recap`.
A profile QR encodes `<origin>/connect/<my id>`.

`/communities/new` creates an invitation for a registered attendee.
`/communities/:id` is its shareable public page. Registration happens on Luma;
Hallway does not verify an RSVP or enroll a community member in this flow.

## Planned: pre-conference additions (v4)

Not built yet. Build against these shapes. The design and the order are in
[`PRE_CONFERENCE.md`](PRE_CONFERENCE.md). Move each block up into the sections above when it merges.

```ts
// B. Crews
interface Crew { id: string; members: Attendee[]; room: string; when: string; why: string; }
interface CrewOut { crew: Crew | null; }       // null: not assigned yet, or opted out

// C. Waves
type WaveState = "none" | "sent" | "received" | "mutual";
interface Match { /* existing fields */ wave: WaveState; }
interface WaveResult { mutual: boolean; other: Attendee; }
interface Waves { mutual: Attendee[]; incoming: Attendee[]; outgoing: Attendee[]; }
interface Edge { /* existing fields */ planned: boolean; }            // true when a wave came first
interface GraphLink { /* existing */ kind: "connected" | "suggested" | "planned"; }
interface Recap { /* existing fields */ planned: number; planned_met: number; still_to_meet: Attendee[]; }

// D. Crowd board
interface Topic { topic: string; asking: number; offering: number; }  // sorted by asking - offering, largest first
interface Count { key: string; count: number; }
interface Crowd { registered: number; with_crew: number; waves: number;
                  topics: Topic[]; comfort: Count[]; groups: Count[]; }

// E. Phase
type Phase = "before" | "live" | "after";
interface Config { /* existing fields */ phase: Phase; }
```

| Method | Path | Auth | Body | Returns | Errors |
|---|---|---|---|---|---|
| GET | `/api/crew` | cookie | | `CrewOut` | 401 |
| DELETE | `/api/crew` | cookie | | `CrewOut` (always `null`; you are not reassigned) | 401 |
| POST | `/api/waves` | cookie | `{to_id: string}` | `WaveResult` | 400 self or already connected, 401, 404, 429 after 20 |
| GET | `/api/waves` | cookie | | `Waves` | 401 |
| GET | `/api/crowd` | | | `Crowd` | |
| POST | `/api/phase` | header `X-Admin-Token` | `{phase}` | `{phase}` | 403 |

New web routes: `/plan` (replaces `/five`, which redirects), `/crowd` (`?kiosk=1` full screen).
