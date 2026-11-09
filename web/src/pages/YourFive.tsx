import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, errorMessage, getMatches } from "../api/client";
import type { Match } from "../api/types";
import { ErrorNote, PersonCard } from "../ui";

export default function YourFive() {
  const navigate = useNavigate();
  const [matches, setMatches] = useState<Match[] | null>(null); // null = still loading
  const [error, setError] = useState("");

  function load() {
    setError("");
    getMatches()
      .then(setMatches)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) navigate("/", { replace: true });
        else setError(errorMessage(err));
      });
  }
  useEffect(load, [navigate]);

  return (
    <>
      <h1>Your five</h1>
      <p className="lede">
        The people here most worth crossing the room for. Found one?{" "}
        <Link to="/me">Show them your code</Link> to connect.
      </p>
      <ErrorNote message={error} />
      {matches === null && !error && <p className="muted" role="status">Looking around the room…</p>}

      {matches !== null && matches.length === 0 && (
        <div className="empty">
          <h2>Nobody yet, but the room is filling up</h2>
          <p>Matches appear as more people register. Meanwhile, your code works with anyone you meet.</p>
          <button type="button" className="button secondary" onClick={load}>Check again</button>
        </div>
      )}

      <ol className="grid">
        {matches?.map((match, index) => (
          <li key={match.attendee.id}>
            <PersonCard person={match.attendee}>
              <span className="rank" aria-hidden="true">{index + 1}</span>
              <p className="reason"><strong>Why:</strong> {match.reason}</p>
              <blockquote className="icebreaker">{match.icebreaker}</blockquote>
              <p><Link to={`/graph?focus=${match.attendee.id}`}>Find them on the graph</Link></p>
            </PersonCard>
          </li>
        ))}
      </ol>
    </>
  );
}
