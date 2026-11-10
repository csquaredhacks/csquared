import type { GraphLink, GraphNode, Me, Relationship } from "../api/types";

// Only confirmed meetings form introduction chains. Suggestions and plans are not meetings.
export function chainTo(
  from: string,
  to: string,
  links: GraphLink[],
): string[] {
  const neighbours = new Map<string, string[]>();
  for (const l of links.filter((l) => l.kind === "connected")) {
    neighbours.set(l.source, [...(neighbours.get(l.source) ?? []), l.target]);
    neighbours.set(l.target, [...(neighbours.get(l.target) ?? []), l.source]);
  }
  const queue = [from],
    previous = new Map<string, string | null>([[from, null]]);
  for (let i = 0; i < queue.length; i++) {
    if (queue[i] === to) {
      const path: string[] = [];
      for (
        let id: string | null = to;
        id !== null;
        id = previous.get(id) ?? null
      )
        path.unshift(id);
      return path;
    }
    for (const id of neighbours.get(queue[i]) ?? [])
      if (!previous.has(id)) {
        previous.set(id, queue[i]);
        queue.push(id);
      }
  }
  return [];
}

export function connection(
  me: Me,
  person: GraphNode,
  relationship: Relationship | undefined,
  links: GraphLink[],
) {
  const chain = chainTo(me.id, person.id, links);
  const facts: string[] = [];
  const kind = relationship?.kind;
  let level = 0,
    title = "No link found yet";
  if (kind === "met" || chain.length === 2) {
    level = 4;
    title = "You have met";
  } else if (kind === "planned") {
    level = 3;
    title = "You both plan to meet";
  } else if (kind === "invited_you") {
    level = 3;
    title = "They invited you to meet";
  } else if (kind === "you_invited") {
    level = 3;
    title = "You invited them to meet";
  } else if (kind === "suggested") {
    level = 2;
    title = "Suggested for you";
  }
  if (level) facts.push(title + ".");
  if (relationship?.reason) facts.push(relationship.reason);
  const groups = person.groups.filter((g) => me.groups.includes(g));
  const tags = person.tags.filter((t) => me.tags.includes(t));
  if (groups.length) facts.push(`Shared communities: ${groups.join(", ")}.`);
  if (tags.length) facts.push(`Shared interests: ${tags.join(", ")}.`);
  if (chain.length > 2)
    facts.push(
      `A chain of ${chain.length - 1} confirmed meetings connects you.`,
    );
  if (relationship?.via.length)
    facts.push(
      `Possible introductions through ${relationship.via.map((p) => p.name).join(", ")}.`,
    );
  if (
    !level &&
    (groups.length ||
      tags.length ||
      chain.length > 2 ||
      relationship?.via.length)
  ) {
    level = 1;
    title =
      chain.length > 2 || relationship?.via.length
        ? "An introduction away"
        : "Common ground";
  }
  if (!facts.length)
    facts.push(
      "No relationship or shared community or interest appears in the available data.",
    );
  return { level, title, facts, chain };
}
