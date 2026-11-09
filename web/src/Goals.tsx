import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { errorMessage, getGoals, setGoals } from "./api/client";
import type { Goal } from "./api/types";
import { ErrorNote } from "./ui";

const MAX_GOALS = 5;
const IDEAS = [
  "Find a collaborator",
  "Learn about a topic I am new to",
  "Meet people from a community",
  "Help someone with something I can offer",
];

/**
 * My own goals for the conference. Private, and only I tick them: meeting someone or
 * scanning a code never completes a goal. `readOnly` is for the recap, which just reports.
 */
export function GoalBoard({ readOnly = false }: { readOnly?: boolean }) {
  const [goals, setLocal] = useState<Goal[] | null>(null); // null = still loading
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getGoals().then((out) => setLocal(out.goals)).catch((err) => setError(errorMessage(err)));
  }, []);

  // One save at a time. The whole list is sent each time, so two saves in flight could
  // reach the server in the wrong order and the older list would win. While one is in
  // flight, only the newest wanted list is kept, and it is sent when the first returns.
  const inFlight = useRef(false);
  const queued = useRef<{ goals: Goal[]; message: string; onSuccess?: () => void } | null>(null);
  const saved = useRef<Goal[]>([]); // what the server last confirmed

  useEffect(() => {
    if (goals !== null && !inFlight.current && queued.current === null) saved.current = goals;
  }, [goals]);

  async function send(next: Goal[], message: string, onSuccess?: () => void) {
    inFlight.current = true;
    setSaving(true);
    let current: { goals: Goal[]; message: string; onSuccess?: () => void } | null = { goals: next, message, onSuccess };
    try {
      while (current) {
        try {
          const confirmed = (await setGoals(current.goals)).goals;
          saved.current = confirmed;
          if (queued.current === null) {
            setLocal(confirmed);
            setStatus(current.message);
            current.onSuccess?.();
          }
        } catch (err) {
          queued.current = null;
          setLocal(saved.current); // show what is really stored
          setStatus("");
          setError(errorMessage(err));
          break;
        }
        current = queued.current;
        queued.current = null;
      }
    } finally {
      inFlight.current = false;
      setSaving(false);
    }
  }

  /** Shows the change at once and saves it. */
  function save(next: Goal[], message: string, onSuccess?: () => void) {
    setLocal(next);
    setError("");
    if (inFlight.current) queued.current = { goals: next, message, onSuccess };
    else void send(next, message, onSuccess);
  }

  function add(event: FormEvent) {
    event.preventDefault();
    const entered = text;
    const wanted = text.trim();
    if (!wanted || !goals) return;
    save([...goals, { text: wanted, done: false }], "Goal added.", () => setText((current) => current === entered ? "" : current));
  }

  if (goals === null) return error ? <ErrorNote message={error} /> : <p className="muted" role="status">Loading your goals…</p>;

  const done = goals.filter((goal) => goal.done).length;
  const full = goals.length >= MAX_GOALS;
  const unused = IDEAS.filter((idea) => !goals.some((goal) => goal.text === idea));

  return (
    <>
      {goals.length === 0 && <p className="muted">{readOnly ? "You did not set any goals." : "No goals yet. Pick one below or write your own."}</p>}
      {goals.length > 0 && (
        <>
          <p className="muted">{done} of {goals.length} done. Only you can see these, and only you tick them.</p>
          <ul className="goals">
            {goals.map((goal, index) => (
              <li key={`${index}-${goal.text}`}>
                <label className="choice">
                  <input type="checkbox" checked={goal.done} disabled={readOnly || saving}
                    onChange={(e) => save(
                      goals.map((g, i) => (i === index ? { ...g, done: e.target.checked } : g)),
                      e.target.checked ? "Marked as done." : "Marked as not done.",
                    )} />
                  <span className={goal.done ? "goal-done" : undefined}>{goal.text}</span>
                </label>
                {!readOnly && (
                  <button type="button" className="link-button" disabled={saving}
                    aria-label={`Remove goal: ${goal.text}`}
                    onClick={() => save(goals.filter((_, i) => i !== index), "Goal removed.")}>
                    Remove
                  </button>
                )}
              </li>
            ))}
          </ul>
        </>
      )}

      {!readOnly && !full && (
        <>
          {unused.length > 0 && (
            <ul className="ideas" aria-label="Goal ideas">
              {unused.map((idea) => (
                <li key={idea}>
                  <button type="button" className="chip" disabled={saving}
                    onClick={() => save([...goals, { text: idea, done: false }], "Goal added.")}>
                    + {idea}
                  </button>
                </li>
              ))}
            </ul>
          )}
          <form onSubmit={add} className="form goal-form">
            <label htmlFor="goal-text">Add your own goal</label>
            <input id="goal-text" maxLength={120} value={text} disabled={saving} onChange={(e) => setText(e.target.value)} />
            <button type="submit" className="button secondary" disabled={!text.trim() || saving}>Add goal</button>
          </form>
        </>
      )}
      {!readOnly && full && <p className="muted">Five is the limit. Remove one to add another.</p>}
      {/* Always mounted, so screen readers announce each change. */}
      <p className="muted" role="status">{status}</p>
      <ErrorNote message={error} />
    </>
  );
}
