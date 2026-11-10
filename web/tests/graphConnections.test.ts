import { test } from "node:test";
import { strict as assert } from "node:assert";
import { chainTo, connection } from "../src/pages/graphConnections.ts";
import type {
  GraphLink,
  Me,
  GraphNode,
  Relationship,
} from "../src/api/types.ts";
const me = { id: "me", groups: ["SRE"], tags: ["tracing"] } as Me;
const person: GraphNode = { id: "them", name: "Them", groups: [], tags: [] };
const edge = (
  source: string,
  target: string,
  kind: GraphLink["kind"] = "connected",
): GraphLink => ({ source, target, kind, reason: "" });
test("shortest meeting chain excludes suggestions and handles cycles", () => {
  const links = [
    edge("me", "them", "suggested"),
    edge("me", "a"),
    edge("a", "b"),
    edge("b", "me"),
    edge("b", "them"),
  ];
  assert.deepEqual(chainTo("me", "them", links), ["me", "b", "them"]);
  assert.deepEqual(chainTo("me", "unknown", links), []);
});
test("shared community is common ground, not a meeting or plan", () => {
  const c = connection(me, { ...person, groups: ["SRE"] }, undefined, []);
  assert.equal(c.level, 1);
  assert.equal(c.title, "Common ground");
  assert.equal(
    connection(me, person, undefined, [edge("me", "them", "planned")]).level,
    0,
  );
});
test("incoming and outgoing invitations retain their direction", () => {
  for (const kind of ["invited_you", "you_invited"] as const) {
    const r = {
      kind,
      reason: "Shared interest in tracing",
      via: [],
      attendee: person,
    } as Relationship;
    const c = connection(me, person, r, []);
    assert.equal(c.level, 3);
    assert.match(
      c.title,
      kind === "invited_you" ? /^They invited/ : /^You invited/,
    );
    assert.ok(c.facts.includes(r.reason));
  }
});
test("confirmed direct meeting wins and absence of evidence stays unconnected", () => {
  assert.equal(
    connection(me, person, undefined, [edge("them", "me")]).level,
    4,
  );
  assert.equal(connection(me, person, undefined, []).level, 0);
});
