import type {
  Attendee, AttendeeIn, Chaos, ChaosMode, Config, ConnectResult, CrewOut, Crowd, Goal, Goals, Graph, Health,
  InvitationResult, Match, Me, MyGraph, Path, Recap, Room,
} from "./types";
import type { components } from "./schema";

export type Community = components["schemas"]["Community"];
type CommunityIn = components["schemas"]["CommunityIn"];
type CommunityUpdate = components["schemas"]["CommunityUpdate"];

/** Thrown for every non-2xx response. `detail` is the server's message. */
export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

/** Turns anything thrown into a sentence we can show the user. */
export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.detail;
  return "Could not reach Hallway. Check your connection and try again.";
}

async function request<T>(method: string, path: string, body?: unknown, headers?: Record<string, string>): Promise<T> {
  const response = await fetch(path, {
    method,
    credentials: "same-origin", // sends the hallway_session cookie
    headers: { ...(body === undefined ? {} : { "Content-Type": "application/json" }), ...headers },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const data = await response.json();
      if (typeof data.detail === "string") detail = data.detail;
      // FastAPI validation errors (422) send a list of { msg } objects instead of a string.
      else if (Array.isArray(data.detail)) detail = data.detail.map((d: { msg: string }) => d.msg).join(". ");
    } catch {
      // body was not JSON; keep the generic message
    }
    throw new ApiError(response.status, detail);
  }
  if (response.status === 204) return undefined as T; // no body to read
  return (await response.json()) as T;
}

export const getHealth = () => request<Health>("GET", "/healthz");
export const getConfig = () => request<Config>("GET", "/api/config");
export const createCommunity = (body: CommunityIn) => request<Community>("POST", "/api/communities", body);
export const getCommunity = (id: string) => request<Community>("GET", `/api/communities/${encodeURIComponent(id)}`);
/** Organizer only. Fields left out keep their value. */
export const updateCommunity = (id: string, changes: CommunityUpdate) =>
  request<Community>("PATCH", `/api/communities/${encodeURIComponent(id)}`, changes);
// Membership is always my own choice: the server takes "me" from the session cookie.
export const joinCommunity = (id: string) =>
  request<Community>("POST", `/api/communities/${encodeURIComponent(id)}/members`);
export const leaveCommunity = (id: string) =>
  request<Community>("DELETE", `/api/communities/${encodeURIComponent(id)}/members`);
/** The communities I joined and the ones I created. */
export const getMyCommunities = () => request<Community[]>("GET", "/api/me/communities");
export const createAttendee = (body: AttendeeIn) => request<Me>("POST", "/api/attendees", body);
export const getMe = () => request<Me>("GET", "/api/me");
export const recover = (code: string) => request<Me>("POST", "/api/recover", { code });
export const getAttendee = (id: string) => request<Attendee>("GET", `/api/attendees/${encodeURIComponent(id)}`);
export const getMatches = () => request<Match[]>("GET", "/api/matches");
export const connect = (toId: string) => request<ConnectResult>("POST", "/api/edges", { to_id: toId });
export const getGraph = () => request<Graph>("GET", "/api/graph");
export const getMyGraph = () => request<MyGraph>("GET", "/api/graph/me");
export const updateMe = (changes: { on_graph?: boolean; show_groups?: boolean }) =>
  request<Me>("PATCH", "/api/me", changes);
export const invite = (toId: string) => request<InvitationResult>("POST", "/api/invitations", { to_id: toId });
export const acceptInvitation = (fromId: string) =>
  request<InvitationResult>("POST", `/api/invitations/${encodeURIComponent(fromId)}/accept`);
/** Decline theirs, take back mine, or cancel our plan. */
export const withdrawInvitation = (otherId: string) =>
  request<void>("DELETE", `/api/invitations/${encodeURIComponent(otherId)}`);
// Arrival groups. Every call returns where I stand now: none, suggested or member.
export const getCrew = () => request<CrewOut>("GET", "/api/crew");
export const suggestCrew = () => request<CrewOut>("POST", "/api/crew/suggest");
export const acceptCrew = (companion: boolean) => request<CrewOut>("POST", "/api/crew/accept", { companion });
export const declineCrew = () => request<CrewOut>("POST", "/api/crew/decline");
export const leaveCrew = () => request<CrewOut>("DELETE", "/api/crew");
/** `startsAt` is ISO 8601 with the UTC offset of `timezone` (an IANA name). */
export const setCrewMeeting = (place: string, startsAt: string, timezone: string) =>
  request<CrewOut>("PUT", "/api/crew/meeting", { place, starts_at: startsAt, timezone });
export const getPath = (toId: string) => request<Path>("GET", `/api/graph/path?to=${encodeURIComponent(toId)}`);
export const checkIn = (room: string) => request<Room>("POST", "/api/checkins", { room });
export const getRooms = () => request<Room[]>("GET", "/api/rooms");
/** Leave my group and ask for another. I still have to accept the new one. */
export const replaceCrew = () => request<CrewOut>("POST", "/api/crew/replace");
export const getGoals = () => request<Goals>("GET", "/api/goals");
export const setGoals = (goals: Goal[]) => request<Goals>("PUT", "/api/goals", { goals });
export const getCrowd = () => request<Crowd>("GET", "/api/crowd");
export const getRecap = () => request<Recap>("GET", "/api/recap");
export const getChaos = () => request<Chaos>("GET", "/api/chaos");
export const setChaos = (mode: ChaosMode, adminToken: string) =>
  request<Chaos>("POST", "/api/chaos", { mode }, { "X-Admin-Token": adminToken });
