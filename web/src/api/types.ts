// Hand-written to match docs/API.md exactly. If a shape changes there, change it here.

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
  on_graph?: boolean;
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
}

export interface Match {
  attendee: Attendee;
  score: number;
  reason: string;
  icebreaker: string;
}

export type EdgeKind = "connected" | "suggested";

export interface Edge {
  id: string;
  source: string;
  target: string;
  kind: EdgeKind;
  reason: string;
  created_at: string;
}

export interface ConnectResult {
  edge: Edge;
  created: boolean;
  other: Attendee;
}

export interface GraphNode {
  id: string;
  name: string;
  groups: string[];
  tags: string[];
  degree: number;
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
