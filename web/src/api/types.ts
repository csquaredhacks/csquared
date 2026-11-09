// Hand-written to match docs/API.md exactly. If a shape changes there, change it here.
import type { components } from "./schema";

/** Arrival groups come straight from the generated schema, so they cannot drift. */
export type CrewOut = components["schemas"]["CrewOut"];
/** One of my own goals. Private to me. */
export type Goal = components["schemas"]["Goal"];
export type Goals = components["schemas"]["Goals"];
/** The organizer board: counts only. */
export type Crowd = components["schemas"]["Crowd"];

export type Comfort = "open" | "small_groups" | "one_on_one";

/** Body of POST /api/attendees */
export interface AttendeeIn {
  name: string;
  working_on: string;
  asks: string;
  offers: string;
  fun_fact?: string;
  tags?: string[];
  groups?: string[];
  comfort?: Comfort;
  /** Opt-in: show me, my plans and my meetings on the public graph. Default false. */
  on_graph?: boolean;
  /** Opt-in, separate: also show my communities there. Default false. */
  show_groups?: boolean;
}

/** Public profile */
export interface Attendee {
  id: string;
  name: string;
  working_on: string;
  asks: string;
  offers: string;
  fun_fact: string;
  tags: string[];
  groups: string[];
  comfort: Comfort;
}

export interface Me extends Attendee {
  recovery_code: string;
  on_graph: boolean;
  show_groups: boolean;
}

export interface Match {
  attendee: Attendee;
  score: number;
  reason: string;
  icebreaker: string;
  /** they offer something I asked for AND I offer something they asked for */
  is_reciprocal: boolean;
}

/** Link kinds on the public graph. A pending invitation is never public. */
export type EdgeKind = "connected" | "planned" | "suggested";

/** What one person is to me, in my own view of the graph. */
export type RelationKind = "met" | "planned" | "invited_you" | "you_invited" | "suggested";

export interface Edge {
  id: string;
  source: string;
  target: string;
  kind: EdgeKind;
  reason: string;
  created_at: string;
  /** true when the two had agreed to meet before they met */
  planned: boolean;
}

export interface ConnectResult {
  edge: Edge;
  created: boolean;
  other: Attendee;
}

export interface GraphNode {
  id: string;
  name: string;
  /** empty unless the person chose to show their communities */
  groups: string[];
  tags: string[];
}

export interface GraphLink {
  source: string;
  target: string;
  kind: EdgeKind;
  reason: string;
}

export interface Graph {
  nodes: GraphNode[];
  links: GraphLink[];
}

export interface PathStep {
  id: string;
  name: string;
}

export interface Relationship {
  attendee: Attendee;
  kind: RelationKind;
  /** why this person is relevant to me, from the matching evidence */
  reason: string;
  /** people I have met who could introduce us, nearest first */
  via: PathStep[];
}

export interface MyGraph {
  relationships: Relationship[];
}

export interface InvitationResult {
  kind: "you_invited" | "planned";
  other: Attendee;
}

/** path is [] when no chain of connected edges exists */
export interface Path {
  path: PathStep[];
}

/** people holds up to 8 names */
export interface Room {
  room: string;
  count: number;
  people: PathStep[];
}

export interface Recap {
  connections: Attendee[];
  groups_bridged: number;
  nudges: string[];
}

export interface Config {
  rooms: string[];
  chaos_enabled: boolean;
  rum: { url: string; token: string } | null;
}

export interface Health {
  ok: true;
  es: "green" | "red";
}

export type ChaosMode = "off" | "slow" | "error";

export interface Chaos {
  mode: ChaosMode;
}
