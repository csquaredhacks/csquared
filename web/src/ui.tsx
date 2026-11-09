import type { ReactNode } from "react";
import type { Attendee } from "./api/types";

export function Tags({ tags }: { tags: string[] }) {
  if (tags.length === 0) return null;
  return (
    <ul className="tags" aria-label="Tags">
      {tags.map((tag) => <li key={tag}>{tag}</li>)}
    </ul>
  );
}

/** role="alert" makes screen readers announce the message as soon as it appears. */
export function ErrorNote({ message }: { message: string }) {
  if (!message) return null;
  return <p className="error" role="alert">{message}</p>;
}

/**
 * One person: name, groups, what they work on, then whatever the page adds, then tags.
 * `nested` is for cards that sit under an <h2> section title, so heading levels stay in order.
 */
export function PersonCard({ person, nested, children }: { person: Attendee; nested?: boolean; children?: ReactNode }) {
  const Heading = nested ? "h3" : "h2";
  return (
    <article className="card">
      <Heading className="card-name">{person.name}</Heading>
      {person.groups.length > 0 && <p className="card-groups">{person.groups.join(" · ")}</p>}
      <p>{person.working_on}</p>
      {children}
      <Tags tags={person.tags} />
    </article>
  );
}
