import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, errorMessage, getRecap } from "../api/client";
import type { Recap as RecapData } from "../api/types";
import { GoalBoard } from "../Goals";
import { ErrorNote, PersonCard } from "../ui";

export default function Recap() {
  const navigate = useNavigate();
  const [recap, setRecap] = useState<RecapData | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getRecap()
      .then(setRecap)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) navigate("/", { replace: true });
        else setError(errorMessage(err));
      });
  }, [navigate]);

  if (!recap) return error ? <ErrorNote message={error} /> : <p className="muted" role="status">Writing your recap…</p>;

  return (
    <>
      <h1>Your recap</h1>
      <dl className="stats">
        <div><dt>People met</dt><dd>{recap.connections.length}</dd></div>
        <div><dt>Groups bridged</dt><dd>{recap.groups_bridged}</dd></div>
      </dl>

      {recap.nudges.length > 0 && (
        <section aria-labelledby="nudges-title">
          <h2 id="nudges-title">Follow up while it's fresh</h2>
          <ul className="nudges">
            {recap.nudges.map((nudge) => <li key={nudge}>{nudge}</li>)}
          </ul>
        </section>
      )}

      <section aria-labelledby="goals-title">
        <h2 id="goals-title">Your goals</h2>
        <GoalBoard readOnly />
      </section>

      <section aria-labelledby="met-title">
        <h2 id="met-title">People you met</h2>
        {recap.connections.length === 0 && (
          <p className="empty">Nobody yet. <Link to="/plan">Start with your five</Link>.</p>
        )}
        <ul className="grid">
          {recap.connections.map((person) => (
            <li key={person.id}>
              <PersonCard person={person} nested>
                {person.offers && <p><strong>Offers:</strong> {person.offers}</p>}
              </PersonCard>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
