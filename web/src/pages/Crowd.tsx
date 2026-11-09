import { useEffect, useState } from "react";
import { errorMessage, getCrowd } from "../api/client";
import type { Crowd as CrowdData } from "../api/types";
import { ErrorNote } from "../ui";

const COMFORT_LABELS: Record<string, string> = {
  open: "Open to anyone",
  small_groups: "Prefer small groups",
  one_on_one: "Prefer one-on-one",
};

/** The organizer board: what people ask for against what they offer, in counts only. */
export default function Crowd() {
  const [crowd, setCrowd] = useState<CrowdData | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    function load() {
      getCrowd()
        .then((fresh) => { setCrowd(fresh); setError(""); })
        .catch((err) => setError(errorMessage(err)));
    }
    load();
    const timer = setInterval(load, 15000);
    return () => clearInterval(timer);
  }, []);

  if (!crowd) return error ? <ErrorNote message={error} /> : <p className="muted" role="status">Counting…</p>;

  const withoutGroup = Math.max(crowd.registered - crowd.in_groups, 0);

  return (
    <>
      <h1>What the crowd needs</h1>
      <p className="lede">
        For organizers, while there is still time to act. Counts only: no names, and nothing
        that describes fewer than three people.
      </p>

      <h2>From sign-up to meeting</h2>
      <dl className="stats">
        <div><dt>Registered on Hallway</dt><dd>{crowd.registered}</dd></div>
        <div><dt>In an arrival group</dt><dd>{crowd.in_groups}</dd></div>
        <div><dt>Still without a group</dt><dd>{withoutGroup}</dd></div>
        <div><dt>Groups with a meeting point</dt><dd>{crowd.groups_with_meeting} <small>of {crowd.groups}</small></dd></div>
        <div><dt>Pairs who plan to meet</dt><dd>{crowd.plans}</dd></div>
        <div><dt>Invitations waiting for an answer</dt><dd>{crowd.invitations}</dd></div>
        <div><dt>Pairs who have met</dt><dd>{crowd.meetings}</dd></div>
        <div><dt>Checked in to a room</dt><dd>{crowd.checked_in}</dd></div>
      </dl>
      <p className="muted">
        Room check-ins are made in Hallway. Luma registration and event check-in are not
        connected, so attendance beyond these numbers is unknown, not zero.
      </p>

      <h2 id="topics-title">Asked for against offered</h2>
      {crowd.topics.length === 0 ? (
        <p className="muted">Not enough people yet. Topics appear once at least three people are behind one.</p>
      ) : (
        <>
          <table className="topics" aria-labelledby="topics-title">
            <thead>
              <tr>
                <th scope="col">Topic</th>
                <th scope="col">Asking</th>
                <th scope="col">Offering</th>
                <th scope="col">What it means</th>
              </tr>
            </thead>
            <tbody>
              {crowd.topics.map((topic) => (
                <tr key={topic.topic}>
                  <th scope="row">{topic.topic}</th>
                  <td>{topic.asking}</td>
                  <td>{topic.offering}</td>
                  <td>{gap(topic.asking, topic.offering)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted">
            Topics are the most used tags. We count the people whose asks or offers mention
            the words, so this is a guide to what to schedule, not a measurement of meaning.
          </p>
        </>
      )}

      <h2>How people like to meet</h2>
      {crowd.comfort.length === 0 ? (
        <p className="muted">Not enough people yet.</p>
      ) : (
        <ul className="pairs">
          {crowd.comfort.map((row) => (
            <li key={row.key}><strong>{row.count}</strong> {COMFORT_LABELS[row.key] ?? row.key}</li>
          ))}
        </ul>
      )}
      <p className="muted">Use this to plan quiet and seated spaces. It is a preference, not a headcount of needs.</p>
      <ErrorNote message={error} />
    </>
  );
}

function gap(asking: number, offering: number): string {
  if (asking > offering) return `${asking - offering} more asking than offering`;
  if (offering > asking) return `${offering - asking} more offering than asking`;
  return "Balanced";
}
