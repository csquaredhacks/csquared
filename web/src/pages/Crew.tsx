import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import {
  acceptCrew, ApiError, declineCrew, errorMessage, getCrew, leaveCrew, setCrewMeeting, suggestCrew,
} from "../api/client";
import type { CrewOut } from "../api/client";
import { ErrorNote, PersonCard } from "../ui";

const LOCAL_ZONE = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";

/** "2026-11-10T08:30" from a datetime-local input, plus the browser's offset, as ISO 8601. */
function withOffset(local: string): string {
  const offsetMin = -new Date(local).getTimezoneOffset();
  const sign = offsetMin >= 0 ? "+" : "-";
  const abs = Math.abs(offsetMin);
  const hh = String(Math.floor(abs / 60)).padStart(2, "0");
  const mm = String(abs % 60).padStart(2, "0");
  return `${local}:00${sign}${hh}:${mm}`;
}

function formatMeeting(startsAt: string, timezone: string): string {
  try {
    // dateStyle cannot be combined with timeZoneName, so the zone is appended by hand.
    const text = new Intl.DateTimeFormat(undefined, {
      dateStyle: "full", timeStyle: "short", timeZone: timezone,
    }).format(new Date(startsAt));
    return `${text} (${timezone})`;
  } catch {
    return `${startsAt} (${timezone})`;
  }
}

export default function Crew() {
  const navigate = useNavigate();
  const [state, setState] = useState<CrewOut | null>(null); // null = loading
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<"" | "join" | "decline" | "other">("");
  const [companion, setCompanion] = useState(false);
  const [place, setPlace] = useState("");
  const [when, setWhen] = useState("");

  function fail(err: unknown) {
    if (err instanceof ApiError && err.status === 401) navigate("/", { replace: true });
    else setError(errorMessage(err));
  }

  async function run(kind: "join" | "decline" | "other", action: () => Promise<CrewOut>) {
    setBusy(kind);
    setError("");
    try {
      setState(await action());
    } catch (err) {
      fail(err);
      // A 409 means the crew changed (for example it filled up): show the fresh state.
      getCrew().then(setState).catch(() => undefined);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    getCrew().then(setState).catch(fail);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function saveMeeting(event: FormEvent) {
    event.preventDefault();
    if (!place.trim() || !when) return;
    run("other", () => setCrewMeeting({ place: place.trim(), starts_at: withOffset(when), timezone: LOCAL_ZONE }));
  }

  const crew = state?.crew ?? null;

  return (
    <>
      <h1>Your crew</h1>
      <p className="lede">
        A few people to walk in with, so nobody arrives alone. Nothing happens until you say yes,
        and you can leave at any time.
      </p>
      <ErrorNote message={error} />
      {state === null && !error && <p className="muted" role="status">Checking for your crew…</p>}

      {state?.status === "none" && (
        <div className="empty">
          <h2>No crew yet</h2>
          <p>We suggest a small group from your best matches. Group size follows your comfort setting.</p>
          <button type="button" className="button" disabled={!!busy} onClick={() => run("other", suggestCrew)}>
            {busy === "other" ? "Looking…" : "Suggest a crew"}
          </button>
        </div>
      )}

      {crew && (
        <section aria-labelledby="crew-heading">
          <h2 id="crew-heading">
            {state?.status === "member" ? "You're in" : "Suggested for you"}
          </h2>
          <p><strong>Why:</strong> {crew.why}</p>
          <p className="muted">
            {crew.seats_taken} of {crew.limit} places taken
            {state?.bringing_companion ? ", including your companion" : ""}.
          </p>

          {crew.members.length === 0 ? (
            <p className="muted">Nobody has accepted yet. You could be first.</p>
          ) : (
            <ul className="grid" aria-label="Crew members">
              {crew.members.map((person) => (
                <li key={person.id}><PersonCard person={person} nested /></li>
              ))}
            </ul>
          )}

          <h3>Where and when you meet</h3>
          {crew.meeting ? (
            <p>
              <strong>{crew.meeting.place}</strong>, {formatMeeting(crew.meeting.starts_at, crew.meeting.timezone)}.
              <span className="muted"> Set by {crew.meeting.set_by}.</span>
            </p>
          ) : (
            <p className="muted">Not agreed yet. Any member can propose a place and time.</p>
          )}

          {state?.status === "suggested" && (
            <>
              <label className="choice">
                <input type="checkbox" checked={companion} onChange={(e) => setCompanion(e.target.checked)} />
                I'm bringing a friend or companion (they take a place too)
              </label>
              <button type="button" className="button" disabled={!!busy}
                onClick={() => run("join", () => acceptCrew({ companion }))}>
                {busy === "join" ? "Joining…" : "Join this crew"}
              </button>
              <button type="button" className="button secondary" disabled={!!busy} onClick={() => run("decline", declineCrew)}>
                {busy === "decline" ? "Declining…" : "No thanks"}
              </button>
            </>
          )}

          {state?.status === "member" && (
            <>
              <form onSubmit={saveMeeting} aria-labelledby="meeting-form-heading">
                <h3 id="meeting-form-heading">{crew.meeting ? "Change the plan" : "Propose a plan"}</h3>
                <label htmlFor="meeting-place">Meeting point</label>
                <input id="meeting-place" value={place} maxLength={200} required
                  placeholder="North entrance, by the ramp" onChange={(e) => setPlace(e.target.value)} />
                <label htmlFor="meeting-when">Date and time ({LOCAL_ZONE})</label>
                <input id="meeting-when" type="datetime-local" value={when} required
                  onChange={(e) => setWhen(e.target.value)} />
                <button type="submit" className="button" disabled={!!busy}>Save the plan</button>
              </form>
              <button type="button" className="button secondary" disabled={!!busy} onClick={() => run("other", leaveCrew)}>
                Leave this crew
              </button>
            </>
          )}
        </section>
      )}
    </>
  );
}
