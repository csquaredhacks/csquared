import { useEffect, useState } from "react";
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

  useEffect(() => {
    getGoals().then((out) => setLocal(out.goals)).catch((err) => setError(errorMessage(err)));
  }, []);

  /** Shows the change at once, saves it, and puts the old list back if saving fails. */
  async function save(next: Goal[], message: string) {
    const before = goals;
    setLocal(next);
    setError("");
    try {
      setLocal((await setGoals(next)).goals);
      setStatus(message);
    } catch (err) {
      setLocal(before);
      setStatus("");
      setError(errorMessage(err));
    }
  }

  function add(event: FormEvent) {
    event.preventDefault();
    const wanted = text.trim();
    if (!wanted || !goals) return;
    setText("");
    save([...goals, { text: wanted, done: false }], "Goal added.");
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
                  <input type="checkbox" checked={goal.done} disabled={readOnly}
                    onChange={(e) => save(
                      goals.map((g, i) => (i === index ? { ...g, done: e.target.checked } : g)),
                      e.target.checked ? "Marked as done." : "Marked as not done.",
                    )} />
                  <span className={goal.done ? "goal-done" : undefined}>{goal.text}</span>
                </label>
                {!readOnly && (
                  <button type="button" className="link-button"
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
                  <button type="button" className="chip"
                    onClick={() => save([...goals, { text: idea, done: false }], "Goal added.")}>
                    + {idea}
                  </button>
                </li>
              ))}
            </ul>
          )}
          <form onSubmit={add} className="form goal-form">
            <label htmlFor="goal-text">Add your own goal</label>
            <input id="goal-text" maxLength={120} value={text} onChange={(e) => setText(e.target.value)} />
            <button type="submit" className="button secondary" disabled={!text.trim()}>Add goal</button>
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
